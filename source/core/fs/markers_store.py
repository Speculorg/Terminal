from __future__ import annotations
import time, os
from .paths import Paths
from .ops import safe_makedirs, atomic_write_text, listdir, remove

class MarkersStore:
    def __init__(self, paths: Paths | None = None) -> None:
        self._paths = paths or Paths()

    def path_for(self, svc: str, name: str) -> str:
        return self._paths.marker_file(svc, name)

    def exists(self, svc: str, name: str) -> bool:
        return os.path.exists(self.path_for(svc, name))

    def set(self, svc: str, name: str, payload: str | None = None) -> None:
        dir_path = self._paths.svc_markers_dir(svc)
        safe_makedirs(dir_path, 0o755)
        ts = int(time.time())
        body = payload if payload is not None else f"{ts}\n"
        atomic_write_text(self.path_for(svc, name), body, mode=0o644)

    def delete(self, svc: str, name: str) -> None:
        remove(self.path_for(svc, name))

    def list(self, svc: str) -> list[str]:
        dir_path = self._paths.svc_markers_dir(svc)
        return [f for f in listdir(dir_path) if f.endswith(".done")]

    def require(self, required: set[str], svc: str) -> tuple[bool, set[str]]:
        missing: set[str] = set()
        for r in required:
            if not self.exists(svc, r):
                missing.add(r)
        return (len(missing) == 0), missing
