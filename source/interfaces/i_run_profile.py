from __future__ import annotations
from typing import Protocol, runtime_checkable, Set

@runtime_checkable
class IRunProfile(Protocol):
    @property
    def required_markers(self) -> Set[str]: ...
