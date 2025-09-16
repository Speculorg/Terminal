# source/core/metrics/registry.py

"""
Minimal in-process metrics with Prometheus text exposition format.
No external deps. Thread-safe updates. Use for counters/gauges in TERM-1.
"""

from __future__ import annotations
import threading
import time
from typing import Dict, Tuple, Mapping, Iterable


def _sanitize(name: str) -> str:
    # Prometheus metric name: [a-zA-Z_:][a-zA-Z0-9_:]*
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:"
    first_allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_:"
    s = "".join(ch if ch in allowed else "_" for ch in name)
    if not s:
        return "m_metric"
    if s[0] not in first_allowed:
        s = "m_" + s
    return s


def _labels_str(labels: Mapping[str, str] | None) -> str:
    if not labels:
        return ""
    items = [f'{k}="{v}"' for k, v in labels.items()]
    return "{" + ",".join(items) + "}"


class Counter:
    def __init__(self, name: str, help_text: str = "") -> None:
        self.name = _sanitize(name)
        self.help = help_text
        self._lock = threading.Lock()
        self._values: Dict[Tuple[Tuple[str, str], ...], float] = {}

    def inc(self, value: float = 1.0, labels: Mapping[str, str] | None = None) -> None:
        key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + float(value)

    def collect(self) -> Iterable[str]:
        yield f"# HELP {self.name} {self.help}"
        yield f"# TYPE {self.name} counter"
        with self._lock:
            for key, val in self._values.items():
                labels = _labels_str(dict(key))
                yield f"{self.name}{labels} {val}"


class Gauge:
    def __init__(self, name: str, help_text: str = "") -> None:
        self.name = _sanitize(name)
        self.help = help_text
        self._lock = threading.Lock()
        self._values: Dict[Tuple[Tuple[str, str], ...], float] = {}

    def set(self, value: float, labels: Mapping[str, str] | None = None) -> None:
        key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._values[key] = float(value)

    def add(self, delta: float, labels: Mapping[str, str] | None = None) -> None:
        key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + float(delta)

    def collect(self) -> Iterable[str]:
        yield f"# HELP {self.name} {self.help}"
        yield f"# TYPE {self.name} gauge"
        with self._lock:
            for key, val in self._values.items():
                labels = _labels_str(dict(key))
                yield f"{self.name}{labels} {val}"


class Registry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics: Dict[str, object] = {}

    def register(self, metric: object) -> object:
        with self._lock:
            # keep last writer wins (idempotent for same object)
            self._metrics[getattr(metric, "name", f"m_{len(self._metrics)}")] = metric
            return metric

    def counter(self, name: str, help_text: str = "") -> Counter:
        c = Counter(name, help_text)
        return self.register(c)  # type: ignore[return-value]

    def gauge(self, name: str, help_text: str = "") -> Gauge:
        g = Gauge(name, help_text)
        return self.register(g)  # type: ignore[return-value]

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            items = list(self._metrics.values())
        for m in items:
            if hasattr(m, "collect"):
                lines.extend(list(m.collect()))
        # Add scrape timestamp sample (optional)
        lines.append(f"# SCRAPE_TIME {int(time.time())}")
        return "\n".join(lines) + "\n"


# Module-level singleton (simple and sufficient for TERM-1)
_default_registry = Registry()

def registry() -> Registry:
    return _default_registry
