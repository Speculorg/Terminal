from __future__ import annotations
import tempfile, os
from .ops import safe_makedirs

class TempStore:
    def __init__(self, path: str) -> None:
        self._path = path
        safe_makedirs(self._path, 0o700)

    def cleanup(self) -> None:
        pass  # P2
