from __future__ import annotations
from typing import Set
from entities.run_mode_enum import RunModeEnum

class MarkerPolicy:
    @staticmethod
    def detect_run_mode(required_markers: Set[str], markers) -> RunModeEnum:
        if not required_markers:
            return RunModeEnum.NORMAL
        found = sum(1 for m in required_markers if markers.exists(m))
        if found == 0:
            return RunModeEnum.FIRST
        if found < len(required_markers):
            return RunModeEnum.RECOVERY
        return RunModeEnum.NORMAL
