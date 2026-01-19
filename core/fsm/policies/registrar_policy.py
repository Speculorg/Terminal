from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from core._base import BasePolicy
from core._entities import ErrorCodeEnum, StateEnum
from core._interfaces import IConfigs, IRegistrar


@dataclass(frozen=True, slots=True)
class RegistrarSpec:
    service: str
    address: str
    port: int
    tags: Sequence[str] = ()
    check_id: Optional[str] = None
    ttl_seconds: Optional[int] = None


class RegistrarPolicy(BasePolicy):
    """
    RegistrarPolicy регистрирует сервис и поддерживает TTL heartbeat.

    Семантика:
    - REGISTERING: делает register()
    - RUNNING: делает heartbeat()
    
    """

    def __init__(self, *, cfg: IConfigs, registrar: IRegistrar, spec: RegistrarSpec) -> None:
        super().__init__("RegistrarPolicy")
        self._cfg = cfg
        self._registrar = registrar
        self._spec = spec

        # deterministic check_id if not set
        self._check_id = spec.check_id or f"service:{spec.service}:ttl"

    def _run_impl(self, *, state: StateEnum):
        try:
            if state == StateEnum.REGISTERING:
                self._registrar.register(
                    service=self._spec.service,
                    address=self._spec.address,
                    port=int(self._spec.port),
                    tags=self._spec.tags,
                    check_id=self._check_id,
                    ttl_seconds=self._spec.ttl_seconds,
                )
                return self.ok(details={"registered": True, "check_id": self._check_id})

            if state == StateEnum.RUNNING:
                # heartbeat период контролируется тиком FSM или отдельным таймером (позже)
                self._registrar.heartbeat(check_id=self._check_id)
                return self.ok(details={"heartbeat": True, "check_id": self._check_id})

            return self.ok(details={"skip": True})

        except RuntimeError as e:
            # нормализованный runtime error от ConsulRegistrar
            return self.retry(reason=str(e))
        except Exception as e:
            return self.fail(error_code=ErrorCodeEnum.ERR_REGISTRY, reason=f"registrar_error:{type(e).__name__}")
