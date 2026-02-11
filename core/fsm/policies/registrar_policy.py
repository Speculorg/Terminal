from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Sequence

from core._base import BasePolicy
from core._entities import StateEnum
from core._interfaces import IConfigs, IMarkers, IRegistrar


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

    TERM-1 (автосходимость):
    - REGISTERING: блокирующая регистрация (RETRY пока не зарегистрировались)
    - RUNNING: НЕ блокирует состояние (никогда не RETRY), работает с backoff и самовосстановлением:
        - если registration/check отсутствуют -> (пере)регистрируется
        - если ACL ещё не готова -> увеличивает backoff
        - если check_id неизвестен (404) -> считает регистрацию потерянной и инициирует re-register
    """

    def __init__(
        self,
        *,
        cfg: IConfigs,
        registrar: IRegistrar,
        spec: RegistrarSpec,
        markers: IMarkers | None = None,
        ready_marker: str | None = None,
    ) -> None:
        super().__init__("RegistrarPolicy")
        self._cfg = cfg
        self._registrar = registrar
        self._spec = spec

        self._markers = markers
        self._ready_marker = (ready_marker or f"{spec.service}_ready") if markers is not None else None

        self._check_id = spec.check_id or f"service:{spec.service}:ttl"

        # state
        self._registered: bool = False

        self._last_register_mon: float = 0.0
        self._last_heartbeat_mon: float = 0.0

        self._next_register_mon: float = 0.0
        self._next_heartbeat_mon: float = 0.0

        self._register_fail_streak: int = 0
        self._heartbeat_fail_streak: int = 0

        # rate limit window for REGISTERING
        self._window_start_mon: float = time.monotonic()
        self._window_attempts: int = 0

    def _cfg_int(self, key: str, default: int) -> int:
        try:
            return int(self._cfg.get(key, default) or default)
        except Exception:
            return int(default)

    @staticmethod
    def _backoff_sec(streak: int, *, base: float, cap: float) -> float:
        v = base * (1.7 ** max(0, streak))
        return cap if v > cap else v

    @staticmethod
    def _is_acl_not_ready(reason: str) -> bool:
        r = (reason or "").lower()
        return ("acl system must be bootstrapped" in r) or ("acl not found" in r)

    @staticmethod
    def _is_unknown_check(reason: str) -> bool:
        r = (reason or "").lower()
        return ("unknown check id" in r) or ("404" in r and "check" in r)

    def _register_once(self, *, ttl_sec: int) -> None:
        self._registrar.register(
            service=self._spec.service,
            address=self._spec.address,
            port=int(self._spec.port),
            tags=self._spec.tags,
            check_id=self._check_id,
            ttl_seconds=int(ttl_sec) if ttl_sec else None,
        )

    def _heartbeat_once(self) -> None:
        self._registrar.heartbeat(check_id=self._check_id)

    def _run_impl(self, *, state: StateEnum):
        now = time.monotonic()

        ttl_sec = self._spec.ttl_seconds
        if ttl_sec is None:
            ttl_sec = self._cfg_int("REGISTRAR_TTL_SEC", 15)

        heartbeat_period = self._cfg_int("REGISTRAR_HEARTBEAT_PERIOD_SEC", 7)
        cooldown = self._cfg_int("REGISTRAR_REREGISTRATION_COOLDOWN_SEC", 15)
        window_sec = max(1, self._cfg_int("REGISTRAR_DEREGISTER_CRITICAL_SERVICE_AFTER_SEC", 45))
        max_attempts = max(1, self._cfg_int("REGISTRAR_MAX_REREG_ATTEMPTS_PER_WINDOW", 5))

        # backoff tuning (не делаем обязательными: берём defaults)
        reg_backoff_base = float(self._cfg_int("REGISTRAR_BACKOFF_BASE_SEC", 1))
        reg_backoff_cap = float(self._cfg_int("REGISTRAR_BACKOFF_CAP_SEC", 30))
        hb_backoff_base = float(self._cfg_int("REGISTRAR_HEARTBEAT_BACKOFF_BASE_SEC", 2))
        hb_backoff_cap = float(self._cfg_int("REGISTRAR_HEARTBEAT_BACKOFF_CAP_SEC", 30))

        # ---------------- REGISTERING (blocking) ----------------
        if state == StateEnum.REGISTERING:
            # window reset
            if (now - self._window_start_mon) >= float(window_sec):
                self._window_start_mon = now
                self._window_attempts = 0

            # cooldown after success
            if self._last_register_mon and (now - self._last_register_mon) < float(cooldown):
                return self.retry(reason="cooldown", details={"check_id": self._check_id})

            # explicit backoff after errors
            if self._next_register_mon and now < self._next_register_mon:
                wait_s = round(self._next_register_mon - now, 3)
                return self.retry(reason="register_backoff", details={"check_id": self._check_id, "wait_s": wait_s})

            # rate limit window
            if self._window_attempts >= max_attempts:
                self._next_register_mon = now + 1.0
                return self.retry(
                    reason="reregistration_rate_limited",
                    details={"check_id": self._check_id, "attempts": self._window_attempts},
                )
            self._window_attempts += 1

            try:
                self._register_once(ttl_sec=int(ttl_sec))
                self._registered = True
                self._last_register_mon = now
                self._last_heartbeat_mon = now
                self._next_heartbeat_mon = now + float(heartbeat_period)
                self._register_fail_streak = 0
                if self._markers is not None and self._ready_marker is not None:
                    try:
                        self._markers.set(self._ready_marker)
                    except Exception:
                        pass
                return self.ok(details={"registered": True, "check_id": self._check_id, "ttl_sec": ttl_sec, "ready_marker": self._ready_marker})

            except RuntimeError as e:
                reason = str(e)
                extra = 2.0 if self._is_acl_not_ready(reason) else 0.0
                self._register_fail_streak += 1
                backoff = self._backoff_sec(self._register_fail_streak, base=reg_backoff_base, cap=reg_backoff_cap) + extra
                self._next_register_mon = now + backoff
                return self.retry(reason=reason, details={"check_id": self._check_id, "backoff_s": round(backoff, 3)})

            except Exception as e:
                self._register_fail_streak += 1
                backoff = self._backoff_sec(self._register_fail_streak, base=reg_backoff_base, cap=reg_backoff_cap)
                self._next_register_mon = now + backoff
                return self.retry(
                    reason=f"registrar_error:{type(e).__name__}",
                    details={"check_id": self._check_id, "backoff_s": round(backoff, 3), "exc": str(e)[:256]},
                )

        # ---------------- RUNNING (non-blocking) ----------------
        if state == StateEnum.RUNNING:
            # 1) if not registered -> background register (NO RETRY)
            if not self._registered:
                if self._next_register_mon and now < self._next_register_mon:
                    return self.ok(details={"registered": False, "reason": "register_backoff", "check_id": self._check_id, "wait_s": round(self._next_register_mon - now, 3)})

                if self._last_register_mon and (now - self._last_register_mon) < float(cooldown):
                    return self.ok(details={"registered": False, "reason": "cooldown", "check_id": self._check_id})

                try:
                    self._register_once(ttl_sec=int(ttl_sec))
                    self._registered = True
                    self._last_register_mon = now
                    self._last_heartbeat_mon = now
                    self._next_heartbeat_mon = now + float(heartbeat_period)
                    self._register_fail_streak = 0
                    if self._markers is not None and self._ready_marker is not None:
                        try:
                            self._markers.set(self._ready_marker)
                        except Exception:
                            pass
                    return self.ok(details={"registered": True, "check_id": self._check_id, "ttl_sec": ttl_sec, "ready_marker": self._ready_marker})

                except RuntimeError as e:
                    reason = str(e)
                    extra = 2.0 if self._is_acl_not_ready(reason) else 0.0
                    self._register_fail_streak += 1
                    backoff = self._backoff_sec(self._register_fail_streak, base=reg_backoff_base, cap=reg_backoff_cap) + extra
                    self._next_register_mon = now + backoff
                    return self.ok(details={"registered": False, "reason": reason, "check_id": self._check_id, "backoff_s": round(backoff, 3)})

                except Exception as e:
                    self._register_fail_streak += 1
                    backoff = self._backoff_sec(self._register_fail_streak, base=reg_backoff_base, cap=reg_backoff_cap)
                    self._next_register_mon = now + backoff
                    return self.ok(details={"registered": False, "reason": f"registrar_error:{type(e).__name__}", "check_id": self._check_id, "backoff_s": round(backoff, 3), "exc": str(e)[:256]})

            # 2) heartbeat with backoff (NO RETRY)
            if self._next_heartbeat_mon and now < self._next_heartbeat_mon:
                return self.ok(details={"registered": True, "reason": "heartbeat_wait", "check_id": self._check_id, "wait_s": round(self._next_heartbeat_mon - now, 3)})

            try:
                self._heartbeat_once()
                self._last_heartbeat_mon = now
                self._next_heartbeat_mon = now + float(heartbeat_period)
                self._heartbeat_fail_streak = 0
                return self.ok(details={"registered": True, "heartbeat": "ok", "check_id": self._check_id})

            except RuntimeError as e:
                reason = str(e)

                # if check disappeared -> force re-register soon
                if self._is_unknown_check(reason):
                    self._registered = False
                    self._next_register_mon = now + 0.2
                    return self.ok(details={"registered": False, "reason": reason, "check_id": self._check_id, "action": "reregister"})

                extra = 2.0 if self._is_acl_not_ready(reason) else 0.0
                self._heartbeat_fail_streak += 1
                backoff = self._backoff_sec(self._heartbeat_fail_streak, base=hb_backoff_base, cap=hb_backoff_cap) + extra
                self._next_heartbeat_mon = now + backoff
                return self.ok(details={"registered": True, "heartbeat": "fail", "reason": reason, "check_id": self._check_id, "backoff_s": round(backoff, 3)})

            except Exception as e:
                self._heartbeat_fail_streak += 1
                backoff = self._backoff_sec(self._heartbeat_fail_streak, base=hb_backoff_base, cap=hb_backoff_cap)
                self._next_heartbeat_mon = now + backoff
                return self.ok(details={"registered": True, "heartbeat": "fail", "reason": f"registrar_error:{type(e).__name__}", "check_id": self._check_id, "backoff_s": round(backoff, 3), "exc": str(e)[:256]})

        return self.ok(details={"skip": True})
