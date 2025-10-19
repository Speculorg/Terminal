from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Paths:
    """Справочник путей локального тома согласно плану.
    Маркеры всегда в `fs/markers`. Секреты и сертификаты берутся из cfg.
    """
    fs_root: str = "fs"
    markers_root: str = "fs/markers"
    secrets_dir: str = "fs/secrets"
    certs_dir: str = "fs/certs"
    tmp_dir: str = "fs/tmp"

    def svc_markers_dir(self, svc: str) -> str:
        return f"{self.markers_root}/{svc}"

    def marker_file(self, svc: str, name: str) -> str:
        return f"{self.svc_markers_dir(svc)}/{name}.done"

    def ensure_relative(self, path: str) -> str:
        # простая защита от абсолютных путей
        if path.startswith('/'):
            raise ValueError("absolute paths are not allowed in FS facade")
        return path
