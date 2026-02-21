from __future__ import annotations

import time
from typing import Any, Dict, Sequence, Tuple

from core._entities import EventCodeEnum, HealthSnapshotType, PolicyStatusEnum, StateEnum
from core._interfaces import IConfigs, IFSM, ILogger, IMarkers, IPolicy


class BaseFSM(IFSM):
    """
    Базовый каркас FSM.

    Наблюдаемость (TERM-1):
    - Переходы FSM: INFO.
    - Политики:
        - verbose: START/OK на DEBUG (FSM_VERBOSE_POLICY_LOGS=1).
        - FAIL: ERROR.
        - RETRY (ожидания): единый механизм WAIT + throttling:
            * policy.wait.start: INFO (однократно на цикл ожидания)
            * POLICY_RUN_RETRY: DEBUG (throttled)
            * policy.wait.long: WARN (редко, если ожидание затянулось)
            * policy.wait.end: INFO (однократно по завершению ожидания)
    """

    def __init__(
        self,
        *,
        cfg: IConfigs,
        log: ILogger,
        markers: IMarkers,
        service_name: str,
        policy_matrix: Dict[StateEnum, Sequence[IPolicy]] | None = None,
    ) -> None:
        self._cfg = cfg
        self._log = log
        self._markers = markers
        self._svc = service_name

        self._state: StateEnum = StateEnum.STARTING
        self._since_ms: int = self._now_ms()

        self._policy_matrix: Dict[StateEnum, Sequence[IPolicy]] = dict(policy_matrix or {})

        self._pause = False
        self._stop = False
        self._restart = False

        self._health: HealthSnapshotType = {
            "svc": self._svc,
            "version": str(getattr(self._cfg, "version", "")),
            "state": self._state,
            "ts_ms": self._now_ms(),
            "since_ts_ms": self._since_ms,
            "health": {},
            "details": {},
        }

        self._verbose_policy_logs = self._cfg_bool("FSM_VERBOSE_POLICY_LOGS", default=False)

        # Unified WAIT throttling (applies to any PolicyStatusEnum.RETRY)
        self._wait_debug_throttle_s = self._cfg_float("FSM_WAIT_DEBUG_THROTTLE_SEC", default=5.0)
        self._wait_warn_after_s = self._cfg_float("FSM_WAIT_WARN_AFTER_SEC", default=30.0)
        self._wait_warn_every_s = self._cfg_float("FSM_WAIT_WARN_EVERY_SEC", default=60.0)

        # key=(state, policy) -> ctx
        self._wait_ctx: Dict[Tuple[str, str], Dict[str, Any]] = {}

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def _now_mon() -> float:
        return time.monotonic()

    def _cfg_bool(self, key: str, default: bool) -> bool:
        try:
            v = self._cfg.get(key, None)
            if v is None:
                return bool(default)
            s = str(v).strip().lower()
            if s in ("1", "true", "yes", "on"):
                return True
            if s in ("0", "false", "no", "off"):
                return False
            return bool(default)
        except Exception:
            return bool(default)

    def _cfg_float(self, key: str, default: float) -> float:
        try:
            v = self._cfg.get(key, None)
            if v is None:
                return float(default)
            s = str(v).strip()
            if not s:
                return float(default)
            return float(s)
        except Exception:
            return float(default)

    # --- IFSM commands ---

    def pause(self) -> None:
        self._pause = True
        self.transition(StateEnum.PAUSED)

    def resume(self) -> None:
        self._pause = False
        self.transition(StateEnum.RUNNING)

    def restart(self) -> None:
        self._restart = True

    def stop(self) -> None:
        self._stop = True

    # --- read-only accessors ---

    def get_state(self) -> StateEnum:
        return self._state

    def get_snapshot(self) -> HealthSnapshotType:
        return dict(self._health)

    # --- configuration hooks ---

    def set_policy_matrix(self, matrix: Dict[StateEnum, Sequence[IPolicy]]) -> None:
        self._policy_matrix = dict(matrix)

    # --- helpers ---

    def transition(self, state: StateEnum) -> None:
        prev = self._state
        self._state = state
        self._since_ms = self._now_ms()

        # Любой переход обрывает контекст ожиданий предыдущего состояния.
        self._wait_ctx.clear()

        self.publish_state(details={"transition": state.value})

        try:
            self._log.event(
                EventCodeEnum.FSM_TRANSITION,
                level="INFO",
                fields={"svc": self._svc, "from": prev.value, "to": state.value},
            )
        except Exception:
            pass

    def publish_state(self, *, health: dict[str, object] | None = None, details: dict[str, object] | None = None) -> None:
        self._health["state"] = self._state
        self._health["ts_ms"] = self._now_ms()
        self._health["since_ts_ms"] = self._since_ms
        if health is not None:
            self._health["health"] = health
        if details is not None:
            self._health["details"] = details

    # --- unified wait logging/throttling ---

    def _wait_key(self, *, state: StateEnum, policy: IPolicy) -> Tuple[str, str]:
        return (state.value, policy.name)

    def _wait_start(self, *, state: StateEnum, policy: IPolicy, details: dict[str, object]) -> None:
        try:
            self._log.event(
                "policy.wait.start",
                level="INFO",
                fields={"svc": self._svc, "state": state.value, "policy": policy.name, "details": details},
            )
        except Exception:
            pass

    def _wait_still(
        self,
        *,
        state: StateEnum,
        policy: IPolicy,
        details: dict[str, object],
        elapsed_s: float,
        attempts: int,
        suppressed: int,
    ) -> None:
        try:
            self._log.event(
                EventCodeEnum.POLICY_RUN_RETRY,
                level="DEBUG",
                fields={
                    "svc": self._svc,
                    "state": state.value,
                    "policy": policy.name,
                    "elapsed_s": round(elapsed_s, 3),
                    "attempts": attempts,
                    "suppressed": suppressed,
                    "details": details,
                },
            )
        except Exception:
            pass

    def _wait_long(self, *, state: StateEnum, policy: IPolicy, details: dict[str, object], elapsed_s: float, attempts: int) -> None:
        try:
            self._log.event(
                "policy.wait.long",
                level="WARN",
                fields={
                    "svc": self._svc,
                    "state": state.value,
                    "policy": policy.name,
                    "elapsed_s": round(elapsed_s, 3),
                    "attempts": attempts,
                    "details": details,
                },
            )
        except Exception:
            pass

    def _wait_end(self, *, state: StateEnum, policy: IPolicy, elapsed_s: float, attempts: int, last_details: dict[str, object]) -> None:
        try:
            self._log.event(
                "policy.wait.end",
                level="INFO",
                fields={
                    "svc": self._svc,
                    "state": state.value,
                    "policy": policy.name,
                    "elapsed_s": round(elapsed_s, 3),
                    "attempts": attempts,
                    "details": last_details,
                },
            )
        except Exception:
            pass

    def _on_retry(self, *, state: StateEnum, policy: IPolicy, details: dict[str, object]) -> None:
        now = self._now_mon()
        k = self._wait_key(state=state, policy=policy)

        ctx = self._wait_ctx.get(k)
        if ctx is None:
            ctx = {
                "since_mon": now,
                "attempts": 0,
                "last_debug_mon": now,  # не печатаем "still" сразу после start
                "last_warn_mon": 0.0,
                "suppressed": 0,
                "last_details": {},
            }
            self._wait_ctx[k] = ctx
            self._wait_start(state=state, policy=policy, details=details)

        ctx["attempts"] = int(ctx.get("attempts", 0)) + 1
        ctx["last_details"] = details

        since = float(ctx.get("since_mon", now))
        elapsed_s = max(0.0, now - since)

        # DEBUG throttled
        last_debug = float(ctx.get("last_debug_mon", 0.0))
        if (now - last_debug) >= max(0.1, float(self._wait_debug_throttle_s)):
            suppressed = int(ctx.get("suppressed", 0))
            ctx["suppressed"] = 0
            ctx["last_debug_mon"] = now
            self._wait_still(
                state=state,
                policy=policy,
                details=details,
                elapsed_s=elapsed_s,
                attempts=int(ctx["attempts"]),
                suppressed=suppressed,
            )
        else:
            ctx["suppressed"] = int(ctx.get("suppressed", 0)) + 1

        # WARN on long waits (rare)
        if elapsed_s >= float(self._wait_warn_after_s):
            last_warn = float(ctx.get("last_warn_mon", 0.0))
            if (now - last_warn) >= max(1.0, float(self._wait_warn_every_s)):
                ctx["last_warn_mon"] = now
                self._wait_long(state=state, policy=policy, details=details, elapsed_s=elapsed_s, attempts=int(ctx["attempts"]))

    def _on_ok(self, *, state: StateEnum, policy: IPolicy, details: dict[str, object]) -> None:
        k = self._wait_key(state=state, policy=policy)
        ctx = self._wait_ctx.pop(k, None)
        if not ctx:
            return

        now = self._now_mon()
        since = float(ctx.get("since_mon", now))
        elapsed_s = max(0.0, now - since)
        attempts = int(ctx.get("attempts", 0))
        last_details = ctx.get("last_details") if isinstance(ctx.get("last_details"), dict) else details
        self._wait_end(state=state, policy=policy, elapsed_s=elapsed_s, attempts=attempts, last_details=last_details or details)

    # --- policies runner ---

    def run_policies(self, state: StateEnum) -> tuple[PolicyStatusEnum, dict[str, object], str]:
        """
        Выполнить политики состояния в фиксированном порядке.

        Возвращает:
        - status
        - details (из результата политики, если есть)
        - policy_name (для RETRY/FAIL)
        """
        for p in self._policy_matrix.get(state, ()) or ():
            if self._verbose_policy_logs:
                try:
                    self._log.event(
                        EventCodeEnum.POLICY_RUN_START,
                        level="DEBUG",
                        fields={"svc": self._svc, "state": state.value, "policy": p.name},
                    )
                except Exception:
                    pass

            r = p.run(state=state)
            status = r.get("status", PolicyStatusEnum.FAIL) if isinstance(r, dict) else PolicyStatusEnum.FAIL
            details = r.get("details", {}) if isinstance(r, dict) else {}
            if not isinstance(details, dict):
                details = {"details": details}

            if status == PolicyStatusEnum.OK:
                self._on_ok(state=state, policy=p, details=details)

                if self._verbose_policy_logs:
                    try:
                        self._log.event(
                            EventCodeEnum.POLICY_RUN_OK,
                            level="DEBUG",
                            fields={"svc": self._svc, "state": state.value, "policy": p.name, "details": details},
                        )
                    except Exception:
                        pass
                continue

            if status == PolicyStatusEnum.RETRY:
                self._on_retry(state=state, policy=p, details=details)
                return PolicyStatusEnum.RETRY, details, p.name

            # FAIL
            try:
                self._log.event(
                    EventCodeEnum.POLICY_RUN_FAIL,
                    level="ERROR",
                    fields={"svc": self._svc, "state": state.value, "policy": p.name, "details": details},
                )
            except Exception:
                pass
            return PolicyStatusEnum.FAIL, details, p.name

        return PolicyStatusEnum.OK, {}, ""
