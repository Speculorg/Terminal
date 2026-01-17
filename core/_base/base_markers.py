from __future__ import annotations
from pathlib import Path
from typing import Iterable

from _interfaces import IFS, IMarkers


class BaseMarkers(IMarkers):
    """
    Базовый фасад маркеров.

    Контракт:
    - маркер = файл `<name>.done`
    - операции должны быть идемпотентны
    """

    def __init__(self, fs: IFS, markers_dir: Path, *, suffix: str = ".done") -> None:
        self._fs = fs
        self._dir = Path(markers_dir)
        self._suffix = suffix
        self._fs.ensure_dir(self._dir)

    def _path(self, name: str) -> Path:
        safe = name.strip().replace("/", "_")
        return self._dir / f"{safe}{self._suffix}"

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
        for p in sorted(Path(self._dir).glob(f"*{self._suffix}")):
            name = p.name[: -len(self._suffix)]
            if prefix and not name.startswith(prefix):
                continue
            out.append(name)
        return out
