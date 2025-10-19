from __future__ import annotations
import tempfile, os
from .ops import safe_makedirs

class TempStore:
    def __init__(self, temp_dir: str) -> None:
        self._root = temp_dir
        safe_makedirs(self._root, 0o700)

    def mktemp(self, prefix: str = "tmp", suffix: str = "") -> str:
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=self._root)
        os.close(fd)
        return path

    def cleanup(self) -> None:
        pass  # P2
