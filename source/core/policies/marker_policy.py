from __future__ import annotations
from typing import Set
from entities.run_mode_enum import RunModeEnum

class MarkerPolicy:
    @staticmethod
    def detect_run_mode(required_markers: Set[str], markers, *, svc: str) -> RunModeEnum:
        """Определяет режим запуска по наличию обязательных маркеров.
        required_markers: имена файлов маркеров без пути и svc.
        svc: имя сервиса (cfg.context.name).
        """
        if not required_markers:
            return RunModeEnum.NORMAL
        ok, missing = markers.require(required_markers, svc=svc)
        if ok:
            return RunModeEnum.NORMAL
        # Частичный набор → RECOVERY, отсутствие всех → FIRST
        if len(missing) == len(required_markers):
            return RunModeEnum.FIRST
        return RunModeEnum.RECOVERY
