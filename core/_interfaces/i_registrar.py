from __future__ import annotations
from typing import Protocol, runtime_checkable, Sequence


@runtime_checkable
class IRegistrar(Protocol):
    """
    Порт Service Discovery / registry (TERM-1: Consul Catalog + TTL heartbeat).
    """

    def register(
        self,
        *,
        service: str,
        address: str,
        port: int,
        tags: Sequence[str] = (),
        check_id: str | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        ...

    def heartbeat(self, *, check_id: str) -> None:
        ...

    def deregister(self, *, service: str, check_id: str | None = None) -> None:
        ...
