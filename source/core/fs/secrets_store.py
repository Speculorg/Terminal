from __future__ import annotations
from .ops import atomic_read, atomic_read_text, atomic_write, atomic_write_text, safe_makedirs

class SecretsStore:
    
    def __init__(self, path: str) -> None:
        self._root = path

    def path(self, name: str) -> str:
        return f"{self._root}/{name}"

    def read(self, name: str) -> bytes:
        return atomic_read(self.path(name))

    def read_text(self, name: str, encoding: str = "utf-8") -> str:
        return atomic_read_text(self.path(name), encoding=encoding)

    def write(self, name: str, data: bytes, mode: int = 0o600) -> None:
        safe_makedirs(self._root, 0o700)
        atomic_write(self.path(name), data, mode=mode)

    def write_text(self, name: str, text: str, mode: int = 0o600, encoding: str = "utf-8") -> None:
        safe_makedirs(self._root, 0o700)
        atomic_write_text(self.path(name), text, mode=mode, encoding=encoding)
