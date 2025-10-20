from __future__ import annotations
from dataclasses import dataclass
from interfaces import INet

@dataclass
class BaseNet:
    """Тонкий прокси над INet без deadline-параметров."""
    net: INet

    def build_url(self, scheme: str, host: str, port: int, path: str = "/") -> str:
        return self.net.build_url(scheme, host, port, path)

    def fqdn(self, host: str) -> str:
        return self.net.fqdn(host)

    def wait_port(self, host: str, port: int) -> None:
        return self.net.wait_port(host, port)

    def probe_http(self, url: str):
        return self.net.probe_http(url)

    def probe_https(self, url: str):
        return self.net.probe_https(url)
