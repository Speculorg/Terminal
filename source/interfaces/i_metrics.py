from __future__ import annotations
from typing import Protocol, runtime_checkable, Mapping

LabelMap = Mapping[str, str]

@runtime_checkable
class IMetrics(Protocol):
    """Минимальный контракт: счётчики, гейджи, гистограммы.
    Все методы принимают именованный параметр deadline_ms.
    """
    def inc_counter(self, name: str, labels: LabelMap, *, deadline_ms: int) -> None: ...
    def set_gauge(self, name: str, value: float, labels: LabelMap, *, deadline_ms: int) -> None: ...
    def observe_histogram(self, name: str, value_ms: float, labels: LabelMap, *, deadline_ms: int) -> None: ...
