from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from interfaces import IMetrics

@dataclass
class BaseMetrics:
    """Тонкий прокси над IMetrics."""
    metrics: IMetrics

    def inc_counter(self, name: str, labels: Mapping[str, str], *, deadline_ms: int) -> None:
        self.metrics.inc_counter(name, labels, deadline_ms=deadline_ms)

    def set_gauge(self, name: str, value: float, labels: Mapping[str, str], *, deadline_ms: int) -> None:
        self.metrics.set_gauge(name, value, labels, deadline_ms=deadline_ms)

    def observe_histogram(self, name: str, value_ms: float, labels: Mapping[str, str], *, deadline_ms: int) -> None:
        self.metrics.observe_histogram(name, value_ms, labels, deadline_ms=deadline_ms)
