from __future__ import annotations
import socket
import ssl
import time
import http.client
import urllib.parse
from typing import Tuple, Optional

from interfaces import IConfigs

class Net:
    """Сетевые утилиты и пробы. Таймауты берём из cfg.fsm.* или передаём явно."""
    def __init__(self, cfg: IConfigs) -> None:
        self._cfg = cfg

    # --- низкоуровневые проверки портов ---
    def tcp_ping(self, host: str, port: int, timeout_ms: int | None = None) -> bool:
        to = (timeout_ms or 2000) / 1000.0
        try:
            with socket.create_connection((host, port), timeout=to):
                return True
        except Exception:
            return False

    def tls_handshake(self, host: str, port: int, timeout_ms: int | None = None) -> bool:
        to = (timeout_ms or 3000) / 1000.0
        ctx = ssl.create_default_context()
        try:
            with socket.create_connection((host, port), timeout=to) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    ssock.do_handshake()
                    return True
        except Exception:
            return False

    # --- HTTP пробы ---
    def http_get(self, url: str, timeout_ms: int | None = None) -> Tuple[int, int]:
        to = (timeout_ms or 2000) / 1000.0
        u = urllib.parse.urlparse(url)
        conn_cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
        port = u.port or (443 if u.scheme == "https" else 80)
        path = u.path or "/"
        if u.query:
            path += f"?{u.query}"
        conn = conn_cls(u.hostname, port=port, timeout=to)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            n = len(resp.read() or b"")
            return resp.status, n
        except Exception:
            return 0, 0
        finally:
            try:
                conn.close()
            except Exception:
                pass
