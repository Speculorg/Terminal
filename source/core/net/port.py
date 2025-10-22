from __future__ import annotations
import socket, time

def wait_port(host: str, port: int, *, timeout_ms: int) -> bool:
    """Ждёт доступности TCP-порта до timeout_ms. True если доступен."""
    deadline = time.time() + max(0.0, timeout_ms/1000.0)
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                if s.connect_ex((host, int(port))) == 0:
                    return True
            except Exception:
                pass
        time.sleep(0.1)
    return False
