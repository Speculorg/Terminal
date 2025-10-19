from __future__ import annotations
from .ops import atomic_read_text, atomic_write_text, safe_makedirs

class CertsStore:
    def __init__(self, certs_dir: str) -> None:
        self._root = certs_dir

    def path(self, name: str) -> str:
        return f"{self._root}/{name}"

    def write_pem(self, name: str, text: str) -> None:
        safe_makedirs(self._root, 0o750)
        mode = 0o644 if name.endswith(".crt") or name.endswith(".pem") else 0o640
        atomic_write_text(self.path(name), text, mode=mode)

    def read_pem(self, name: str) -> str:
        return atomic_read_text(self.path(name))
