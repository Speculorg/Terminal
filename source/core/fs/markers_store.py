from __future__ import annotations
import os
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
        d = self._paths.svc_markers_dir(svc)
        safe_makedirs(d, 0o755)
        text = "" if payload is None else str(payload)
        atomic_write_text(self.path_for(svc, name), text, mode=0o644)

    def delete(self, svc: str, name: str) -> None:
        remove(self.path_for(svc, name))

    def list(self, svc: str) -> list[str]:
        d = self._paths.svc_markers_dir(svc)
        files = listdir(d)
        return [f[:-5] for f in files if f.endswith(".done")]

    def require(self, required: set[str], svc: str) -> tuple[bool, set[str]]:
        have = set(self.list(svc))
        missing = required - have
        return len(missing) == 0, missing
