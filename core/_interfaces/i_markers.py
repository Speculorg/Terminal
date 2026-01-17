from __future__ import annotations
from typing import Protocol, runtime_checkable, Iterable


@runtime_checkable
class IMarkers(Protocol):
    """
    Порт маркеров (stage gates).
    Маркеры — устойчивые артефакты на FS, используемые для идемпотентного bootstrap.
    """

    def has(self, name: str) -> bool: ...
    def set(self, name: str) -> None: ...
    def delete(self, name: str) -> None: ...
    def list(self, *, prefix: str | None = None) -> Iterable[str]: ...
