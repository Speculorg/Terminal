from __future__ import annotations
from typing import Optional, List
from base.base_marker import BaseMarker
from interfaces import IConfigs
from core.fs import FS

class Markers(BaseMarker):
    """Фасад маркеров поверх FS с плоскими именами."""
    def __init__(self, cfg: IConfigs, fs: Optional[FS] = None) -> None:
        self._cfg = cfg
        self._fs = fs or FS(cfg)

    def exists(self, name: str) -> bool:
        n = self._validate(name)
        try:
            return self._fs.markers.exists(n)
        except Exception:
            return False

    def set(self, name: str, payload: str | None = None) -> None:
        n = self._validate(name)
        svc = n.split("_", 1)[0]
        short = n[len(svc)+1:]
        try:
            self._fs.markers.set(svc, short, payload)
        except Exception:
            path = self._fs.markers.path_for(svc, short)
            text = payload if payload is not None else ""
            self._fs.atomic_write_text(path, text, mode=0o644)

    def delete(self, name: str) -> None:
        n = self._validate(name)
        svc = n.split("_", 1)[0]
        short = n[len(svc)+1:]
        try:
            self._fs.markers.delete(svc, short)
        except Exception:
            path = self._fs.markers.path_for(svc, short)
            try:
                self._fs.remove(path)
            except Exception:
                pass

    def list(self, prefix: str | None = None) -> list[str]:
        items = self._list_all()
        if prefix:
            pre = (prefix or "").strip().lower()
            items = [m for m in items if m.lower().startswith(pre)]
        return sorted(items)

    def _list_all(self) -> list[str]:
        try:
            return self._fs.markers.list_all()
        except Exception:
            return []
