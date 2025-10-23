from __future__ import annotations
import json
import http.client
import ssl
from typing import Optional, Dict

from interfaces import IConfigs, ILogger

class ConsulRegistrar:
    """Минимальный HTTP клиент для регистрации service+TTL в Consul Agent API."""
    def __init__(self, cfg: IConfigs, logger: ILogger) -> None:
        self.cfg = cfg
        self.logger = logger
        self._token_cache: Optional[str] = cfg.context.consul_token

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        t = self._token_cache
        if t:
            h["X-Consul-Token"] = t
        return h

    def _conn(self) -> http.client.HTTPConnection:
        # Используем HTTP по умолчанию для agent (127.0.0.1 или consul), HTTPS можно добавить позже
        return http.client.HTTPConnection(self.cfg.consul.host, self.cfg.consul.http_port, timeout=5)

    def register_service(self, svc_id: str, name: str, port: int, tags: list[str], ttl_sec: int) -> bool:
        body = {
            "ID": svc_id,
            "Name": name,
            "Port": port,
            "Tags": tags,
            "Check": {"TTL": f"{int(ttl_sec)}s"}
        }
        conn = self._conn()
        try:
            conn.request("PUT", "/v1/agent/service/register", body=json.dumps(body), headers=self._headers())
            resp = conn.getresponse()
            resp.read()
            return 200 <= resp.status < 300
        finally:
            conn.close()

    def deregister_service(self, svc_id: str) -> bool:
        conn = self._conn()
        try:
            conn.request("PUT", f"/v1/agent/service/deregister/{svc_id}", headers=self._headers())
            resp = conn.getresponse()
            resp.read()
            return 200 <= resp.status < 300
        finally:
            conn.close()

    def pass_ttl(self, check_id: str) -> bool:
        conn = self._conn()
        try:
            conn.request("PUT", f"/v1/agent/check/pass/{check_id}", headers=self._headers())
            resp = conn.getresponse()
            resp.read()
            return 200 <= resp.status < 300
        finally:
            conn.close()
