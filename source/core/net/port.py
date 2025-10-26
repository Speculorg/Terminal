from __future__ import annotations
import socket, time


def wait_port(host: str, port: int, *, timeout_ms: int, interval_ms: int = 200) -> bool:
    """Ждёт доступности TCP-порта до timeout_ms. True если доступен."""
    deadline = time.time() + max(0.0, timeout_ms/1000.0)
    last_err: Exception | None = None
    while time.time() < deadline:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(max(0.05, interval_ms/1000.0))
        try:
            s.connect((host, int(port)))
            s.close()
            return True
        except Exception as e:
            last_err = e
            time.sleep(interval_ms/1000.0)
        finally:
            try: s.close()
            except Exception: pass
    return False
