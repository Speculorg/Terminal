from __future__ import annotations

from _interfaces import IRegistrar


class BaseRegistrar(IRegistrar):
    """
    Базовый фасад registrar.

    Принцип: не использовать NotImplementedError.
    Если вдруг используется базовая реализация — это явная ошибка конфигурации.
    """

    def register(
        self,
        *,
        service: str,
        address: str,
        port: int,
        tags=(),
        check_id: str | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        raise RuntimeError("registrar_not_configured")

    def heartbeat(self, *, check_id: str) -> None:
        raise RuntimeError("registrar_not_configured")

    def deregister(self, *, service: str, check_id: str | None = None) -> None:
        raise RuntimeError("registrar_not_configured")
