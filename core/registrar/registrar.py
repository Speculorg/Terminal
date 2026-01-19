from __future__ import annotations

from _base import BaseRegistrar
from _interfaces import IConfigs, IRegistrar

from registrar.adapters.consul_registrar import ConsulRegistrar


class Registrar(BaseRegistrar):
    """
    Registrar — фасад service discovery / registry.

    TERM-1: Consul Catalog + TTL heartbeat.
    """

    def __init__(self, impl: IRegistrar) -> None:
        self._impl = impl

    @classmethod
    def from_configs(cls, *, cfg: IConfigs) -> "Registrar":
        # TERM-1: единственная реализация — Consul
        impl = ConsulRegistrar.from_configs(cfg=cfg)
        return cls(impl=impl)

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
        self._impl.register(
            service=service,
            address=address,
            port=port,
            tags=tags,
            check_id=check_id,
            ttl_seconds=ttl_seconds,
        )

    def heartbeat(self, *, check_id: str) -> None:
        self._impl.heartbeat(check_id=check_id)

    def deregister(self, *, service: str, check_id: str | None = None) -> None:
        self._impl.deregister(service=service, check_id=check_id)
