from __future__ import annotations
import http.client, ssl, urllib.parse
from typing import Tuple, Optional
from interfaces import IConfigs
from .port import wait_port as _wait_port

class Net:
    """Сетевые операции. Все таймауты берём из cfg при отсутствии явных значений."""
    def __init__(self, cfg: IConfigs) -> None:
        self._cfg = cfg

    # Общее
    def build_url(self, scheme: str, host: str, port: int, path: str = "/") -> str:
        path = path or "/"
        if not path.startswith("/"):
            path = "/" + path
        return f"{scheme}://{host}:{int(port)}{path}"

    def fqdn(self, host: str) -> str:
        return host  # FQDN как есть; логика DNS вне скоупа

    # Порт
    def wait_port(self, host: str, port: int, *, timeout_ms: Optional[int] = None, interval_ms: Optional[int] = None) -> None:
        tmo = int(timeout_ms if timeout_ms is not None else self._cfg.fsm.state_initializing_timeout_ms)
        interval = int(interval_ms if interval_ms is not None else 200)
        ok = _wait_port(host, int(port), timeout_ms=tmo, interval_ms=interval)
        if not ok:
            raise TimeoutError(f"port {host}:{port} not ready within {tmo}ms")

    # HTTP(S) пробы для будущих use-cases
    def probe_http(self, url: str, *, timeout_ms: Optional[int] = None) -> Tuple[int, bytes]:
        tmo = (timeout_ms if timeout_ms is not None else self._cfg.fsm.state_running_tick_timeout_ms) / 1000.0
        u = urllib.parse.urlparse(url)
        conn = http.client.HTTPConnection(u.hostname, u.port, timeout=tmo)
        conn.request("GET", u.path or "/")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body

    def probe_https(self, url: str, *, timeout_ms: Optional[int] = None) -> Tuple[int, bytes]:
        tmo = (timeout_ms if timeout_ms is not None else self._cfg.fsm.state_running_tick_timeout_ms) / 1000.0
        u = urllib.parse.urlparse(url)
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(u.hostname, u.port, timeout=tmo, context=ctx)
        conn.request("GET", u.path or "/")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body
