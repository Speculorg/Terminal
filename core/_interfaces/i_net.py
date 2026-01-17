from __future__ import annotations
from typing import Protocol, runtime_checkable, Optional


@runtime_checkable
class INet(Protocol):
    """
    Порт сетевых проверок/ожиданий.
    Используется политиками готовности (ports/HTTP/HTTPS).
    """

    def tcp_check(self, host: str, port: int, *, timeout_ms: int) -> bool:
        ...

    def tcp_wait(self, host: str, port: int, *, timeout_ms: int) -> bool:
        ...

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
        """Возвращает (status_code, body_snippet). Исключения должны быть нормализованы реализацией."""
        ...
