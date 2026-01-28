from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core._interfaces import IFS, IMarkers


class BaseMarkers(IMarkers):
    """
    Базовый фасад маркеров.

    TERM-1 контракт:
    - маркер = файл `<name>` в markers_dir (без суффиксов)
    - операции идемпотентны
    - допускается входное имя `<name>.done` как legacy (нормализация имени)
    """

    LEGACY_SUFFIX = ".done"

    def __init__(self, fs: IFS, markers_dir: Path) -> None:
        self._fs = fs
        self._dir = Path(markers_dir)
        self._fs.ensure_dir(self._dir)

    @classmethod
    def _norm(cls, name: str) -> str:
        safe = (name or "").strip().replace("/", "_")
        if safe.endswith(cls.LEGACY_SUFFIX):
            safe = safe[: -len(cls.LEGACY_SUFFIX)]
        return safe

    def _path(self, name: str) -> Path:
        return self._dir / self._norm(name)

    def has(self, name: str) -> bool:
        return self._fs.exists(self._path(name))

    def set(self, name: str) -> None:
        p = self._path(name)
        if self._fs.exists(p):
            return
        self._fs.write_text_atomic(p, "done\n")

    def delete(self, name: str) -> None:
        p = self._path(name)
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            # любые ошибки удаления не должны валить процесс на этом уровне
            pass

    def list(self, *, prefix: str | None = None) -> Iterable[str]:
        if not Path(self._dir).exists():
            return ()
        out: list[str] = []
        for p in sorted(Path(self._dir).glob("*")):
            if not p.is_file():
                continue
            name = p.name
            if prefix and not name.startswith(prefix):
                continue
            out.append(name)
        return out
