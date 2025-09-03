# source/services/vault/app/main.py

from __future__ import annotations

import asyncio
import json
import ssl
import subprocess
import time
import http.client
from pathlib import Path
from typing import Final

from core.base.service import ContextMicroservice
from core.runtime.status import ServiceStatus
from core.settings.settings import SETTINGS
from core.net.port import wait_port


# ───────────────────────────── Paths & Const ─────────────────────────────
CERTS_DIR: Final[Path] = Path(SETTINGS.paths.tls_certs_dir)
SECRETS_DIR: Final[Path] = Path("/vault/secrets")
SECRETS_DIR.mkdir(parents=True, exist_ok=True)

ROOT_TOKEN_JSON: Final[Path] = SECRETS_DIR / "root_vault_token.json"

CFG_HTTP:  Final[str] = "/vault/config/vault_http.hcl"
CFG_HTTPS: Final[str] = "/vault/config/vault_https.hcl"

CA_PEM  = CERTS_DIR / "ca.crt"
CRT_VLT = CERTS_DIR / "vault.crt"
KEY_VLT = CERTS_DIR / "vault.key"

WAIT_HEALTH_SEC: Final[int] = 30

# PKI / domain (из SETTINGS)
DOMAIN_ROOT: Final[str] = SETTINGS.domain.root
PKI_ROOT_PATH: Final[str] = SETTINGS.vault.pki_root_path  # например: pki-root
PKI_INT_PATH:  Final[str] = SETTINGS.vault.pki_int_path   # например: pki-int
PKI_ROLE:      Final[str] = SETTINGS.vault.pki_role       # например: terminal-leaf

PKI_ROOT_TTL:     Final[str] = "87600h"
PKI_ROLE_MAX_TTL: Final[str] = "720h"

# Лифы — по именам сервисов; SAN-список берём из SETTINGS.policy.san_list
LEAF_SVCS: Final[dict[str, dict[str, str]]] = {
    "consul":  {"common_name": f"consul.{DOMAIN_ROOT}",  "alt_names": "server.dc-1.consul,consul,localhost"},
    "vault":   {"common_name": f"vault.{DOMAIN_ROOT}",   "alt_names": "vault,localhost"},
    "traefik": {"common_name": f"traefik.{DOMAIN_ROOT}", "alt_names": "traefik,localhost"},
}

SECRETS_KV: Final[dict[str, dict[str, str]]] = {
    "database": {"user": "speculorg", "pass": "speculpwd"},
    "rabbitmq": {"user": "guest",     "pass": "guest"},
    "keycloak": {"user": "admin",     "pass": "admin"},
}

POLICIES: Final[dict[str, str]] = {
    "read-db": """
        path "secret/data/database" {
          capabilities = ["read"]
        }
    """,
}

APPROLES: Final[dict[str, dict]] = {
    "db-role": {"policies": ["read-db"], "secret_id_ttl": "0s"},
}


# ───────────────────────────── HTTP helpers ─────────────────────────────
def _http_conn(https: bool) -> http.client.HTTPConnection | http.client.HTTPSConnection:
    host = SETTINGS.vault.host
    if not https:
        return http.client.HTTPConnection(host, SETTINGS.vault.http_port, timeout=6)
    ctx = ssl.create_default_context(cafile=str(CA_PEM)) if CA_PEM.exists() else ssl.create_default_context()
    return http.client.HTTPSConnection(host, SETTINGS.vault.https_port, timeout=6, context=ctx)


def _api(method: str, path: str, *, token: str | None = None, https: bool = False, body: dict | None = None) -> http.client.HTTPResponse:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Vault-Token"] = token
    data = json.dumps(body).encode("utf-8") if body is not None else None
    conn = _http_conn(https)
    conn.request(method, path, body=data, headers=headers)
    return conn.getresponse()


def _health_ok(https: bool, timeout: float = WAIT_HEALTH_SEC) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            resp = _api("GET", "/v1/sys/health", https=https)
            # 200/429/501/503 — валидные статусы жизненного цикла Vault
            if resp.status in (200, 429, 501, 503):
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


# ───────────────────────────── Service ─────────────────────────────
class VaultService(ContextMicroservice):
    async def initialize(self) -> None:
        first_run = not (CRT_VLT.exists() and CA_PEM.exists())

        # 1) first boot (HTTP), init/unseal + PKI/KV/Policies/AppRoles -> issue leaf certs
        if first_run:
            if not await self._start_vault(cfg=CFG_HTTP, https=False):
                return
            await self._ensure_init_unseal_http()
            await self._ensure_kv_policies_roles_http()
            await self._ensure_pki_and_certs_http()
            await self._stop_child()

        # 2) normal run (TLS)
        self._set_status(ServiceStatus.TLS_TRANSITION, "vault.https.start")
        if not await self._start_vault(cfg=CFG_HTTPS, https=True):
            return
        self.svc_set_tls_active(True)

    async def start(self) -> None:
        self._set_status(ServiceStatus.RUNNING, "vault.up")
        while not getattr(self, "_shutdown").is_set():
            await asyncio.sleep(5)

    # ── helpers ──
    async def _start_vault(self, *, cfg: str, https: bool) -> bool:
        cmd = ["vault", "server", f"-config={cfg}"]
        self.log.info("evt=proc.start app=vault mode=%s cmd=%s", "https" if https else "http", " ".join(cmd))
        proc = subprocess.Popen(cmd)  # noqa: S603
        self.proc_attach(proc)

        host = SETTINGS.vault.host
        port = SETTINGS.vault.https_port if https else SETTINGS.vault.http_port
        if not await wait_port(host, port, timeout=60.0):
            self.log.error("evt=wait.port.timeout host=%s port=%s", host, port)
            return False

        if not await asyncio.get_event_loop().run_in_executor(None, _health_ok, https):
            self.log.error("evt=wait.health.timeout mode=%s", "https" if https else "http")
            return False

        self.log.info("evt=vault.ready mode=%s", "https" if https else "http")
        return True

    async def _stop_child(self) -> None:
        if getattr(self, "_child", None) and self._child.poll() is None:
            self.log.info("evt=proc.stop app=vault")
            try:
                self._child.terminate()
                await asyncio.get_event_loop().run_in_executor(None, self._child.wait, 10)
            except Exception:
                try:
                    self._child.kill()
                except Exception:
                    pass

    # ── init/unseal/kv/policies/pki (HTTP) ──
    async def _ensure_init_unseal_http(self) -> None:
        # already initialised?
        resp = _api("GET", "/v1/sys/health", https=False)
        data = json.loads(resp.read().decode("utf-8") or "{}")
        if not ROOT_TOKEN_JSON.exists():
            if data.get("initialized"):
                self.log.error("evt=vault.init.missing.root_token_json")
                return
            self.log.info("evt=vault.init.start")
            init = _api("PUT", "/v1/sys/init", https=False, body={"secret_shares": 1, "secret_threshold": 1})
            if not (200 <= init.status < 300):
                self.log.error("evt=vault.init.fail code=%s", init.status); return
            body = init.read().decode("utf-8")
            ROOT_TOKEN_JSON.write_text(body, encoding="utf-8")
            self.log.info("evt=vault.init.ok file=%s", ROOT_TOKEN_JSON)

        keys = json.loads(ROOT_TOKEN_JSON.read_text(encoding="utf-8"))
        root_token = keys.get("root_token", "")
        unseal_key = (keys.get("keys") or [""])[0]

        # unseal if sealed
        health = _api("GET", "/v1/sys/health", https=False)
        hjson = json.loads(health.read().decode("utf-8") or "{}")
        if hjson.get("sealed", True):
            self.log.info("evt=vault.unseal.start")
            res = _api("PUT", "/v1/sys/unseal", https=False, body={"key": unseal_key})
            if not (200 <= res.status < 300):
                self.log.error("evt=vault.unseal.fail code=%s", res.status); return
            self.log.info("evt=vault.unseal.ok")

        # enable approle auth if not enabled
        auths = _api("GET", "/v1/sys/auth", token=root_token, https=False)
        amap = json.loads(auths.read().decode("utf-8") or "{}")
        if "approle/" not in amap:
            _api("POST", "/v1/sys/auth/approle", token=root_token, https=False, body={"type": "approle"}).read()
            self.log.info("evt=vault.auth.enable method=approle")

    async def _ensure_kv_policies_roles_http(self) -> None:
        keys = json.loads(ROOT_TOKEN_JSON.read_text(encoding="utf-8"))
        root_token = keys.get("root_token", "")

        # KV v2 at secret/
        mounts = _api("GET", "/v1/sys/mounts", token=root_token, https=False)
        mjson = json.loads(mounts.read().decode("utf-8") or "{}")
        if "secret/" not in mjson:
            _api("POST", "/v1/sys/mounts/secret", token=root_token, https=False,
                 body={"type": "kv", "options": {"version": "2"}}).read()
            self.log.info("evt=vault.mount.kv path=secret/")

        # secrets (seed)
        for path, data in SECRETS_KV.items():
            _api("POST", f"/v1/secret/data/{path}", token=root_token, https=False, body={"data": data}).read()
            self.log.info("evt=vault.secret.upsert path=%s", path)

        # policies
        resp = _api("GET", "/v1/sys/policies/acl", token=root_token, https=False)
        existing = set(json.loads(resp.read().decode("utf-8") or "{}").keys())
        for name, rules in POLICIES.items():
            if name in existing:
                self.log.info("evt=vault.policy.exists name=%s", name)
                continue
            _api("PUT", f"/v1/sys/policies/acl/{name}", token=root_token, https=False,
                 body={"policy": rules, "type": "service"}).read()
            self.log.info("evt=vault.policy.create name=%s", name)

        # approles
        for role, cfg in APPROLES.items():
            chk = _api("GET", f"/v1/auth/approle/role/{role}", token=root_token, https=False)
            if 200 <= chk.status < 300:
                self.log.info("evt=vault.approle.exists name=%s", role)
                continue
            _api("POST", f"/v1/auth/approle/role/{role}", token=root_token, https=False, body=cfg).read()
            self.log.info("evt=vault.approle.create name=%s", role)

    async def _ensure_pki_and_certs_http(self) -> None:
        keys = json.loads(ROOT_TOKEN_JSON.read_text(encoding="utf-8"))
        root_token = keys.get("root_token", "")

        # Проверяем/монтируем PKI root и int по путям из SETTINGS
        mounts = _api("GET", "/v1/sys/mounts", token=root_token, https=False)
        mjson = json.loads(mounts.read().decode("utf-8") or "{}")

        if f"{PKI_ROOT_PATH}/" not in mjson:
            _api("POST", f"/v1/sys/mounts/{PKI_ROOT_PATH}", token=root_token, https=False, body={"type": "pki"}).read()
            self.log.info("evt=vault.mount.pki path=%s/", PKI_ROOT_PATH)

        if f"{PKI_INT_PATH}/" not in mjson:
            _api("POST", f"/v1/sys/mounts/{PKI_INT_PATH}", token=root_token, https=False, body={"type": "pki"}).read()
            self.log.info("evt=vault.mount.pki path=%s/", PKI_INT_PATH)

        # root CA
        if not CA_PEM.exists():
            self.log.info("evt=vault.pki.root.generate cn=%s", DOMAIN_ROOT)
            res = _api("POST", f"/v1/{PKI_ROOT_PATH}/root/generate/internal", token=root_token, https=False,
                       body={"common_name": DOMAIN_ROOT, "ttl": PKI_ROOT_TTL})
            if not (200 <= res.status < 300):
                self.log.error("evt=vault.pki.root.fail code=%s", res.status); return
            ca_pem = json.loads(res.read().decode("utf-8") or "{}").get("data", {}).get("certificate", "")
            CA_PEM.write_text(ca_pem, encoding="utf-8")
            CA_PEM.chmod(0o644)
            self.log.info("evt=vault.pki.root.saved path=%s", CA_PEM)

            _api("POST", f"/v1/{PKI_ROOT_PATH}/config/urls", token=root_token, https=False, body={
                "issuing_certificates": f"http://{SETTINGS.vault.host}:{SETTINGS.vault.http_port}/v1/{PKI_ROOT_PATH}/ca",
                "crl_distribution_points": f"http://{SETTINGS.vault.host}:{SETTINGS.vault.http_port}/v1/{PKI_ROOT_PATH}/crl",
            }).read()

            # Создаём промежуточный CA и подписываем его рутом
            # 1) генерируем CSR для intermediate
            csr_res = _api("POST", f"/v1/{PKI_INT_PATH}/intermediate/generate/internal",
                           token=root_token, https=False, body={"common_name": f"intermediate.{DOMAIN_ROOT}"})
            if not (200 <= csr_res.status < 300):
                self.log.error("evt=vault.pki.int.csr.fail code=%s", csr_res.status); return
            csr = json.loads(csr_res.read().decode("utf-8") or "{}").get("data", {}).get("csr", "")

            # 2) root подписывает
            sign_res = _api("POST", f"/v1/{PKI_ROOT_PATH}/root/sign-intermediate",
                            token=root_token, https=False, body={"csr": csr, "ttl": PKI_ROOT_TTL})
            if not (200 <= sign_res.status < 300):
                self.log.error("evt=vault.pki.int.sign.fail code=%s", sign_res.status); return
            cert = json.loads(sign_res.read().decode("utf-8") or "{}").get("data", {}).get("certificate", "")

            # 3) публим сертификат в intermediate
            _api("POST", f"/v1/{PKI_INT_PATH}/intermediate/set-signed",
                 token=root_token, https=False, body={"certificate": cert}).read()
            self.log.info("evt=vault.pki.int.ready")

        # роль для выдачи leaf в intermediate PKI
        _api("POST", f"/v1/{PKI_INT_PATH}/roles/{PKI_ROLE}", token=root_token, https=False, body={
            "allowed_domains": f"{DOMAIN_ROOT},consul,vault,traefik,localhost",
            "allow_subdomains": True,
            "allow_bare_domains": True,
            "allow_glob_domains": True,
            "max_ttl": PKI_ROLE_MAX_TTL,
        }).read()

        # leafs
        for name, params in LEAF_SVCS.items():
            crt, key = CERTS_DIR / f"{name}.crt", CERTS_DIR / f"{name}.key"
            if crt.exists() and key.exists():
                self.log.info("evt=vault.pki.leaf.exists name=%s", name); continue
            self.log.info("evt=vault.pki.issue name=%s cn=%s", name, params.get("common_name"))
            res = _api("POST", f"/v1/{PKI_INT_PATH}/issue/{PKI_ROLE}", token=root_token, https=False, body=params)
            if not (200 <= res.status < 300):
                self.log.error("evt=vault.pki.issue.fail name=%s code=%s", name, res.status); continue
            data = json.loads(res.read().decode("utf-8") or "{}").get("data", {})
            crt.write_text(data.get("certificate", ""), encoding="utf-8"); crt.chmod(0o644)
            key.write_text(data.get("private_key", ""), encoding="utf-8");  key.chmod(0o600)
            self.log.info("evt=vault.pki.leaf.saved name=%s crt=%s key=%s", name, crt, key)


async def main() -> None:
    await VaultService().serve()


if __name__ == "__main__":
    asyncio.run(main())
