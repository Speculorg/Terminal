from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from interfaces import IMetrics

@dataclass
class BaseMetrics:
    """Тонкий прокси над IMetrics без deadline-параметров."""
    metrics: IMetrics

    def inc_counter(self, name: str, labels: Mapping[str, str]) -> None:
        self.metrics.inc_counter(name, labels)

    def set_gauge(self, name: str, value: float, labels: Mapping[str, str]) -> None:
        self.metrics.set_gauge(name, value, labels)

    def observe_histogram(self, name: str, value_ms: float, labels: Mapping[str, str]) -> None:
        self.metrics.observe_histogram(name, value_ms, labels)
