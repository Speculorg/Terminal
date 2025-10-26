from __future__ import annotations
from typing import List


class DaemonPolicy:
    """Строит финальную команду старта демона на основе профиля и выбранного режима."""
    @staticmethod
    def build_start_cmd(run_profile, mode: str) -> List[str]:
        start_cmd = getattr(run_profile, "start_cmd", None) or {}
        if mode not in start_cmd:
            raise ValueError(f"start_cmd for mode '{mode}' not defined")
        cmd = start_cmd[mode]
        if not isinstance(cmd, (list, tuple)) or not cmd:
            raise ValueError("start_cmd must be a non-empty list[str]")
        return list(cmd)
