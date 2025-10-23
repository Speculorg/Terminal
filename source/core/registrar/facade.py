from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from interfaces import IConfigs, ILogger

@dataclass
class Registrar:
    """Порт регистрации и TTL-heartbeat поверх клиент-адаптера ConsulRegistrar."""
    cfg: IConfigs
    logger: ILogger
    client: Any  # должен иметь методы register_service, deregister_service, pass_ttl

    def _service_id(self, svc: str) -> str:
        return f"{svc}"

    def register(self, svc: str) -> bool:
        return self.client.register_service(
            svc_id=self._service_id(svc),
            name=svc,
            port=int(self.cfg.context.port),
            tags=list(self.cfg.context.tags),
            ttl_sec=int(self.cfg.registrar.ttl_sec),
        )

    def deregister(self, svc: str) -> bool:
        return self.client.deregister_service(self._service_id(svc))

    def heartbeat(self, svc: str) -> bool:
        check_id = f"service:{self._service_id(svc)}"
        return self.client.pass_ttl(check_id)
