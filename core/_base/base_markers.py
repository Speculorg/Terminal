from __future__ import annotations
from pathlib import Path
from typing import Iterable

from core._interfaces import IFS, IMarkers


class BaseMarkers(IMarkers):
    """
    Базовый фасад маркеров.

    Контракт TERM-1 (канонический):
    - маркер = файл `<name>` в markers_dir (БЕЗ суффиксов)
    - операции идемпотентны
    - имя маркера должно быть переносимым на файловую систему
    """

    def __init__(self, fs: IFS, markers_dir: Path) -> None:
        self._fs = fs
        self._dir = Path(markers_dir)
        self._fs.ensure_dir(self._dir)

    @staticmethod
    def _norm(name: str) -> str:
        # legacy cleanup: allow passing "<name>.done" from old code/config
        n = (name or "").strip()
        while n.endswith(".done"):
            n = n[: -len(".done")]
        return n.replace("/", "_").strip()

    def _path(self, name: str) -> Path:
        safe = self._norm(name)
        return self._dir / safe

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
        for p in sorted(Path(self._dir).iterdir()):
            if not p.is_file():
                continue
            name = p.name
            if prefix and not name.startswith(prefix):
                continue
            out.append(name)
        return out
