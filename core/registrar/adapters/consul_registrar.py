from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

import requests

from core._base import BaseRegistrar
from core._interfaces import IConfigs


def _token_from_cfg(cfg: IConfigs) -> Optional[str]:
    # 1) cfg.model.context.consul_token (preferred)
    try:
        model = getattr(cfg, "model", None)
        if model and getattr(model, "context", None) and getattr(model.context, "consul_token", None):
            return str(model.context.consul_token)
    except Exception:
        pass

    # 2) fallback to env key
    try:
        v = cfg.get("CONSUL_HTTP_TOKEN", None)
        return str(v) if v else None
    except Exception:
        return None


@dataclass(frozen=True, slots=True)
class ConsulConn:
    scheme: str
    host: str
    port: int
    token: Optional[str]
    tls_verify: Optional[str] = None  # ca file path
    tls_cert: Optional[Tuple[str, str]] = None  # (cert_file, key_file)

    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"


class ConsulRegistrar(BaseRegistrar):
    """
    Consul registrar via Agent HTTP API.

    TERM-1:
    - после bootstrap ожидается HTTPS + mTLS
    - все ошибки requests нормализуются в RuntimeError для RETRY в политиках
    """

    def __init__(self, *, conn: ConsulConn, timeout_ms: int = 3000) -> None:
        self._conn = conn
        self._timeout_s = max(0.001, int(timeout_ms)) / 1000.0

    @classmethod
    def from_configs(cls, *, cfg: IConfigs) -> "ConsulRegistrar":
        # По умолчанию: HTTPS (TERM-1 secure). HTTP допустим только если явно задан CONSUL_SCHEME=http.
        scheme = str(cfg.get("CONSUL_SCHEME", "https")).strip() or "https"
        host = str(cfg.get("CONSUL_HOST", "consul"))
        if scheme == "https":
            port = int(cfg.get("CONSUL_HTTPS_PORT", 8501) or 8501)
        else:
            port = int(cfg.get("CONSUL_HTTP_PORT", 8500) or 8500)

        token = _token_from_cfg(cfg)
        timeout_ms = int(cfg.get("CONSUL_REQUEST_TIMEOUT_MS", 3000) or 3000)

        tls_verify: Optional[str] = None
        tls_cert: Optional[Tuple[str, str]] = None

        if scheme == "https":
            certs_dir = Path(str(cfg.get("FS_CERTS_DIR", "/fs/terminal/certs")))
            ca_file = certs_dir / "ca.crt"

            # сервис регистрирует себя -> используем leaf cert сервиса
            svc_name = getattr(cfg, "service_name", None) or str(cfg.get("SERVICE_NAME", "unknown"))
            cert_file = certs_dir / f"{svc_name}.crt"
            key_file = certs_dir / f"{svc_name}.key"

            tls_verify = str(ca_file)
            tls_cert = (str(cert_file), str(key_file))

        conn = ConsulConn(
            scheme=scheme,
            host=host,
            port=port,
            token=token,
            tls_verify=tls_verify,
            tls_cert=tls_cert,
        )
        return cls(conn=conn, timeout_ms=timeout_ms)

    # --- IRegistrar ---

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
        """
        PUT /v1/agent/service/register

        TTL check:
        - если ttl_seconds задан, создаём check вида {"TTL":"15s"}.
        - check_id обязателен для heartbeat; если не задан — генерируем детерминированный.
        """
        sid = self._service_id(service, check_id)
        payload: dict[str, object] = {
            "ID": sid,
            "Name": service,
            "Address": address,
            "Port": int(port),
            "Tags": list(tags or ()),
        }

        if ttl_seconds is not None:
            cid = check_id or self._default_check_id(service)
            payload["Check"] = {
                "CheckID": cid,
                "Name": f"{service}:ttl",
                "TTL": f"{int(ttl_seconds)}s",
                "DeregisterCriticalServiceAfter": "0s",
            }

        self._put_json("/v1/agent/service/register", payload)

    def heartbeat(self, *, check_id: str) -> None:
        """
        PUT /v1/agent/check/pass/<check_id>
        """
        cid = str(check_id)
        self._put(f"/v1/agent/check/pass/{cid}")

    def deregister(self, *, service: str, check_id: str | None = None) -> None:
        """
        PUT /v1/agent/service/deregister/<service_id>
        """
        sid = self._service_id(service, check_id)
        self._put(f"/v1/agent/service/deregister/{sid}")

    # --- internals ---

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._conn.token:
            h["X-Consul-Token"] = self._conn.token
        return h

    def _url(self, path: str) -> str:
        return self._conn.base_url() + path

    def _req_kwargs(self) -> dict:
        kw = {"timeout": self._timeout_s}
        if self._conn.tls_verify:
            kw["verify"] = self._conn.tls_verify
        if self._conn.tls_cert:
            kw["cert"] = self._conn.tls_cert
        return kw

    def _put(self, path: str) -> None:
        try:
            r = requests.put(self._url(path), headers=self._headers(), **self._req_kwargs())
            if r.status_code >= 300:
                raise RuntimeError(f"consul_http_error:{r.status_code}:{(r.text or '')[:256]}")
        except requests.RequestException as e:
            raise RuntimeError(f"consul_request_error:{type(e).__name__}") from e

    def _put_json(self, path: str, payload: dict[str, object]) -> None:
        try:
            data = json.dumps(payload, ensure_ascii=False)
            r = requests.put(self._url(path), data=data, headers=self._headers(), **self._req_kwargs())
            if r.status_code >= 300:
                raise RuntimeError(f"consul_http_error:{r.status_code}:{(r.text or '')[:256]}")
        except requests.RequestException as e:
            raise RuntimeError(f"consul_request_error:{type(e).__name__}") from e

    @staticmethod
    def _default_check_id(service: str) -> str:
        return f"service:{service}:ttl"

    @staticmethod
    def _service_id(service: str, check_id: str | None) -> str:
        if check_id:
            return f"{service}:{check_id}"
        return service
