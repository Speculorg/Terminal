from __future__ import annotations
import socket, time, http.client, ssl, urllib.parse
from typing import Tuple, Optional
from interfaces import INet, IConfigs

class BaseNet(INet):
    """Базовый каркас сетевых операций (stdlib)."""
    def __init__(self, cfg: IConfigs) -> None:
        self._cfg = cfg

    def build_url(self, scheme: str, host: str, port: int, path: str = "/") -> str:
        path = path or "/"
        if not path.startswith("/"):
            path = "/" + path
        return f"{scheme}://{host}:{int(port)}{path}"

    def fqdn(self, host: str) -> str:
        return host

    def wait_port(self, host: str, port: int, *, timeout_ms: Optional[int] = None, interval_ms: Optional[int] = None) -> None:
        tmo = int(timeout_ms if timeout_ms is not None else self._cfg.fsm.state_initializing_timeout_ms)
        interval = int(interval_ms if interval_ms is not None else 200)
        deadline = time.time() + max(0.0, tmo/1000.0)
        last_err: Exception | None = None
        while time.time() < deadline:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(max(0.05, interval/1000.0))
            try:
                s.connect((host, int(port)))
                s.close()
                return
            except Exception as e:
                last_err = e
                time.sleep(interval/1000.0)
            finally:
                try: s.close()
                except Exception: pass
        raise TimeoutError(f"port {host}:{port} not ready within {tmo}ms: {last_err}")

    def probe_http(self, url: str, *, timeout_ms: Optional[int] = None) -> Tuple[int, bytes]:
        tmo = int(timeout_ms if timeout_ms is not None else self._cfg.fsm.state_initializing_timeout_ms)
        pr = urllib.parse.urlparse(url)
        conn = http.client.HTTPConnection(pr.hostname, pr.port or 80, timeout=max(0.05, tmo/1000.0))
        conn.request("GET", pr.path or "/")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body

    def probe_https(self, url: str, *, timeout_ms: Optional[int] = None) -> Tuple[int, bytes]:
        tmo = int(timeout_ms if timeout_ms is not None else self._cfg.fsm.state_initializing_timeout_ms)
        pr = urllib.parse.urlparse(url)
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(pr.hostname, pr.port or 443, timeout=max(0.05, tmo/1000.0), context=ctx)
        conn.request("GET", pr.path or "/")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body
