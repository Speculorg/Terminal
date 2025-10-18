from __future__ import annotations
from dataclasses import dataclass
from interfaces import INet

@dataclass
class BaseNet:
    """Тонкий прокси над INet."""
    net: INet

    def build_url(self, scheme: str, host: str, port: int, path: str = "/", *, deadline_ms: int) -> str:
        return self.net.build_url(scheme, host, port, path, deadline_ms=deadline_ms)

    def fqdn(self, host: str, *, deadline_ms: int) -> str:
        return self.net.fqdn(host, deadline_ms=deadline_ms)

    def wait_port(self, host: str, port: int, *, deadline_ms: int) -> None:
        return self.net.wait_port(host, port, deadline_ms=deadline_ms)

    def probe_http(self, url: str, *, deadline_ms: int):
        return self.net.probe_http(url, deadline_ms=deadline_ms)

    def probe_https(self, url: str, *, deadline_ms: int):
        return self.net.probe_https(url, deadline_ms=deadline_ms)
