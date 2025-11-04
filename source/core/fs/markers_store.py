from __future__ import annotations
import os, re

from .paths import Paths
from .ops import atomic_write_text


_VALID = re.compile(r"^[a-z0-9]+_[a-z0-9_]+\.done$", re.IGNORECASE)


class MarkersStore:

    def __init__(self, path: Paths) -> None:
        self._path = path

    def _dir(self) -> str:
        return self._path

    def path_for(self, svc: str, name: str) -> str:
        fname = f"{svc}_{name}.done"
        if not _VALID.match(fname):
            raise ValueError("invalid marker name")
        return os.path.join(self._dir(), fname)

    def create(self, svc: str, name: str, text: str = "") -> None:
        atomic_write_text(self.path_for(svc, name), text, mode=0o644)

    def delete(self, svc: str, name: str) -> None:
        try:
            os.remove(self.path_for(svc, name))
        except FileNotFoundError:
            pass

    def list(self, svc: str) -> list[str]:
        try:
            files = os.listdir(self._dir())
        except FileNotFoundError:
            files = []
        return [f for f in files if f.lower().startswith(f"{svc.lower()}_") and f.endswith(".done") and _VALID.match(f)]

    def require(self, required: set[str], svc: str) -> tuple[bool, set[str]]:
        have = set(self.list(svc))
        missing = required - have
        return (len(missing) == 0, missing)

    def list_all(self) -> list[str]:
        try:
            files = os.listdir(self._dir())
        except FileNotFoundError:
            files = []
        return [f for f in files if f.endswith(".done") and _VALID.match(f)]

    def exists(self, marker_name: str) -> bool:
        try:
            target = marker_name.strip().lower()
            allm = {m.lower() for m in self.list_all()}
            return target in allm
        except Exception:
            return False
