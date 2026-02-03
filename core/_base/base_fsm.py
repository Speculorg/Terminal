from __future__ import annotations

import time
from typing import Dict, Sequence

from core._entities import HealthSnapshotType, PolicyStatusEnum, StateEnum
from core._interfaces import IConfigs, IFSM, ILogger, IMarkers, IPolicy


class BaseFSM(IFSM):
    """
    Базовый каркас FSM.

    Инварианты:
    - хранит текущее состояние
    - хранит матрицу "state -> policies" (фиксированный порядок внутри состояния)
    - публикует HealthSnapshot (in-memory)
    - предоставляет базовые команды управления (pause/resume/restart/stop)

    Важно:
    - stage_gates не проверяются самим FSM; это ответственность MarkerPolicy.
      (RunProfile.stage_gates -> MarkerPolicy)
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

        # IFSM command flags
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

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    # --- IFSM commands ---

    def pause(self) -> None:
        self._pause = True
        self.transition(StateEnum.PAUSED)

    def resume(self) -> None:
        self._pause = False
        # минимально: возвращаемся в RUNNING; фактический цикл сам продолжит выполнение
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
        self._state = state
        self._since_ms = self._now_ms()
        self.publish_state(details={"transition": state.value})

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
        - RETRY: немедленно прекращаем выполнение остальных политик и остаёмся в состоянии
        - FAIL: немедленно прекращаем и считаем ошибкой

        Примечание:
        - Детализация причин RETRY/FAIL логируется на уровне политик и/или FSM (верхний уровень).
        """
        for p in self._policy_matrix.get(state, ()) or ():
            r = p.run(state=state)
            status = r.get("status", PolicyStatusEnum.FAIL)
            if status == PolicyStatusEnum.OK:
                continue
            return status
        return PolicyStatusEnum.OK
