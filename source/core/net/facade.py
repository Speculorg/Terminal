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
        self._port_timeout_ms = int(cfg.fsm.state_securing_timeout_ms)
        self._http_timeout_ms = int(cfg.kv.request_timeout_ms)

    def build_url(self, scheme: str, host: str, port: int, path: str = "/") -> str:
        path = path if path.startswith("/") else "/" + path
        return f"{scheme}://{host}:{int(port)}{path}"

    def fqdn(self, host: str) -> str:
        try:
            return socket.getfqdn(host)
        except Exception:
            return host

    def wait_port(self, host: str, port: int) -> None:
        deadline = time.time() + self._port_timeout_ms / 1000.0
        last_err: Exception | None = None
        while time.time() < deadline:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            try:
                s.connect((host, int(port)))
                s.close()
                return
            except Exception as e:
                last_err = e
                time.sleep(0.2)
            finally:
                try:
                    s.close()
                except Exception:
                    pass
        raise TimeoutError(f"port not ready: {host}:{port} -> {type(last_err).__name__ if last_err else 'unknown'}")

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
        port = parsed.port or 443
        conn = http.client.HTTPSConnection(parsed.hostname, port, timeout=self._http_timeout_ms/1000.0, context=context)
        try:
            conn.request("GET", parsed.path or "/")
            resp = conn.getresponse()
            body = resp.read()
            return resp.status, body
        finally:
            conn.close()
