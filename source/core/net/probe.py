from __future__ import annotations
import http.client, ssl, urllib.parse

def probe_http(url: str, *, timeout_ms: int = 5_000) -> tuple[int, bytes]:
    p = urllib.parse.urlparse(url)
    port = p.port or 80
    conn = http.client.HTTPConnection(p.hostname, port, timeout=timeout_ms/1000.0)
    try:
        conn.request("GET", p.path or "/")
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        conn.close()

def probe_https(url: str, *, timeout_ms: int = 5_000) -> tuple[int, bytes]:
    p = urllib.parse.urlparse(url)
    port = p.port or 443
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection(p.hostname, port, timeout=timeout_ms/1000.0, context=ctx)
    try:
        conn.request("GET", p.path or "/")
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        conn.close()
