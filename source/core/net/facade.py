from __future__ import annotations
import socket
import ssl
import time
import http.client
import urllib.parse
from typing import Tuple

from interfaces import IConfigs

class Net:
    """Сетевые утилиты и пробы.
    Таймауты берутся из cfg.fsm.*. Параметры вызова без deadline_ms.
    """
    def __init__(self, cfg: IConfigs) -> None:
        self._cfg = cfg
        # Базовые окна
        self._wait_port_timeout_ms = int(getattr(cfg.fsm, "state_securing_timeout_ms", 10000))
        self._http_timeout_ms = int(getattr(cfg.kv, "request_timeout_ms", 5000))

    # ---- API ----
    def build_url(self, scheme: str, host: str, port: int, path: str = "/") -> str:
        path = path or "/"
        if not path.startswith("/"):
            path = "/" + path
        return f"{scheme}://{host}:{port}{path}"

    def fqdn(self, host: str) -> str:
        try:
            return socket.getfqdn(host)
        except Exception:
            return host

    def wait_port(self, host: str, port: int) -> None:
        deadline = time.time() + (self._wait_port_timeout_ms / 1000.0)
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                with socket.create_connection((host, port), timeout=1.0):
                    return
            except Exception as e:
                last_err = e
                time.sleep(0.1)
        if last_err:
            raise last_err
        raise TimeoutError(f"port not ready: {host}:{port}")

    def probe_http(self, url: str) -> Tuple[int, bytes]:
        parsed = urllib.parse.urlparse(url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=self._http_timeout_ms/1000.0)
        try:
            conn.request("GET", parsed.path or "/")
            resp = conn.getresponse()
            body = resp.read()
            return resp.status, body
        finally:
            conn.close()

    def probe_https(self, url: str) -> Tuple[int, bytes]:
        parsed = urllib.parse.urlparse(url)
        context = ssl.create_default_context()
        conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=self._http_timeout_ms/1000.0, context=context)
        try:
            conn.request("GET", parsed.path or "/")
            resp = conn.getresponse()
            body = resp.read()
            return resp.status, body
        finally:
            conn.close()
