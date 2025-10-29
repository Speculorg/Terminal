from __future__ import annotations
from typing import Dict, Iterable, List, Sequence, Tuple, Set, Optional

from entities import StateEnum

class BaseFSM:
    """Базовый каркас FSM. Централизует проверку stage-gates перед входом в состояние."""
    def __init__(self, cfg, logger, markers):
        self.cfg = cfg
        self.logger = logger
        self.markers = markers
        self.svc: Optional[str] = None
        self.required_markers: Set[str] = set()
        # Dict[StateEnum, Sequence[Tuple[svc, marker]|str]]
        self.stage_gates: Dict[StateEnum, Sequence] = {}

    def _flat_gate_names(self, items: Sequence) -> List[str]:
        names: List[str] = []
        for it in items or ():
            if isinstance(it, tuple) and len(it) == 2:
                names.append(it[1])
            else:
                names.append(str(it))
        return names

    def precheck_stage_gates(self, state: StateEnum) -> Tuple[bool, List[str]]:
        """Возвращает (ok, missing). Применяется до on_enter(state)."""
        req_seq = self.stage_gates.get(state, ()) or ()
        req = self._flat_gate_names(req_seq)
        missing = [m for m in req if not self.markers.exists(m)]
        return (len(missing) == 0, missing)
