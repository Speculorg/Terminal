from __future__ import annotations
import socket, ssl, time, http.client, urllib.parse
from typing import Tuple

class Net:
    def __init__(self, *, default_timeout_ms: int = 5000) -> None:
        self._default_timeout = max(100, int(default_timeout_ms))

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
        end_ts = time.monotonic() + (self._default_timeout / 1000.0)
        last_err: Exception | None = None
        while time.monotonic() < end_ts:
            try:
                with socket.create_connection((host, port), timeout=1.0):
                    return
            except Exception as e:
                last_err = e
                time.sleep(0.1)
        raise TimeoutError(f"wait_port timeout for {host}:{port}: {last_err}")

    def probe_http(self, url: str) -> Tuple[int, bytes]:
        parsed = urllib.parse.urlparse(url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=self._default_timeout/1000.0)
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
        conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=self._default_timeout/1000.0, context=context)
        try:
            conn.request("GET", parsed.path or "/")
            resp = conn.getresponse()
            body = resp.read()
            return resp.status, body
        finally:
            conn.close()
