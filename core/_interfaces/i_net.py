from __future__ import annotations

from typing import Mapping, Optional, Protocol, runtime_checkable


@runtime_checkable
class INet(Protocol):
    """
    Порт сетевых проверок/ожиданий.

    Используется политиками готовности (ports/HTTP/HTTPS).

    TERM-1: реализации должны нормализовать сетевые ошибки и не выбрасывать
    исключения наружу. Для http/https возвращается (status_code, body_snippet).
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
        headers: Optional[Mapping[str, str]] = None,
    ) -> tuple[int, str]:
        """Возвращает (status_code, body_snippet)."""
        ...

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
        """Возвращает (status_code, body_snippet)."""
        ...
