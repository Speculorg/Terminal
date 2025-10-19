from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class MarkerName:
    svc: str
    name: str  # без суффикса .done
