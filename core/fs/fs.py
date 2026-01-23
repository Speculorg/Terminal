from __future__ import annotations

from pathlib import Path

from core._base import BaseFS
from core._entities import EventCodeEnum
from core._interfaces import IConfigs, ILogger


class FS(BaseFS):
    """
    FS — фасад файловой системы Core.

    Контракт:
    - единый root (по умолчанию /fs/terminal)
    - обязательные директории: markers, secrets, certs, tmp
    
    """

    def __init__(self, fs_root: Path) -> None:
        super().__init__(fs_root=fs_root)

    @classmethod
    def from_configs(cls, *, cfg: IConfigs, log: ILogger | None = None) -> "FS":
        fs_root = Path(str(cfg.get("FS_ROOT", "/fs/terminal")))
        fs = cls(fs_root=fs_root)

        # Обязательные директории TERM-1
        markers_dir = Path(str(cfg.get("FS_MARKERS_DIR", str(fs.p("markers")))))
        secrets_dir = Path(str(cfg.get("FS_SECRETS_DIR", str(fs.p("secrets")))))
        certs_dir = Path(str(cfg.get("FS_CERTS_DIR", str(fs.p("certs")))))
        tmp_dir = Path(str(cfg.get("FS_TMP_DIR", str(fs.p("tmp")))))

        fs.ensure_dir(fs_root)
        fs.ensure_dir(markers_dir)
        fs.ensure_dir(secrets_dir)
        fs.ensure_dir(certs_dir)
        fs.ensure_dir(tmp_dir)

        if log is not None:
            log.event(
                EventCodeEnum.FS_ENSURE_LAYOUT,
                fields={
                    "fs_root": str(fs_root),
                    "markers_dir": str(markers_dir),
                    "secrets_dir": str(secrets_dir),
                    "certs_dir": str(certs_dir),
                    "tmp_dir": str(tmp_dir),
                },
            )

        return fs
