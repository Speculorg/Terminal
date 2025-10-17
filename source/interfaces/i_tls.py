from __future__ import annotations
from typing import Protocol, runtime_checkable, Iterable

@runtime_checkable
class ITLSReloader(Protocol):
    def reload(self) -> None: ...

@runtime_checkable
class ITLSWatch(Protocol):
    def start_watch(self, paths: Iterable[str], *, debounce_ms: int) -> None: ...

@runtime_checkable
class ITLSProbe(Protocol):
    def validate_chain(self, cert_path: str, fullchain_path: str, ca_path: str) -> None: ...
