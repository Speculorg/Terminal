from __future__ import annotations
import re
from typing import Set, Tuple, List

from interfaces.i_markers import IMarkers

_VALID = re.compile(r"^[a-z0-9]+_[a-z0-9_]+\.done$")

class BaseMarkers(IMarkers):
    """Базовый каркас фасада маркеров.
    Реализует валидацию имени и базовую логику require()/list(prefix).
    Конкретные операции чтения/записи определяются в наследнике.
    """
    def _validate(self, name: str) -> str:
        n = (name or "").strip()
        if not _VALID.match(n):
            raise ValueError(f"invalid marker name: {name!r}")
        return n

    def exists(self, name: str) -> bool:
        raise NotImplementedError

    def set(self, name: str, payload: str | None = None) -> None:
        raise NotImplementedError

    def delete(self, name: str) -> None:
        raise NotImplementedError

    def list(self, prefix: str | None = None) -> list[str]:
        items = self._list_all()
        if prefix:
            pre = prefix.strip().lower()
            items = [m for m in items if m.lower().startswith(pre)]
        return sorted(items)

    def require(self, required: Set[str]) -> Tuple[bool, Set[str]]:
        req = set(required or [])
        if not req:
            return True, set()
        missing = {m for m in req if not self.exists(m)}
        return (len(missing) == 0, missing)

    def _list_all(self) -> list[str]:
        raise NotImplementedError
