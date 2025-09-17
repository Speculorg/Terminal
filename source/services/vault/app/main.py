# source/services/vault/app/main.py

from __future__ import annotations
import asyncio
import json
import ssl
import subprocess
import time
import http.client
import hashlib
from pathlib import Path
from typing import Final, Dict

from core.base.service import ContextMicroservice
from core.runtime.status import ServiceStatus
from core.settings.settings import SETTINGS
from core.net.port import wait_port
from core.logging import get_logger
from core.kv import KV, build_consul_kv_from_settings

log = get_logger("vault.app")


# ----------------------------- Paths & Const -----------------------------
CERTS_DIR: Final[Path] = Path(SETTINGS.paths.tls_certs_dir)
SECRETS_DIR: Final[Path] = Path("/vault/secrets")
SECRETS_DIR.mkdir(parents=True, exist_ok=True)

ROOT_TOKEN_JSON: Final[Path] = SECRETS_DIR / "root_vault_token.json"

CFG_HTTP:  Final[str] = "/vault/config/vault_http.hcl"
CFG_HTTPS: Final[str] = "/vault/config/vault_https.hcl"

CA_PEM  = CERTS_DIR / "ca.crt"
CRT_VLT = CERTS_DIR / "vault.crt"
KEY_VLT = CERTS_DIR / "vault.key"

# Consul tokens issued by Consul service (must be mounted read-only here)
CONSUL_TOKENS_DIR: Final[Path] = Path("/consul/secrets")
VAULT_CONSUL_TOKEN_FILE: Final[Path] = CONSUL_TOKENS_DIR / "vault_consul_token"

# Тайминги из SETTINGS
INIT_TIMEOUT = float(SETTINGS.timeouts.init_timeout_s)
RETRY_BASE   = float(SETTINGS.timeouts.retry_interval_s)
RETRY_MAX    = float(SETTINGS.timeouts.max_retry_interval_s)
BACKOFF      = float(SETTINGS.timeouts.backoff_factor)

# PKI / domain (из SETTINGS)
DOMAIN_ROOT: Final[str] = SETTINGS.domain.root
PKI_ROOT_PATH: Final[str] = SETTINGS.vault.pki_root_path   # например: "pki"
PKI_INT_PATH:  Final[str] = SETTINGS.vault.pki_int_path    # например: "pki-int"
PKI_ROLE:      Final[str] = SETTINGS.vault.pki_role        # например: "terminal-leaf"

PKI_ROOT_TTL:     Final[str] = "87600h"
PKI_ROLE_MAX_TTL: Final[str] = "720h"

# Лифы — минимальный набор
LEAF_SVCS: Final[dict[str, dict[str, str]]] = {
    "consul":  {"common_name": f"consul.{DOMAIN_ROOT}",  "alt_names": "server.dc-1.consul,consul,localhost"},
    "vault":   {"common_name": f"vault.{DOMAIN_ROOT}",   "alt_names": "vault,localhost"},
    "traefik": {"common_name": f"traefik.{DOMAIN_ROOT}", "alt_names": "traefik,localhost"},
}

# Начальные KV/политики/approle (seed)
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

# ----------------------------- HTTP helpers -----------------------------
def _http_conn(https: bool) -> http.client.HTTPConnection | http.client.HTTPSConnection:
    host = SETTINGS.vault.host
    if not https:
        return http.client.HTTPConnection(host, SETTINGS.vault.http_port, timeout=6)
    ctx = ssl.create_default_context(cafile=str(CA_PEM)) if CA_PEM.exists() else ssl.create_default_context()
    return http.client.HTTPSConnection(host, SETTINGS.vault.https_port, timeout=6, context=ctx)


def _api(
    method: str,
    path: str,
    *,
    token: str | None = None,
    https: bool = False,
    body: dict | None = None
) -> http.client.HTTPResponse:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Vault-Token"] = token
    data = json.dumps(body).encode("utf-8") if body is not None else None
    conn = _http_conn(https)
    conn.request(method, path, body=data, headers=headers)
    return conn.getresponse()


def _health_ok(https: bool, timeout: float) -> bool:
    """Ожидание валидного статуса здоровья экспоненциальным backoff."""
    deadline = time.time() + max(1.0, timeout)
    delay = max(0.2, RETRY_BASE)
    while time.time() < deadline:
        try:
            resp = _api("GET", "/v1/sys/health", https=https)
            # 200/429/501/503 — допустимые стадии Vault
            if resp.status in (200, 429, 501, 503):
                return True
        except Exception:
            pass
        time.sleep(min(delay, RETRY_MAX))
        delay = min(delay * BACKOFF, RETRY_MAX)
    return False

# ----------------------------- Service -----------------------------
class VaultService(ContextMicroservice):
    async def initialize(self) -> None:
        first_run = not (CRT_VLT.exists() and CA_PEM.exists())

        # 1) first boot (HTTP): init/unseal + PKI/KV/Policies/AppRoles -> issue leaf certs
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

        # 3) Публикация публичных сертификатов и версии в Consul KV (после HTTPS старта)
        await self._publish_certs_to_kv()

    async def start(self) -> None:
        self._set_status(ServiceStatus.RUNNING, "vault.up")
        while not getattr(self, "_shutdown").is_set():
            await asyncio.sleep(5)

    # -- helpers --
    async def _start_vault(self, *, cfg: str, https: bool) -> bool:
        cmd = ["vault", "server", f"-config={cfg}"]
        self.log.info("evt=proc.start app=vault mode=%s cmd=%s", "https" if https else "http", " ".join(cmd))
        proc = subprocess.Popen(cmd)  # noqa: S603
        self.proc_attach(proc)

        host = SETTINGS.vault.host
        port = SETTINGS.vault.https_port if https else SETTINGS.vault.http_port
        if not await wait_port(host, port, timeout=INIT_TIMEOUT):
            self.log.error("evt=wait.port.timeout host=%s port=%s", host, port)
            return False

        loop = asyncio.get_event_loop()
        ok = await loop.run_in_executor(None, _health_ok, https, INIT_TIMEOUT)
        if not ok:
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

    # -- init/unseal/kv/policies/pki (HTTP) --
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
            CA_PEM.write_text(ca_pem, encoding="utf-8"); CA_PEM.chmod(0o644)
            self.log.info("evt=vault.pki.root.saved path=%s", CA_PEM)

            _api("POST", f"/v1/{PKI_ROOT_PATH}/config/urls", token=root_token, https=False, body={
                "issuing_certificates": f"http://{SETTINGS.vault.host}:{SETTINGS.vault.http_port}/v1/{PKI_ROOT_PATH}/ca",
                "crl_distribution_points": f"http://{SETTINGS.vault.host}:{SETTINGS.vault.http_port}/v1/{PKI_ROOT_PATH}/crl",
            }).read()

            # Создаём промежуточный CA и подписываем его рутом
            csr_res = _api("POST", f"/v1/{PKI_INT_PATH}/intermediate/generate/internal",
                           token=root_token, https=False, body={"common_name": f"intermediate.{DOMAIN_ROOT}"})
            if not (200 <= csr_res.status < 300):
                self.log.error("evt=vault.pki.int.csr.fail code=%s", csr_res.status); return
            csr = json.loads(csr_res.read().decode("utf-8") or "{}").get("data", {}).get("csr", "")

            sign_res = _api("POST", f"/v1/{PKI_ROOT_PATH}/root/sign-intermediate",
                            token=root_token, https=False, body={"csr": csr, "ttl": PKI_ROOT_TTL})
            if not (200 <= sign_res.status < 300):
                self.log.error("evt=vault.pki.int.sign.fail code=%s", sign_res.status); return
            cert = json.loads(sign_res.read().decode("utf-8") or "{}").get("data", {}).get("certificate", "")

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

        # leafs (FULLCHAIN = leaf + issuing_ca/ca_chain)
        for name, params in LEAF_SVCS.items():
            crt, key = CERTS_DIR / f"{name}.crt", CERTS_DIR / f"{name}.key"
            if crt.exists() and key.exists():
                self.log.info("evt=vault.pki.leaf.exists name=%s", name)
                continue

            self.log.info("evt=vault.pki.issue name=%s cn=%s", name, params.get("common_name"))
            res = _api("POST", f"/v1/{PKI_INT_PATH}/issue/{PKI_ROLE}",
                       token=root_token, https=False, body=params)
            if not (200 <= res.status < 300):
                self.log.error("evt=vault.pki.issue.fail name=%s code=%s", name, res.status)
                continue

            data = json.loads(res.read().decode("utf-8") or "{}").get("data", {})
            leaf = data.get("certificate", "")
            issuing_ca = data.get("issuing_ca", "")
            ca_chain = data.get("ca_chain") or []

            chain_tail = "\n".join([c for c in ca_chain if c.strip()]) if ca_chain else issuing_ca
            fullchain_pem = (leaf or "").strip()
            if chain_tail:
                if not fullchain_pem.endswith("\n"):
                    fullchain_pem += "\n"
                fullchain_pem += chain_tail.strip() + "\n"

            crt.write_text(fullchain_pem, encoding="utf-8"); crt.chmod(0o644)
            key.write_text(data.get("private_key", ""), encoding="utf-8");  key.chmod(0o600)
            self.log.info("evt=vault.pki.leaf.saved name=%s crt=%s key=%s", name, crt, key)

    # ----------------------------- Publish certs to KV -----------------------------

    async def _publish_certs_to_kv(self) -> None:
        """
        Публикует публичные PEM в Consul KV + маркеры готовности PKI/сертификатов.
        Использует Consul-токен для Vault из /consul/secrets/vault_consul_token.
        """
        token = None
        try:
            if VAULT_CONSUL_TOKEN_FILE.exists():
                token = VAULT_CONSUL_TOKEN_FILE.read_text(encoding="utf-8").strip() or None
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=vault.kv.token.read.fail err=%s", exc)

        if not token:
            self.log.warning("evt=vault.kv.publish.skip reason=no.consul.token")
            return

        try:
            kv_client = build_consul_kv_from_settings(SETTINGS, token=token)
            kv = KV(kv_client)
            if getattr(self, "deps", None) is not None:
                self.deps.kv = kv
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=vault.kv.attach.fail err=%s", exc)
            return

        # Маркеры готовности PKI
        try:
            kv.marker.vault.initialized.ensure()
            kv.marker.vault.pki_root_ready.ensure()
            kv.marker.vault.pki_int_ready.ensure()
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=vault.kv.marker.pki.fail err=%s", exc)

        # Публикация PEM и версии
        try:
            if CA_PEM.exists():
                kv.cert.publish_ca_pem(CA_PEM.read_text(encoding="utf-8"))

            svc_pems: Dict[str, str] = {}
            for svc in ("consul", "vault", "traefik"):
                p = CERTS_DIR / f"{svc}.crt"
                if p.exists():
                    svc_pems[svc] = p.read_text(encoding="utf-8")

            if svc_pems:
                # Версию считаем как sha256 всех PEM (детерминированно по имени сервиса)
                hasher = hashlib.sha256()
                for svc in sorted(svc_pems):
                    hasher.update(svc.encode("utf-8")); hasher.update(b"\0")
                    hasher.update(svc_pems[svc].encode("utf-8")); hasher.update(b"\0")
                version = hasher.hexdigest()

                if kv.cert.publish_bundle(svc_pems, version=version):
                    kv.marker.vault.pki_leaf_ready.ensure()
                    self.log.info("evt=vault.kv.certs.published version=%s svcs=%s", version, ",".join(sorted(svc_pems)))
                else:
                    self.log.warning("evt=vault.kv.certs.publish.false")
            else:
                self.log.warning("evt=vault.kv.certs.skip reason=no.svc_pems")
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=vault.kv.certs.publish.fail err=%s", exc)


async def main() -> None:
    await VaultService().serve()


if __name__ == "__main__":
    asyncio.run(main())
