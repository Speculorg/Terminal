from __future__ import annotations

from pathlib import Path

from core._base import BaseMarkers
from core._entities import EventCodeEnum
from core._interfaces import IConfigs, IFS, ILogger


class Markers(BaseMarkers):
    """
    Markers — фасад маркеров (stage gates).

    Контракт:
    - marker = файл <name>.done в markers_dir
    - операции идемпотентны
    
    """

    def __init__(self, *, fs: IFS, markers_dir: Path, suffix: str = ".done") -> None:
        super().__init__(fs=fs, markers_dir=markers_dir, suffix=suffix)

    @classmethod
    def from_configs(cls, *, cfg: IConfigs, fs: IFS, log: ILogger | None = None) -> "Markers":
        # Источник: env/Configs (TERM-1)
        # Стабильные ключи: FS_MARKERS_DIR, MARKERS_SUFFIX
        markers_dir = Path(str(cfg.get("FS_MARKERS_DIR", "/fs/terminal/markers")))
        suffix = str(cfg.get("MARKERS_SUFFIX", ".done"))

        m = cls(fs=fs, markers_dir=markers_dir, suffix=suffix)

        if log is not None:
            log.event(
                EventCodeEnum.FS_ENSURE_LAYOUT,
                fields={
                    "markers_dir": str(markers_dir),
                    "markers_suffix": suffix,
                },
            )

        return m

    # (опционально) удобные события — без изменения базовой семантики

    def set(self, name: str) -> None:
        super().set(name)

    def delete(self, name: str) -> None:
        super().delete(name)
