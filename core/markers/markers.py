from __future__ import annotations

from pathlib import Path

from core._base import BaseMarkers
from core._entities import EventCodeEnum
from core._interfaces import IConfigs, IFS, ILogger


class Markers(BaseMarkers):
    """
    Markers — фасад маркеров (stage gates).

    Контракт TERM-1:
    - marker = файл <name> в markers_dir (без суффиксов)
    - операции идемпотентны
    - допускается legacy имя '<name>.done' на входе методов (нормализация)
    """

    def __init__(self, *, fs: IFS, markers_dir: Path) -> None:
        super().__init__(fs=fs, markers_dir=markers_dir)

    @classmethod
    def from_configs(cls, *, cfg: IConfigs, fs: IFS, log: ILogger | None = None) -> "Markers":
        markers_dir = Path(str(cfg.get("FS_MARKERS_DIR", "/fs/terminal/markers")))
        m = cls(fs=fs, markers_dir=markers_dir)

        if log is not None:
            log.event(
                EventCodeEnum.FS_ENSURE_LAYOUT,
                fields={
                    "markers_dir": str(markers_dir),
                    "markers_suffix": "",
                },
            )
        return m
