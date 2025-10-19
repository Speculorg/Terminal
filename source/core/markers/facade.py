from __future__ import annotations
from interfaces.i_marker import IMarker
from core.fs import FS

class Markers(IMarker):
    """Фасад маркеров поверх FS."""
    def __init__(self, cfg=None, fs: FS | None = None) -> None:
        self._fs = fs or FS(cfg)

    def path_for(self, svc: str, name: str) -> str:
        return self._fs.markers.path_for(svc, name)

    def exists(self, svc: str, name: str) -> bool:
        return self._fs.markers.exists(svc, name)

    def set(self, svc: str, name: str, payload: str | None = None) -> None:
        self._fs.markers.set(svc, name, payload=payload)

    def delete(self, svc: str, name: str) -> None:
        self._fs.markers.delete(svc, name)

    def list(self, svc: str) -> list[str]:
        return self._fs.markers.list(svc)

    def require(self, required: set[str], svc: str) -> tuple[bool, set[str]]:
        return self._fs.markers.require(required, svc)
