# source\core\infra\registrars\consul.py


from __future__ import annotations
import http.client, json
from typing import Sequence

from core.settings.settings import SETTINGS
from core.infra.secrets import read_token_from_envfile
from core.net.port import wait_port
from core.infra.registrars.base import Registrar


class ConsulRegistrar(Registrar):
    """Простая регистрация сервиса в Consul по HTTP (до TLS-перехода)."""

    def __init__(self, service_id: str, name: str, port: int, tags: Sequence[str] = ()):
        self.service_id = service_id
        self.name = name
        self.port = int(port)
        self.tags = list(tags)

    async def register(self) -> None:
        ok = await wait_port(SETTINGS.consul.host, SETTINGS.consul.http_port, timeout=20.0)
        if not ok:
            return
        headers = {"Content-Type": "application/json"}
        token = read_token_from_envfile("CONSUL_HTTP_TOKEN_FILE")
        if token:
            headers["X-Consul-Token"] = token
        payload = {
            "ID": self.service_id,
            "Name": self.name,
            "Port": self.port,
            "Tags": self.tags,
            "Meta": {"domain": SETTINGS.domain.root},
            "EnableTagOverride": False,
        }
        conn = http.client.HTTPConnection(SETTINGS.consul.host, SETTINGS.consul.http_port, timeout=5)
        try:
            conn.request("PUT", "/v1/agent/service/register", body=json.dumps(payload), headers=headers)
            conn.getresponse()  # ignore body; rely on logs/health
        finally:
            try:
                conn.close()
            except Exception:
                pass

    async def deregister(self) -> None:
        headers = {"Content-Type": "application/json"}
        token = read_token_from_envfile("CONSUL_HTTP_TOKEN_FILE")
        if token:
            headers["X-Consul-Token"] = token
        conn = http.client.HTTPConnection(SETTINGS.consul.host, SETTINGS.consul.http_port, timeout=5)
        try:
            conn.request("PUT", f"/v1/agent/service/deregister/{self.service_id}", headers=headers)
            conn.getresponse()
        finally:
            try:
                conn.close()
            except Exception:
                pass
