# source\core\net\port.py


from __future__ import annotations
import asyncio, socket, time

async def wait_port(host: str, port: int, timeout: float = 30.0, probe_timeout: float = 2.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=probe_timeout):
                return True
        except Exception:
            await asyncio.sleep(0.5)
    return False
