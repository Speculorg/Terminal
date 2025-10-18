"""TERM-1 Stage 5: core.metrics (реестр метрик)."""
from .facade import Metrics
from . import names as metric_names
__all__ = ["Metrics", "metric_names"]
