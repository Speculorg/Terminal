from __future__ import annotations
import socket
import time
from typing import Optional
import requests

from core._interfaces import INet


class BaseNet(INet):
    """
    Базовый фасад сетевых проверок/ожиданий.

    Принцип:
    - tcp_check: одиночная попытка
    - tcp_wait: попытки до timeout_ms (с небольшим sleep)
    """

    def tcp_check(self, host: str, port: int, *, timeout_ms: int) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(max(0.001, timeout_ms / 1000.0))
            return s.connect_ex((host, port)) == 0
        except Exception:
            return False
        finally:
            try:
                s.close()
            except Exception:
                pass

    def tcp_wait(self, host: str, port: int, *, timeout_ms: int) -> bool:
        deadline = time.monotonic() + max(0, timeout_ms) / 1000.0
        while time.monotonic() <= deadline:
            if self.tcp_check(host, port, timeout_ms=min(250, timeout_ms)):
                return True
            time.sleep(0.1)
        return False

    def http_get(
        self,
        url: str,
        *,
        timeout_ms: int,
        verify_tls: bool = True,
        ca_file: Optional[str] = None,
        client_cert_file: Optional[str] = None,
        client_key_file: Optional[str] = None,
    ) -> tuple[int, str]:
        timeout_s = max(0.001, timeout_ms / 1000.0)

        verify: bool | str
        if not verify_tls:
            verify = False
        elif ca_file:
            verify = ca_file
        else:
            verify = True

        cert = None
        if client_cert_file and client_key_file:
            cert = (client_cert_file, client_key_file)
        elif client_cert_file:
            cert = client_cert_file

        try:
            r = requests.get(url, timeout=timeout_s, verify=verify, cert=cert)
            body = (r.text or "")[:2048]
            return int(r.status_code), body
        except requests.RequestException as e:
            # Нормализуем сетевые ошибки в единый ответ
            return 0, f"request_error:{type(e).__name__}"
