from __future__ import annotations

import socket
import time
from typing import Any, Mapping, Optional

import requests

from core._interfaces import INet

class BaseNet(INet):
    """
    BaseNet — минимальный набор сетевых утилит TERM-1.

    Принципы:
    - без исключений наружу: ошибки нормализуются в (0, "request_error:...")
    - один общий приватный _get(); публичные http_get/https_get — тонкие врапперы
    """

    def tcp_check(self, host: str, port: int, *, timeout_ms: int) -> bool:
        try:
            with socket.create_connection((host, int(port)), timeout=max(0.001, timeout_ms / 1000.0)):
                return True
        except Exception:
            return False

    def tcp_wait(self, host: str, port: int, *, timeout_ms: int) -> bool:
        deadline = time.time() + max(0.0, timeout_ms / 1000.0)
        while time.time() < deadline:
            if self.tcp_check(host, port, timeout_ms=250):
                return True
            time.sleep(0.05)
        return False

    def _get(
        self,
        url: str,
        *,
        timeout_ms: int,
        headers: Optional[Mapping[str, str]] = None,
        verify_tls: bool = True,
        ca_file: Optional[str] = None,
        client_cert_file: Optional[str] = None,
        client_key_file: Optional[str] = None,
    ) -> tuple[int, str]:
        """Общий HTTP(S) GET, нормализует ошибки."""
        verify: Any
        if not verify_tls:
            verify = False
        elif ca_file:
            verify = ca_file
        else:
            verify = True

        cert: Any = None
        if client_cert_file and client_key_file:
            cert = (client_cert_file, client_key_file)
        elif client_cert_file:
            cert = client_cert_file

        try:
            r = requests.get(
                url,
                headers=dict(headers or {}),
                timeout=max(0.001, timeout_ms / 1000.0),
                verify=verify,
                cert=cert,
            )
            body = (r.text or "")
            return int(r.status_code), body[:512]
        except Exception as e:
            return 0, f"request_error:{type(e).__name__}:{str(e)[:256]}"

    def http_get(
        self,
        url: str,
        *,
        timeout_ms: int,
        headers: Optional[Mapping[str, str]] = None,
    ) -> tuple[int, str]:
        return self._get(url, timeout_ms=timeout_ms, headers=headers, verify_tls=False)

    def https_get(
        self,
        url: str,
        *,
        timeout_ms: int,
        headers: Optional[Mapping[str, str]] = None,
        verify_tls: bool = True,
        ca_file: Optional[str] = None,
        client_cert_file: Optional[str] = None,
        client_key_file: Optional[str] = None,
    ) -> tuple[int, str]:
        return self._get(
            url,
            timeout_ms=timeout_ms,
            headers=headers,
            verify_tls=verify_tls,
            ca_file=ca_file,
            client_cert_file=client_cert_file,
            client_key_file=client_key_file,
        )
