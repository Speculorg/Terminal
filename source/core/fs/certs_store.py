from __future__ import annotations
from .ops import atomic_read_text, atomic_write_text, safe_makedirs

class CertsStore:

    def __init__(self, path: str) -> None:
        self._path = path

    def path(self, name: str) -> str:
        return f"{self._path}/{name}"

    def write_pem(self, name: str, text: str, mode: int = 0o644) -> None:
        safe_makedirs(self._path, 0o755)
        atomic_write_text(self.path(name), text, mode=mode)

    def read_pem(self, name: str, encoding: str = "utf-8") -> str:
        return atomic_read_text(self.path(name), encoding=encoding)
