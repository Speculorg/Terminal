from __future__ import annotations
from typing import Protocol, runtime_checkable, Set, Dict, Tuple

@runtime_checkable
class IRunProfile(Protocol):
    required_markers: Set[str] | None
    stage_gates: Dict | None
