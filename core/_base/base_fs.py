from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from core._interfaces import IFS


class BaseFS(IFS):
    """
    Базовый фасад FS.

    Инварианты:
    - Все пути относительны fs_root (абсолютный Path).
    - Запись "атомарная": tmp -> os.replace().
    """

    def __init__(self, fs_root: Path) -> None:
        self._root = Path(fs_root).resolve()

    def p(self, *parts: str) -> Path:
        return (self._root.joinpath(*parts)).resolve()

    def exists(self, path: Path) -> bool:
        return Path(path).exists()

    def ensure_dir(self, path: Path, *, mode: int = 0o750) -> None:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(p, mode)
        except PermissionError:
            # chmod может быть запрещён (например, на некоторых FS/контейнерах)
            pass

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        return Path(path).read_text(encoding=encoding)

    def write_text_atomic(self, path: Path, data: str, *, encoding: str = "utf-8", mode: int = 0o640) -> None:
        b = data.encode(encoding)
        self.write_bytes_atomic(path, b, mode=mode)

    def read_bytes(self, path: Path) -> bytes:
        return Path(path).read_bytes()

    def write_bytes_atomic(self, path: Path, data: bytes, *, mode: int = 0o640) -> None:
        dst = Path(path)
        self.ensure_dir(dst.parent)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{dst.name}.", dir=str(dst.parent))
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            try:
                os.chmod(tmp, mode)
            except PermissionError:
                pass
            os.replace(str(tmp), str(dst))
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass

    def read_json(self, path: Path) -> dict[str, Any]:
        raw = self.read_text(path)
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("JSON root must be an object")
        return obj

    def write_json_atomic(self, path: Path, data: dict[str, Any], *, mode: int = 0o640) -> None:
        raw = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
        self.write_text_atomic(path, raw + "\n", mode=mode)
