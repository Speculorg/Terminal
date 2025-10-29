
from __future__ import annotations
from typing import Iterable, Set, Tuple, Dict, Optional
from entities.state_enum import StateEnum

class MarkerPolicy:
    """
    Политика маркеров: только проверки и решения. Файлы не создает.
    """

    @staticmethod
    def check_required(logger, svc: str, markers, required: Optional[Iterable[str]]) -> bool:
        req = set(required or [])
        if not req:
            return True
        missing = sorted([m for m in req if not markers.exists(m)])
        if missing:
            logger.info("service.start.precondition", svc=svc, details={"missing": missing})
            return False
        return True

    @staticmethod
    def gates_for_state(profile, state: StateEnum) -> Set[str]:
        sg = getattr(profile, "stage_gates", None) or {}
        return set(sg.get(state, set()))

    @staticmethod
    def decide_initial_mode(profile, markers) -> str:
        # https, если гейты SECURING присутствуют
        need = MarkerPolicy.gates_for_state(profile, StateEnum.SECURING)
        ready = all(markers.exists(m) for m in need) if need else False
        return "https" if ready else "http"
