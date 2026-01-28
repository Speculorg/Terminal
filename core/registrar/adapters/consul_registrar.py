from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

import requests

from core._interfaces import IConfigs, ITLS
from core.tls.paths import TlsPaths


@dataclass(frozen=True, slots=True)
class ConsulEndpoint:
    scheme: str
    host: str
    port: int
    token: str
    token_file: Optional[str] = None
    # TLS (for https)
    ca_file: Optional[str] = None
    client_cert: Optional[Tuple[str, str]] = None
    # registrar behavior
    deregister_critical_after_sec: int = 45


class ConsulRegistrar:
    """
    Consul Registrar (TERM-1).

    Использует:
    - /v1/agent/service/register (agent API)
    - /v1/agent/check/pass (TTL heartbeat)

    Принцип для TERM-1 автосходимости:
    - Токен может быть недоступен на старте контейнера (создаётся bootstrap'ом Consul).
      В этом случае adapter НЕ падает при сборке deps, а отдаёт retryable RuntimeError
      во время операций register/heartbeat/deregister.
    - После bootstrap работает по HTTPS+mTLS (CA + leaf сертификат текущего сервиса).
    """

    def __init__(self, *, ep: ConsulEndpoint) -> None:
        self._ep = ep

    @classmethod
    def from_configs(cls, *, cfg: IConfigs, tls: ITLS | None = None) -> "ConsulRegistrar":
        # endpoint base
        scheme = str(cfg.get("CONSUL_SCHEME", "https")).strip() or "https"
        host = str(cfg.get("CONSUL_HOST", "consul")).strip() or "consul"
        port = int(cfg.get("CONSUL_HTTPS_PORT" if scheme == "https" else "CONSUL_HTTP_PORT", 8501 if scheme == "https" else 8500))

        # token: может появиться позже (bootstrap), поэтому НЕ требуем его здесь.
        token = ""
        token_file = None

        # 1) из context (если уже заполнен где-то выше)
        try:
            model = getattr(cfg, "_model", None)
            ctx = getattr(model, "context", None)
            token = str(getattr(ctx, "consul_token", "") or "").strip()
        except Exception:
            token = ""

        # 2) из env *_TOKEN_FILE (наиболее надёжно в TERM-1)
        for key in ("CONSUL_HTTP_TOKEN_FILE", "CONTEXT_CONSUL_HTTP_TOKEN_FILE"):
            try:
                p = str(cfg.get(key, "") or "").strip()
                if p:
                    token_file = p
                    break
            except Exception:
                continue

        # registrar tuning
        dereg_after = int(cfg.get("REGISTRAR_DEREGISTER_CRITICAL_SERVICE_AFTER_SEC", 45) or 45)

        # TLS
        ca_file = None
        client_cert = None
        if scheme == "https":
            certs_dir = Path(str(cfg.get("FS_CERTS_DIR", "/fs/terminal/certs")))
            svc_name = str(getattr(cfg, "service_name", "unknown"))
            p = TlsPaths(certs_dir=certs_dir)
            ca_file = str(p.ca())
            client_cert = (str(p.cert(svc_name)), str(p.key(svc_name)))

        return cls(
            ep=ConsulEndpoint(
                scheme=scheme,
                host=host,
                port=int(port),
                token=token,
                token_file=token_file,
                ca_file=ca_file,
                client_cert=client_cert,
                deregister_critical_after_sec=int(dereg_after),
            )
        )

    def _base(self) -> str:
        return f"{self._ep.scheme}://{self._ep.host}:{self._ep.port}"

    def _load_token_from_file(self) -> str:
        p = self._ep.token_file
        if not p:
            return ""
        try:
            fp = Path(p)
            if not fp.exists():
                return ""
            v = fp.read_text(encoding="utf-8").strip()
            return v
        except Exception:
            return ""

    def _token(self) -> str:
        # in-memory wins, then file
        if self._ep.token:
            return self._ep.token
        return self._load_token_from_file()

    def _headers(self) -> dict[str, str]:
        token = self._token()
        if not token:
            # для политики RegistrarPolicy это будет RETRY, а не crash сервиса
            raise RuntimeError("consul_registrar_token_not_ready")
        return {"X-Consul-Token": token}

    def _verify(self) -> Any:
        return self._ep.ca_file or True

    def _cert(self) -> Any:
        return self._ep.client_cert

    def register(
        self,
        *,
        service: str,
        address: str,
        port: int,
        tags: Sequence[str] = (),
        check_id: str | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        if not ttl_seconds:
            # TERM-1 всегда TTL, но не запрещаем вызывать без TTL
            ttl_seconds = 15

        dereg_after = int(self._ep.deregister_critical_after_sec)
        payload = {
            "ID": service,
            "Name": service,
            "Address": address,
            "Port": int(port),
            "Tags": list(tags),
            "Check": {
                "CheckID": check_id or f"service:{service}:ttl",
                "Name": f"{service} ttl",
                "TTL": f"{int(ttl_seconds)}s",
                "DeregisterCriticalServiceAfter": f"{dereg_after}s",
            },
        }

        r = requests.put(
            f"{self._base()}/v1/agent/service/register",
            headers=self._headers(),
            json=payload,
            timeout=5.0,
            verify=self._verify(),
            cert=self._cert(),
        )
        if r.status_code != 200:
            raise RuntimeError(f"consul_register_failed:{r.status_code}:{(r.text or '')[:256]}")

    def heartbeat(self, *, check_id: str) -> None:
        r = requests.put(
            f"{self._base()}/v1/agent/check/pass/{check_id}",
            headers=self._headers(),
            timeout=5.0,
            verify=self._verify(),
            cert=self._cert(),
        )
        if r.status_code != 200:
            raise RuntimeError(f"consul_check_pass_failed:{r.status_code}:{(r.text or '')[:256]}")

    def deregister(self, *, service: str, check_id: str | None = None) -> None:
        # сначала дерегистрируем сервис
        r = requests.put(
            f"{self._base()}/v1/agent/service/deregister/{service}",
            headers=self._headers(),
            timeout=5.0,
            verify=self._verify(),
            cert=self._cert(),
        )
        if r.status_code != 200:
            raise RuntimeError(f"consul_deregister_failed:{r.status_code}:{(r.text or '')[:256]}")
