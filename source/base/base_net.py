from __future__ import annotations
from typing import Tuple, Optional

from interfaces import INet, IConfigs
from core.net import Net


class BaseNet(INet):
    def __init__(self, cfg: IConfigs) -> None:
        self._n = Net(cfg)

    def build_url(self, scheme: str, host: str, port: int, path: str = "/") -> str:
        return self._n.build_url(scheme, host, port, path)

    def fqdn(self, host: str) -> str:
        return self._n.fqdn(host)

    def wait_port(self, host: str, port: int, *, timeout_ms: Optional[int] = None, interval_ms: Optional[int] = None) -> None:
        return self._n.wait_port(host, port, timeout_ms=timeout_ms, interval_ms=interval_ms)

    def probe_http(self, url: str, *, timeout_ms: Optional[int] = None) -> Tuple[int, bytes]:
        return self._n.probe_http(url, timeout_ms=timeout_ms)

    def probe_https(self, url: str, *, timeout_ms: Optional[int] = None) -> Tuple[int, bytes]:
        return self._n.probe_https(url, timeout_ms=timeout_ms)
