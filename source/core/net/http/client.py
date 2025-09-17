# source\core\net\http\client.py

from __future__ import annotations
import http.client
import ssl
from urllib.parse import urlparse
from typing import Optional


def probe_https(url: str, *, ssl_context: Optional[ssl.SSLContext], timeout: float = 3.0) -> bool:
    """
    Лёгкая синхронная GET-проба к HTTPS-ресурсу с клиентским TLS.
    Возвращает True при 2xx/3xx/401/403 (сервер ответил и рукопожатие прошло).
    Ошибки рукопожатия/сокета трактуем как False.
    """
    try:
        parts = urlparse(url)
        if parts.scheme != "https":
            return False
        host = parts.hostname or "localhost"
        port = parts.port or 443
        conn = http.client.HTTPSConnection(host, port, timeout=float(timeout), context=ssl_context)
        path = parts.path or "/"
        if parts.query:
            path += f"?{parts.query}"
        conn.request("GET", path, headers={"User-Agent": "terminal-probe/1.0"})
        resp = conn.getresponse()
        return 200 <= resp.status < 400 or resp.status in (401, 403)
    except Exception:
        return False
