from __future__ import annotations

from typing import Mapping, Optional

from core._base import BaseNet
from core._interfaces import IConfigs


class Net(BaseNet):
    """
    Net — фасад сетевых проверок.

    TERM-1:
    - tcp_check/tcp_wait для ожидания портов демонов/прокси
    - http_get/https_get для readiness проверок (с заголовками и mTLS)
    """

    def __init__(self, *, default_timeout_ms: int = 3000) -> None:
        super().__init__()
        self._default_timeout_ms = max(1, int(default_timeout_ms))

    @classmethod
    def from_configs(cls, *, cfg: IConfigs) -> "Net":
        timeout_ms = int(cfg.get("NET_DEFAULT_TIMEOUT_MS", 3000) or 3000)
        return cls(default_timeout_ms=timeout_ms)

    def tcp_check(self, host: str, port: int, *, timeout_ms: int | None = None) -> bool:
        return super().tcp_check(host, port, timeout_ms=int(timeout_ms or self._default_timeout_ms))

    def tcp_wait(self, host: str, port: int, *, timeout_ms: int | None = None) -> bool:
        return super().tcp_wait(host, port, timeout_ms=int(timeout_ms or self._default_timeout_ms))

    def http_get(
        self,
        url: str,
        *,
        timeout_ms: int | None = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> tuple[int, str]:
        return super().http_get(
            url,
            timeout_ms=int(timeout_ms or self._default_timeout_ms),
            headers=headers,
        )

    def https_get(
        self,
        url: str,
        *,
        timeout_ms: int | None = None,
        headers: Optional[Mapping[str, str]] = None,
        verify_tls: bool = True,
        ca_file: str | None = None,
        client_cert_file: str | None = None,
        client_key_file: str | None = None,
    ) -> tuple[int, str]:
        return super().https_get(
            url,
            timeout_ms=int(timeout_ms or self._default_timeout_ms),
            headers=headers,
            verify_tls=verify_tls,
            ca_file=ca_file,
            client_cert_file=client_cert_file,
            client_key_file=client_key_file,
        )
