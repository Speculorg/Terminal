from __future__ import annotations
from typing import Mapping
from core.metrics.facade import Metrics

class PromMetrics(Metrics):
    """Пока наследуем in-memory Metrics. Экспорт отдаётся как text."""
    def __init__(self) -> None:
        super().__init__()
