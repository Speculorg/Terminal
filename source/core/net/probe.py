from __future__ import annotations
from typing import Tuple
from .facade import Net

def tcp(host: str, port: int, *, cfg=None, timeout_ms: int | None = None) -> bool:
    n = Net(cfg) if cfg is not None else Net(type("C", (), {})())
    return n.tcp_ping(host, port, timeout_ms=timeout_ms)

def tls(host: str, port: int, *, cfg=None, timeout_ms: int | None = None) -> bool:
    n = Net(cfg) if cfg is not None else Net(type("C", (), {})())
    return n.tls_handshake(host, port, timeout_ms=timeout_ms)

def http_get(url: str, *, cfg=None, timeout_ms: int | None = None) -> Tuple[int,int]:
    n = Net(cfg) if cfg is not None else Net(type("C", (), {})())
    return n.http_get(url, timeout_ms=timeout_ms)
