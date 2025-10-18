from __future__ import annotations
import socket, ssl, time, http.client, urllib.parse
from typing import Tuple
from interfaces import INet
from base.exceptions import DeadlineRequiredError, OperationTimeoutError

class Net(INet):
    def __init__(self):
        pass

    def _require_deadline(self, deadline_ms: int) -> float:
        if deadline_ms is None:
            raise DeadlineRequiredError("deadline_ms is required as a named argument")
        return time.monotonic() + (deadline_ms / 1000.0)

    # ---- INet ----
    def build_url(self, scheme: str, host: str, port: int, path: str = "/", *, deadline_ms: int) -> str:
        deadline_ts = self._require_deadline(deadline_ms)
        path = path or "/"
        if not path.startswith("/"):
            path = "/" + path
        netloc = f"{host}:{int(port)}"
        return urllib.parse.urlunparse((scheme, netloc, path, "", "", ""))

    def fqdn(self, host: str, *, deadline_ms: int) -> str:
        self._require_deadline(deadline_ms)
        return socket.getfqdn(host)

    def wait_port(self, host: str, port: int, *, deadline_ms: int) -> None:
        deadline_ts = self._require_deadline(deadline_ms)
        last_err: Exception | None = None
        while time.monotonic() < deadline_ts:
            try:
                with socket.create_connection((host, port), timeout=0.5):
                    return
            except Exception as e:
                last_err = e
                time.sleep(0.1)
        raise OperationTimeoutError(f"wait_port timeout for {host}:{port}: {last_err}")

    def probe_http(self, url: str, *, deadline_ms: int) -> Tuple[int, bytes]:
        deadline_ts = self._require_deadline(deadline_ms)
        parsed = urllib.parse.urlparse(url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=2.0)
        try:
            conn.request("GET", parsed.path or "/")
            resp = conn.getresponse()
            body = resp.read()
            return resp.status, body
        finally:
            conn.close()

    def probe_https(self, url: str, *, deadline_ms: int) -> Tuple[int, bytes]:
        deadline_ts = self._require_deadline(deadline_ms)
        parsed = urllib.parse.urlparse(url)
        context = ssl.create_default_context()
        conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=2.0, context=context)
        try:
            conn.request("GET", parsed.path or "/")
            resp = conn.getresponse()
            body = resp.read()
            return resp.status, body
        finally:
            conn.close()
