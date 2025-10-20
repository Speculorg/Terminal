from __future__ import annotations
from typing import Protocol, runtime_checkable, Mapping

LabelMap = Mapping[str, str]

@runtime_checkable
class IMetrics(Protocol):
    """Минимальный контракт: счётчики, гейджи, гистограммы."""
    def inc_counter(self, name: str, labels: LabelMap) -> None: ...
    def set_gauge(self, name: str, value: float, labels: LabelMap) -> None: ...
    def observe_histogram(self, name: str, value_ms: float, labels: LabelMap) -> None: ...
