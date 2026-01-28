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

    TERM-1 вариант B:
    - stage-gates завязаны на маркеры (сетевые проверки живут в политиках/ACL)
    - REGISTERING: register() с TTL check
    - RUNNING: периодический heartbeat(check_id) (throttle по REGISTRAR_HEARTBEAT_PERIOD_SEC)

    Защита от "шторма":
    - cooldown на повторную регистрацию (REGISTRAR_REREGISTRATION_COOLDOWN_SEC)
    - max попыток повторной регистрации в окне (REGISTRAR_MAX_REREG_ATTEMPTS_PER_WINDOW)
    """

    def __init__(self, *, cfg: IConfigs, registrar: IRegistrar, spec: RegistrarSpec) -> None:
        super().__init__("RegistrarPolicy")
        self._cfg = cfg
        self._registrar = registrar
        self._spec = spec

        self._check_id = spec.check_id or f"service:{spec.service}:ttl"

        # state
        self._last_register_mon: float = 0.0
        self._last_heartbeat_mon: float = 0.0
        self._window_start_mon: float = time.monotonic()
        self._window_attempts: int = 0

    def _cfg_int(self, key: str, default: int) -> int:
        try:
            return int(self._cfg.get(key, default) or default)
        except Exception:
            return int(default)

    def _run_impl(self, *, state: StateEnum):
        now = time.monotonic()

        ttl_sec = self._spec.ttl_seconds
        if ttl_sec is None:
            ttl_sec = self._cfg_int("REGISTRAR_TTL_SEC", 15)

        heartbeat_period = self._cfg_int("REGISTRAR_HEARTBEAT_PERIOD_SEC", 7)
        cooldown = self._cfg_int("REGISTRAR_REREGISTRATION_COOLDOWN_SEC", 15)
        window_sec = max(1, self._cfg_int("REGISTRAR_DEREGISTER_CRITICAL_SERVICE_AFTER_SEC", 45))
        max_attempts = max(1, self._cfg_int("REGISTRAR_MAX_REREG_ATTEMPTS_PER_WINDOW", 5))

        try:
            if state == StateEnum.REGISTERING:
                # window reset
                if (now - self._window_start_mon) >= float(window_sec):
                    self._window_start_mon = now
                    self._window_attempts = 0

                # cooldown
                if self._last_register_mon and (now - self._last_register_mon) < float(cooldown):
                    return self.ok(details={"registered": False, "reason": "cooldown", "check_id": self._check_id})

                if self._window_attempts >= max_attempts:
                    return self.retry(reason="reregistration_rate_limited", details={"check_id": self._check_id, "attempts": self._window_attempts})

                self._window_attempts += 1

                self._registrar.register(
                    service=self._spec.service,
                    address=self._spec.address,
                    port=int(self._spec.port),
                    tags=self._spec.tags,
                    check_id=self._check_id,
                    ttl_seconds=int(ttl_sec) if ttl_sec else None,
                )
                self._last_register_mon = now
                self._last_heartbeat_mon = now
                return self.ok(details={"registered": True, "check_id": self._check_id, "ttl_sec": ttl_sec})

            if state == StateEnum.RUNNING:
                if (now - self._last_heartbeat_mon) < float(heartbeat_period):
                    return self.ok(details={"heartbeat": False, "reason": "throttle", "check_id": self._check_id})

                self._registrar.heartbeat(check_id=self._check_id)
                self._last_heartbeat_mon = now
                return self.ok(details={"heartbeat": True, "check_id": self._check_id})

            return self.ok(details={"skip": True})

        except RuntimeError as e:
            # нормализованный runtime error от Registrar adapter
            return self.retry(reason=str(e), details={"check_id": self._check_id})
        except Exception as e:
            return self.fail(error_code=ErrorCodeEnum.ERR_REGISTRY, reason=f"registrar_error:{type(e).__name__}", details={"check_id": self._check_id})
