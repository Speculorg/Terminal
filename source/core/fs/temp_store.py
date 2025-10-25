from __future__ import annotations
import tempfile, os
from .ops import safe_makedirs

class TempStore:
    def __init__(self, temp_dir: str) -> None:
        self._root = temp_dir
        safe_makedirs(self._root, 0o700)

    def cleanup(self) -> None:
        pass  # P2
