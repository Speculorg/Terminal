from __future__ import annotations

import time
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

    Семантика TERM-1:
    - REGISTERING: register()
    - RUNNING: heartbeat() с троттлингом по REGISTRAR_HEARTBEAT_PERIOD_SEC
    """

    def __init__(self, *, cfg: IConfigs, registrar: IRegistrar, spec: RegistrarSpec) -> None:
        super().__init__("RegistrarPolicy")
        self._cfg = cfg
        self._registrar = registrar
        self._spec = spec

        self._check_id = spec.check_id or f"service:{spec.service}:ttl"
        self._last_hb_ms: int = 0

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    def _hb_period_ms(self) -> int:
        try:
            sec = int(self._cfg.get("REGISTRAR_HEARTBEAT_PERIOD_SEC", 7) or 7)
        except Exception:
            sec = 7
        return max(1000, sec * 1000)

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
                now = self._now_ms()
                if self._last_hb_ms and (now - self._last_hb_ms) < self._hb_period_ms():
                    return self.ok(details={"skip": True, "reason": "heartbeat_throttled"})
                self._registrar.heartbeat(check_id=self._check_id)
                self._last_hb_ms = now
                return self.ok(details={"heartbeat": True, "check_id": self._check_id})

            return self.ok(details={"skip": True})

        except RuntimeError as e:
            return self.retry(reason=str(e))
        except Exception:
            return self.fail(error_code=ErrorCodeEnum.ERR_REGISTRY, reason="registrar_error")
