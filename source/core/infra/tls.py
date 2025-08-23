# source\core\infra\tls.py


from __future__ import annotations
import socket, ssl

def probe_tls(host: str, port_https: int, ca_file: str | None = None, timeout: float = 5.0) -> bool:
    ctx = ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()
    try:
        with socket.create_connection((host, port_https), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host):
                return True
    except Exception:
        return False
