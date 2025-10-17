from __future__ import annotations
from typing import Protocol, runtime_checkable

@runtime_checkable
class IHealthCheck(Protocol):
    def is_healthy(self) -> bool: ...
