from __future__ import annotations
import http.client
import json
import ssl
from dataclasses import dataclass, field
from typing import Optional, Tuple

from interfaces import IConfigs, ILogger

@dataclass
class ConsulRegistrar:
    cfg: IConfigs
    logger: ILogger
    _token_cache: Optional[str] = field(default=None, init=False)

    # --- low-level HTTP ---
    def _token(self) -> str:
        if self._token_cache is not None:
            return self._token_cache
        path = self.cfg.context.consul_token
        token = ""
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    token = f.read().strip()
            except Exception:
                token = ""
        self._token_cache = token
        return token

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        t = self._token()
        if t:
            h["X-Consul-Token"] = t
        return h

    def _conn(self) -> http.client.HTTPConnection:
        host = self.cfg.consul.host
        port = int(self.cfg.consul.https_port)
        context = ssl.create_default_context()
        return http.client.HTTPSConnection(host, port, context=context, timeout=5.0)

    def _do(self, method: str, path: str, body: Optional[dict]) -> Tuple[int, str]:
        conn = self._conn()
        try:
            data = None if body is None else json.dumps(body)
            conn.request(method, path, body=data, headers=self._headers())
            resp = conn.getresponse()
            payload = resp.read().decode("utf-8", "ignore")
            return resp.status, payload
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # --- high-level operations ---
    def register_service(self, service_def: dict) -> bool:
        status, _ = self._do("PUT", "/v1/agent/service/register", service_def)
        self.logger.info("consul.agent.service.register", status=status)
        return 200 <= status < 300

    def deregister_service(self, service_id: str) -> bool:
        status, _ = self._do("PUT", f"/v1/agent/service/deregister/{service_id}", None)
        self.logger.info("consul.agent.service.deregister", service_id=service_id, status=status)
        return 200 <= status < 300

    def pass_ttl(self, check_id: str) -> bool:
        status, _ = self._do("PUT", f"/v1/agent/check/pass/{check_id}", None)
        self.logger.info("consul.agent.check.pass", check_id=check_id, status=status)
        return 200 <= status < 300
