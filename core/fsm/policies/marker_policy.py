from __future__ import annotations

from typing import Mapping, MutableMapping, Sequence

from core._base import BasePolicy
from core._entities import RunModeEnum, StateEnum
from core._interfaces import IMarkers


class MarkerPolicy(BasePolicy):
    """
    MarkerPolicy — единый механизм проверки stage_gates (маркеров) для состояния FSM.

    Семантика TERM-1:
    - Для StateEnum.INITIALIZING: stage_gates используется только для вычисления RunMode.
      Это не блокировка и не ожидание. Policy всегда возвращает OK и записывает run_mode в run_mode_ref.
    - Для остальных состояний: отсутствие хотя бы одного маркера => RETRY (ожидание).
    """

    def __init__(
        self,
        *,
        markers: IMarkers,
        stage_gates: Mapping[StateEnum, Sequence[str]],
        run_mode_ref: MutableMapping[str, object] | None = None,
    ) -> None:
        super().__init__("MarkerPolicy")
        self._markers = markers
        self._gates = dict(stage_gates)
        self._run_mode_ref = run_mode_ref if run_mode_ref is not None else {}

    def _run_impl(self, *, state: StateEnum):
        req = list(self._gates.get(state, ()) or ())

        # INITIALIZING: вычисляем RunMode по правилам, не блокируем.
        if state == StateEnum.INITIALIZING:
            run_mode, missing = self._calc_run_mode(req)
            self._run_mode_ref["run_mode"] = run_mode
            details: dict[str, object] = {"run_mode": run_mode.value, "gates": req}
            if missing:
                details["missing"] = missing
            return self.ok(details=details)

        # Остальные состояния: обычная блокировка по маркерам.
        if not req:
            return self.ok(details={"gates": []})

        missing = [m for m in req if not self._markers.has(m)]
        if missing:
            return self.retry(reason="missing_stage_gates", missing=missing)

        return self.ok(details={"gates": req})

    def _calc_run_mode(self, initializing_gates: list[str]) -> tuple[RunModeEnum, list[str]]:
        """
        Правила вычисления RunMode (TERM-1):
        - Если ключ INITIALIZING отсутствует в stage_gates -> RunMode.NORMAL (req=[]).
        - Если ключ INITIALIZING присутствует, но список пуст -> RunMode.NORMAL.
        - Если список непустой:
            - при отсутствии хотя бы одного маркера -> RunMode.FIRST;
            - при наличии всех маркеров -> RunMode.NORMAL.
        """
        if not initializing_gates:
            return (RunModeEnum.NORMAL, [])

        missing = [m for m in initializing_gates if not self._markers.has(m)]
        if missing:
            return (RunModeEnum.FIRST, missing)

        return (RunModeEnum.NORMAL, [])
