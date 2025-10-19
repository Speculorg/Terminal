from __future__ import annotations
import http.client
import json
from dataclasses import dataclass, field
from typing import Optional

from interfaces.i_configs import IConfigs
from interfaces.i_logger import ILogger

@dataclass
class ConsulRegistrar:
    cfg: IConfigs
    logger: ILogger
    _token_cache: Optional[str] = field(default=None, init=False)

    def _token(self) -> str:
        if self._token_cache is not None:
            return self._token_cache
        # Читаем токен из cfg.context.consul_token (уже путь или значение в фасаде Configs)
        token = (self.cfg.context.consul_token or "").strip()
        self._token_cache = token
        return token

    def _conn(self) -> http.client.HTTPConnection:
        host = self.cfg.consul.host
        port = int(self.cfg.consul.http_port)  # агент принимает локально по HTTP
        return http.client.HTTPConnection(host, port, timeout=max(1, int(self.cfg.kv.request_timeout_ms)/1000))

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        tok = self._token()
        if tok:
            h["X-Consul-Token"] = tok
        return h

    def _do(self, method: str, path: str, body: Optional[dict]) -> tuple[int, str]:
        conn = self._conn()
        data = None if body is None else json.dumps(body)
        conn.request(method, path, body=data, headers=self._headers())
        resp = conn.getresponse()
        payload = resp.read().decode("utf-8", "ignore")
        return resp.status, payload

    def register_service(self, service_def: dict) -> bool:
        status, payload = self._do("PUT", "/v1/agent/service/register", service_def)
        self.logger.info("consul.agent.service.register", status=status)
        return 200 <= status < 300

    def deregister_service(self, service_id: str) -> bool:
        status, payload = self._do("PUT", f"/v1/agent/service/deregister/{service_id}", None)
        self.logger.info("consul.agent.service.deregister", service_id=service_id, status=status)
        return 200 <= status < 300

    def pass_ttl(self, check_id: str) -> bool:
        status, payload = self._do("PUT", f"/v1/agent/check/pass/{check_id}", None)
        self.logger.info("consul.agent.check.pass", check_id=check_id, status=status)
        return 200 <= status < 300
