from __future__ import annotations
import threading
from typing import Dict, Tuple, Any, Optional, List
from core.metrics.names import (
    ALLOWED_LABEL_KEYS, DEFAULT_BUCKETS_MS, CARDINALITY_LIMIT
)

def _escape(s: str) -> str:
    return s.replace('\\', r'\\').replace('\n', r'\n').replace('"', r'\"')

class _Counter:
    def __init__(self, name: str, registry: "Metrics", *, help_text: str = "") -> None:
        self._name = name
        self._help = help_text
        self._reg = registry
        self._values: Dict[Tuple[Tuple[str,str], ...], float] = {}
        self._seen: set[Tuple[Tuple[str,str], ...]] = set()
        self._lock = threading.Lock()

    def inc(self, labels: Dict[str,str], value: float = 1.0) -> None:
        key = self._reg._normalize_labels(labels)
        with self._lock:
            if key not in self._seen and len(self._seen) >= CARDINALITY_LIMIT:
                return  # дроп из-за кардинальности
            self._seen.add(key)
            self._values[key] = self._values.get(key, 0.0) + float(value)

    def _export(self) -> List[str]:
        lines: List[str] = []
        if self._help:
            lines.append(f"# HELP {self._name} {_escape(self._help)}")
        lines.append(f"# TYPE {self._name} counter")
        with self._lock:
            for key, val in self._values.items():
                labels = ",".join([f"{k}=\"{_escape(v)}\"" for k,v in key])
                lines.append(f"{self._name}{{{labels}}} {val:.0f}")
        return lines

class _Gauge:
    def __init__(self, name: str, registry: "Metrics", *, help_text: str = "") -> None:
        self._name = name
        self._help = help_text
        self._reg = registry
        self._values: Dict[Tuple[Tuple[str,str], ...], float] = {}
        self._seen: set[Tuple[Tuple[str,str], ...]] = set()
        self._lock = threading.Lock()

    def set(self, labels: Dict[str,str], value: float) -> None:
        key = self._reg._normalize_labels(labels)
        with self._lock:
            if key not in self._seen and len(self._seen) >= CARDINALITY_LIMIT:
                return
            self._seen.add(key)
            self._values[key] = float(value)

    def _export(self) -> List[str]:
        lines: List[str] = []
        if self._help:
            lines.append(f"# HELP {self._name} {_escape(self._help)}")
        lines.append(f"# TYPE {self._name} gauge")
        with self._lock:
            for key, val in self._values.items():
                labels = ",".join([f"{k}=\"{_escape(v)}\"" for k,v in key])
                lines.append(f"{self._name}{{{labels}}} {val}")
        return lines

class _Histogram:
    def __init__(self, name: str, registry: "Metrics", *, buckets_ms: List[int] | None = None, help_text: str = "") -> None:
        self._name = name
        self._help = help_text
        self._reg = registry
        self._buckets = list(buckets_ms or DEFAULT_BUCKETS_MS)
        # Для каждого ключа: {le<=b: count, 'sum': s, 'count': c}
        self._values: Dict[Tuple[Tuple[str,str], ...], Dict[str, float]] = {}
        self._seen: set[Tuple[Tuple[str,str], ...]] = set()
        self._lock = threading.Lock()

    def _ensure_labelset(self, key: Tuple[Tuple[str,str], ...]) -> None:
        if key not in self._values:
            ds: Dict[str, float] = {f"le_{b}": 0.0 for b in self._buckets}
            ds["sum"] = 0.0
            ds["count"] = 0.0
            self._values[key] = ds

    def observe(self, labels: Dict[str,str], value_ms: float) -> None:
        key = self._reg._normalize_labels(labels)
        with self._lock:
            if key not in self._seen and len(self._seen) >= CARDINALITY_LIMIT:
                return
            self._seen.add(key)
            self._ensure_labelset(key)
            ds = self._values[key]
            ds["sum"] += float(value_ms)
            ds["count"] += 1.0
            for b in self._buckets:
                if value_ms <= b:
                    ds[f"le_{b}"] += 1.0
            # +inf bucket
            ds.setdefault("le_inf", 0.0)
            ds["le_inf"] += 1.0

    def _export(self) -> List[str]:
        lines: List[str] = []
        if self._help:
            lines.append(f"# HELP {self._name} {_escape(self._help)}")
        lines.append(f"# TYPE {self._name} histogram")
        with self._lock:
            for key, ds in self._values.items():
                labels_base = ",".join([f"{k}=\"{_escape(v)}\"" for k,v in key])
                running = 0.0
                for b in self._buckets:
                    running = ds[f"le_{b}"]
                    lines.append(f'{self._name}_bucket{{{labels_base},le="{b}"}} {running}')
                lines.append(f'{self._name}_bucket{{{labels_base},le="+Inf"}} {ds.get("le_inf", 0.0)}')
                lines.append(f"{self._name}_sum{{{labels_base}}} {ds['sum']}")
                lines.append(f"{self._name}_count{{{labels_base}}} {ds['count']}")
        return lines

class Metrics:
    """Потокобезопасный in-process регистр метрик с экспортом в формате Prometheus."""
    def __init__(self) -> None:
        self._common_labels: Dict[str,str] = {}
        self._counters: Dict[str, _Counter] = {}
        self._gauges: Dict[str, _Gauge] = {}
        self._histograms: Dict[str, _Histogram] = {}
        self._lock = threading.Lock()

    # --- API регистрации/инкрементов ---
    def set_common_labels(self, labels: Dict[str,str]) -> None:
        with self._lock:
            for k, v in labels.items():
                if k in ALLOWED_LABEL_KEYS:
                    self._common_labels[k] = str(v)

    def counter(self, name: str, *, help_text: str = "") -> _Counter:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = _Counter(name, self, help_text=help_text)
            return self._counters[name]

    def gauge(self, name: str, *, help_text: str = "") -> _Gauge:
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = _Gauge(name, self, help_text=help_text)
            return self._gauges[name]

    def histogram(self, name: str, *, buckets_ms: List[int] | None = None, help_text: str = "") -> _Histogram:
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = _Histogram(name, self, buckets_ms=buckets_ms, help_text=help_text)
            return self._histograms[name]

    # --- Совместимая обобщённая обёртка под IMetrics ---
    def inc_counter(self, name: str, labels: Dict[str,str], *, deadline_ms: int) -> None:
        self.counter(name).inc(labels)

    def set_gauge(self, name: str, value: float, labels: Dict[str,str], *, deadline_ms: int) -> None:
        self.gauge(name).set(labels, value)

    def observe_histogram(self, name: str, value_ms: float, labels: Dict[str,str], *, deadline_ms: int) -> None:
        self.histogram(name).observe(labels, value_ms)

    # --- Экспорт ---
    def export_prometheus(self) -> str:
        lines: List[str] = []
        for d in (self._counters, self._gauges, self._histograms):
            for obj in d.values():
                lines.extend(obj._export())
        return "\n".join(lines) + "\n"

    # --- нормализация ---
    def _normalize_labels(self, labels: Dict[str,str]) -> tuple[tuple[str,str], ...]:
        merged = dict(self._common_labels)
        for k, v in labels.items():
            if k in ALLOWED_LABEL_KEYS:
                merged[k] = str(v)
        return tuple(sorted(merged.items()))
