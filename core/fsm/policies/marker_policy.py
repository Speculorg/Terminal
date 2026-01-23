from __future__ import annotations

from typing import Mapping, Sequence

from core._base import BasePolicy
from core._entities import StateEnum
from core._interfaces import IMarkers


class MarkerPolicy(BasePolicy):
    """
    MarkerPolicy проверяет наличие stage gates (маркеров) для текущего состояния.

    Важно:
    - Это "простая блокировка" перехода.
    - Не создаёт маркеры автоматически (создание — ответственность bootstrap-политик).
    """

    def __init__(self, *, markers: IMarkers, stage_gates: Mapping[StateEnum, Sequence[str]]) -> None:
        super().__init__("MarkerPolicy")
        self._markers = markers
        self._gates = dict(stage_gates)

    def _run_impl(self, *, state: StateEnum):
        req = list(self._gates.get(state, ()) or ())
        if not req:
            return self.ok(details={"gates": []})

        missing = [m for m in req if not self._markers.has(m)]
        if missing:
            return self.retry(reason="missing_stage_gates", missing=missing)

        return self.ok(details={"gates": req})
