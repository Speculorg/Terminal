# source/services/consul/app/main.py

from __future__ import annotations
import asyncio
import json
import ssl
import subprocess
import time
import http.client
from pathlib import Path
from typing import Dict, Optional

from core.base.service import ContextMicroservice
from core.runtime.status import ServiceStatus
from core.settings.settings import SETTINGS
from core.net.port import wait_port
from core.logging import get_logger
from core.kv import KV, build_consul_kv_from_settings

log = get_logger("consul.app")


# ----------------------------- Paths & Const -----------------------------
CERTS_DIR = Path(SETTINGS.paths.tls_certs_dir)
CONSUL_CERT = CERTS_DIR / "consul.crt"
CONSUL_KEY  = CERTS_DIR / "consul.key"
CA_CERT     = CERTS_DIR / "ca.crt"

CFG_HTTP  = "/consul/config/consul_http.hcl"
CFG_HTTPS = "/consul/config/consul_https.hcl"

SECRETS_DIR       = Path("/consul/secrets")
SECRETS_DIR.mkdir(parents=True, exist_ok=True)

ROOT_TOKEN_JSON   = SECRETS_DIR / "root_consul_token.json"
AGENT_TOKEN_FILE  = SECRETS_DIR / "agent_consul_token"
VAULT_TOKEN_FILE  = SECRETS_DIR / "vault_consul_token"
TRAEFIK_TOKEN_FILE= SECRETS_DIR / "traefik_consul_token"

# Тайминги из SETTINGS
INIT_TIMEOUT = float(SETTINGS.timeouts.init_timeout_s)
RETRY_BASE   = float(SETTINGS.timeouts.retry_interval_s)
RETRY_MAX    = float(SETTINGS.timeouts.max_retry_interval_s)
BACKOFF      = float(SETTINGS.timeouts.backoff_factor)

# ----------------------------- ACL policies -----------------------------
POLICIES: Dict[str, Dict] = {
    "agent": {
        "name": "agent-policy",
        "rules": """
            agent            "" { policy = "write" }
            node_prefix      "" { policy = "write" }
            service_prefix   "" { policy = "read"  }
            session_prefix   "" { policy = "write" }
        """,
        "token_file": AGENT_TOKEN_FILE,
        "desc": "token-for-consul-agent",
    },
    "vault": {
        "name": "vault-policy",
        "rules": """
            # Vault Consul storage (обязательно)
            key_prefix "vault/"                   { policy = "write" }
            session_prefix ""                     { policy = "write" }

            # Vault публикует сертификаты и статус ротации
            key_prefix "certs/"                   { policy = "write" }
            key_prefix "marker/vault/"            { policy = "write" }

            # Vault читает глобальные конфиги/статусы
            key_prefix "config/global/"           { policy = "read"  }
            key_prefix "status/"                  { policy = "read"  }

            # Минимально необходимое для сервис-дискавери
            service "vault"                       { policy = "write" }
            node_prefix ""                        { policy = "read"  }
            query_prefix ""                       { policy = "read"  }
        """,
        "token_file": VAULT_TOKEN_FILE,
        "desc": "token-for-vault",
    },
    "traefik": {
        "name": "traefik-policy",
        "rules": """
            # Traefik читает сертификаты и маркер их статуса/версии
            key_prefix "certs/"                    { policy = "read"  }
            key_prefix "marker/vault/certs_status" { policy = "read"  }
            key_prefix "config/global/"            { policy = "read"  }

            # Чтение каталога и нод для роутинга/health
            node_prefix ""                         { policy = "read"  }
            query_prefix ""                        { policy = "read"  }
            service_prefix ""                      { policy = "read"  }
        """,
        "token_file": TRAEFIK_TOKEN_FILE,
        "desc": "token-for-traefik",
    },
}

# ----------------------------- HTTP helpers -----------------------------
def _http_conn(https: bool) -> http.client.HTTPConnection | http.client.HTTPSConnection:
    host = SETTINGS.consul.host
    if not https:
        return http.client.HTTPConnection(host, SETTINGS.consul.http_port, timeout=6)
    ctx = ssl.create_default_context(cafile=str(CA_CERT)) if CA_CERT.exists() else ssl.create_default_context()
    return http.client.HTTPSConnection(host, SETTINGS.consul.https_port, timeout=6, context=ctx)


def _api(
    method: str,
    path: str,
    *,
    token: str | None = None,
    https: bool = False,
    body: Optional[dict] = None
) -> http.client.HTTPResponse:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Consul-Token"] = token
    body_bytes = json.dumps(body).encode("utf-8") if body is not None else None
    conn = _http_conn(https)
    conn.request(method, path, body=body_bytes, headers=headers)
    return conn.getresponse()


def _leader_ready(https: bool, timeout: float) -> bool:
    """Ожидание лидера с экспоненциальным backoff до timeout."""
    deadline = time.time() + max(1.0, timeout)
    delay = max(0.2, RETRY_BASE)
    while time.time() < deadline:
        try:
            resp = _api("GET", "/v1/status/leader", https=https)
            data = resp.read().decode("utf-8", "ignore").strip()
            if 200 <= resp.status < 300 and data and data != '""':
                return True
        except Exception:
            pass
        time.sleep(min(delay, RETRY_MAX))
        delay = min(delay * BACKOFF, RETRY_MAX)
    return False

# ----------------------------- Service -----------------------------
class ConsulService(ContextMicroservice):
    async def initialize(self) -> None:
        first_run = not AGENT_TOKEN_FILE.exists()

        # 1) bootstrap run (HTTP) if first time
        if first_run:
            self._set_status(ServiceStatus.BOOTSTRAPPING, "consul.http.start")
            if not await self._start_consul(cfg=CFG_HTTP, https=False):
                return
            await self._ensure_init_http()
            await asyncio.sleep(2.0)
            await self._stop_child()

        # 2) normal run (TLS if certs present)
        use_tls = CONSUL_CERT.exists() and CONSUL_KEY.exists() and CA_CERT.exists()
        self.svc_set_tls_active(use_tls)
        cfg = CFG_HTTPS if use_tls else CFG_HTTP
        self._set_status(ServiceStatus.INITIALIZING, f"consul.start cfg={'https' if use_tls else 'http'}")
        if not await self._start_consul(cfg=cfg, https=use_tls):
            return

        # 3) set agent token (once agent fully up)
        await self._apply_agent_token()

        # 4) attach KV and publish markers (idempotent)
        await self._late_attach_kv_and_publish_markers(use_tls)

    async def start(self) -> None:
        self._set_status(ServiceStatus.RUNNING, "consul.up")
        while not getattr(self, "_shutdown").is_set():
            await asyncio.sleep(5)

    # -- helpers --
    async def _start_consul(self, *, cfg: str, https: bool) -> bool:
        cmd = ["consul", "agent", f"-config-file={cfg}"]
        self.log.info("evt=proc.start app=consul mode=%s cmd=%s", "https" if https else "http", " ".join(cmd))
        proc = subprocess.Popen(cmd)  # noqa: S603
        self.proc_attach(proc)

        # ждём порта + лидера
        host = SETTINGS.consul.host
        port = SETTINGS.consul.https_port if https else SETTINGS.consul.http_port
        if not await wait_port(host, port, timeout=INIT_TIMEOUT):
            self.log.error("evt=wait.port.timeout host=%s port=%s", host, port)
            return False

        loop = asyncio.get_event_loop()
        ok = await loop.run_in_executor(None, _leader_ready, https, INIT_TIMEOUT)
        if not ok:
            self.log.error("evt=wait.leader.timeout mode=%s", "https" if https else "http")
            return False

        self.log.info("evt=leader.ready mode=%s", "https" if https else "http")
        return True

    async def _stop_child(self) -> None:
        if getattr(self, "_child", None) and self._child.poll() is None:
            self.log.info("evt=proc.stop app=consul")
            try:
                self._child.terminate()
                await asyncio.get_event_loop().run_in_executor(None, self._child.wait, 10)
            except Exception:
                try:
                    self._child.kill()
                except Exception:
                    pass

    async def _ensure_init_http(self) -> None:
        """ACL bootstrap + policies + tokens (HTTP mode). Идемпотентно."""
        loop = asyncio.get_event_loop()
        ok = await loop.run_in_executor(None, _leader_ready, False, INIT_TIMEOUT)
        if not ok:
            self.log.error("evt=init.abort reason=leader.not.ready")
            return

        root_token = None
        if ROOT_TOKEN_JSON.exists():
            try:
                root_token = json.loads(ROOT_TOKEN_JSON.read_text(encoding="utf-8")).get("SecretID", "")
            except Exception:
                root_token = None

        if not root_token:
            # Bootstrap ACL только если нет management токена
            resp = _api("PUT", "/v1/acl/bootstrap", https=False)
            if resp.status != 200:
                self.log.error("evt=acl.bootstrap.fail code=%s", resp.status)
                return
            body = resp.read().decode("utf-8")
            ROOT_TOKEN_JSON.write_text(body, encoding="utf-8")
            root_token = json.loads(body).get("SecretID", "")
            self.log.info("evt=acl.bootstrap.ok token_saved=%s", ROOT_TOKEN_JSON)

        # Upsert policies (всегда PUT)
        for name, cfg in POLICIES.items():
            _api("PUT", "/v1/acl/policy", token=root_token, https=False, body={
                "Name": cfg["name"],
                "Description": f"auto {name}",
                "Rules": cfg["rules"],
            }).read()
            self.log.info("evt=policy.upsert name=%s", cfg["name"])

            # Создаём токен если не сохранён
            token_path = Path(cfg["token_file"])
            if not token_path.exists():
                t_resp = _api("PUT", "/v1/acl/token", token=root_token, https=False, body={
                    "Description": cfg["desc"],
                    "Policies": [{"Name": cfg["name"]}],
                })
                if 200 <= t_resp.status < 300:
                    secret = json.loads(t_resp.read().decode("utf-8") or "{}").get("SecretID", "")
                    token_path.write_text(secret, encoding="utf-8")
                    self.log.info("evt=token.saved path=%s", token_path)
                else:
                    self.log.error("evt=token.create.fail name=%s code=%s", cfg["name"], t_resp.status)
            else:
                self.log.info("evt=token.exists path=%s", token_path)

        self.log.info("evt=init.ok")

    async def _apply_agent_token(self) -> None:
        if not (AGENT_TOKEN_FILE.exists() and ROOT_TOKEN_JSON.exists()):
            self.log.warning("evt=agent.token.skip reason=files.missing")
            return
        try:
            mgmt_token = json.loads(ROOT_TOKEN_JSON.read_text(encoding="utf-8")).get("SecretID", "")
            agent_token = AGENT_TOKEN_FILE.read_text(encoding="utf-8").strip()
            cmd = ["consul", "acl", "set-agent-token", "-token", mgmt_token, "agent", agent_token]
            self.log.info("evt=consul.set-agent-token")
            res = await asyncio.get_event_loop().run_in_executor(
                None, lambda: subprocess.run(cmd, capture_output=True, text=True)
            )
            if res.returncode == 0:
                self.log.info("evt=agent.token.applied")
            else:
                self.log.error("evt=agent.token.fail code=%s stderr=%s", res.returncode, res.stderr.strip() or "<empty>")
        except Exception as exc:  # noqa: BLE001
            self.log.error("evt=agent.token.error err=%s", exc)

    async def _late_attach_kv_and_publish_markers(self, use_tls: bool) -> None:
        """
        После того как Consul встал и токены созданы - прикрепляем KV и публикуем маркеры.
        """
        try:
            token = None
            if ROOT_TOKEN_JSON.exists():
                token = json.loads(ROOT_TOKEN_JSON.read_text(encoding="utf-8")).get("SecretID", "") or None
            if not token:
                log.warning("evt=kv.attach.skip reason=no.token")
                return

            kv_client = build_consul_kv_from_settings(SETTINGS, token=token)
            kv = KV(kv_client)
            if getattr(self, "deps", None) is not None:
                self.deps.kv = kv

            # 1) initialized
            kv.marker.svc("consul").initialized.ensure()

            # 2) mTLS готов (если подняли TLS)
            if use_tls:
                kv.marker.svc("consul").mtls_ready.ensure()

            # 3) минимальный маркер синхронизации каталога
            kv.marker.consul.catalog_synchronized.ensure()

        except Exception as exc:  # noqa: BLE001
            log.warning("evt=kv.attach_or_publish.fail err=%s", exc)


async def main() -> None:
    await ConsulService().serve()


if __name__ == "__main__":
    asyncio.run(main())
