from __future__ import annotations

def build_url(host: str, port: int, path: str = "/", *, https: bool = False) -> str:
    scheme = "https" if https else "http"
    if not path.startswith('/'):
        path = '/' + path
    return f"{scheme}://{host}:{int(port)}{path}"
