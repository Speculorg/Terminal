from __future__ import annotations

import time
from typing import Dict, Sequence

from core._entities import EventCodeEnum, HealthSnapshotType, PolicyStatusEnum, StateEnum
from core._interfaces import IConfigs, IFSM, ILogger, IMarkers, IPolicy


class BaseFSM(IFSM):
    """
    Базовый каркас FSM.

    Важно:
    - stage_gates не проверяются самим FSM; это ответственность MarkerPolicy.
    - FSM не должен создавать зависимостей и не должен знать о конкретных сервисах.

    Наблюдаемость:
    - Всегда логируем переходы FSM.
    - Логи политик:
        - По умолчанию: только RETRY/FAIL (чтобы не засорять логи в TERM-1).
        - Подробно (verbose): START/OK тоже логируются, если FSM_VERBOSE_POLICY_LOGS=1.
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

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

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
        self.publish_state(details={"transition": state.value})

        try:
            self._log.event(
                EventCodeEnum.FSM_TRANSITION,
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

    def run_policies(self, state: StateEnum) -> PolicyStatusEnum:
        """
        Выполнить политики состояния в фиксированном порядке.

        Семантика:
        - OK: продолжаем
        - RETRY: прекращаем выполнение остальных политик и остаёмся в состоянии
        - FAIL: прекращаем и считаем ошибкой

        Логирование:
        - по умолчанию: только RETRY/FAIL (TERM-1 без шума)
        - verbose: START/OK тоже логируются
        """
        for p in self._policy_matrix.get(state, ()) or ():
            if self._verbose_policy_logs:
                try:
                    self._log.event(
                        EventCodeEnum.POLICY_RUN_START,
                        fields={"svc": self._svc, "state": state.value, "policy": p.name},
                    )
                except Exception:
                    pass

            r = p.run(state=state)
            status = r.get("status", PolicyStatusEnum.FAIL)
            details = r.get("details", {}) if isinstance(r, dict) else {}

            if status == PolicyStatusEnum.OK:
                if self._verbose_policy_logs:
                    try:
                        self._log.event(
                            EventCodeEnum.POLICY_RUN_OK,
                            fields={"svc": self._svc, "state": state.value, "policy": p.name, "details": details},
                        )
                    except Exception:
                        pass
                continue

            if status == PolicyStatusEnum.RETRY:
                try:
                    self._log.event(
                        EventCodeEnum.POLICY_RUN_RETRY,
                        fields={"svc": self._svc, "state": state.value, "policy": p.name, "details": details},
                    )
                except Exception:
                    pass
                return PolicyStatusEnum.RETRY

            try:
                self._log.event(
                    EventCodeEnum.POLICY_RUN_FAIL,
                    level="ERROR",
                    fields={"svc": self._svc, "state": state.value, "policy": p.name, "details": details},
                )
            except Exception:
                pass
            return PolicyStatusEnum.FAIL

        return PolicyStatusEnum.OK
