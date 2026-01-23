from __future__ import annotations

import time
from typing import Dict, Iterable, List, Mapping, Sequence

from core._entities import HealthSnapshotType, PolicyStatusEnum, StateEnum
from core._interfaces import IConfigs, ILogger, IMarkers, IPolicy


class BaseFSM:
    """
    Базовый каркас FSM.

    Этот каркас фиксирует:
    - текущее состояние
    - матрицу "state -> policies" (фиксированный порядок)
    - publish_state() как единый контракт наблюдаемости
    """

    def __init__(
        self,
        *,
        cfg: IConfigs,
        log: ILogger,
        markers: IMarkers,
        service_name: str,
        stage_gates: Mapping[StateEnum, Sequence[str]] | None = None,
        policy_matrix: Mapping[StateEnum, Sequence[IPolicy]] | None = None,
    ) -> None:
        self._cfg = cfg
        self._log = log
        self._markers = markers
        self._svc = service_name

        self._state: StateEnum = StateEnum.STARTING
        self._since_ms: int = self._now_ms()

        self._stage_gates: Dict[StateEnum, Sequence[str]] = dict(stage_gates or {})
        self._policy_matrix: Dict[StateEnum, Sequence[IPolicy]] = dict(policy_matrix or {})

        self._health: HealthSnapshotType = {
            "svc": self._svc,
            "version": "",
            "state": self._state,
            "ts_ms": self._now_ms(),
            "since_ts_ms": self._since_ms,
            "health": {},
            "details": {},
        }

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    # --- read-only accessors ---

    def get_state(self) -> StateEnum:
        return self._state

    def get_snapshot(self) -> HealthSnapshotType:
        return dict(self._health)

    # --- configuration hooks ---

    def set_stage_gates(self, gates: Mapping[StateEnum, Sequence[str]]) -> None:
        self._stage_gates = dict(gates)

    def set_policy_matrix(self, matrix: Mapping[StateEnum, Sequence[IPolicy]]) -> None:
        self._policy_matrix = dict(matrix)

    # --- helpers ---

    def stage_gates_missing(self, state: StateEnum) -> List[str]:
        req = list(self._stage_gates.get(state, ()) or ())
        missing = [m for m in req if not self._markers.has(m)]
        return missing

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
        - RETRY: прекращаем выполнение остальных политик и остаёмся в состоянии
        - FAIL: прекращаем и считаем ошибкой
        """
        for p in self._policy_matrix.get(state, ()) or ():
            r = p.run(state=state)
            status = r.get("status", PolicyStatusEnum.FAIL)
            if status == PolicyStatusEnum.OK:
                continue
            return status
        return PolicyStatusEnum.OK
