from __future__ import annotations

from _interfaces import IRegistrar


class BaseRegistrar(IRegistrar):
    """
    Базовый каркас registrar.

    TERM-1: Consul Catalog + TTL heartbeat (реализация будет в core/registrar/adapters/consul_registrar.py).
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
        raise NotImplementedError

    def heartbeat(self, *, check_id: str) -> None:
        raise NotImplementedError

    def deregister(self, *, service: str, check_id: str | None = None) -> None:
        raise NotImplementedError
