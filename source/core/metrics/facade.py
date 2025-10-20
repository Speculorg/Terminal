from __future__ import annotations
import threading
from typing import Dict, Tuple, Any, Optional, List, Mapping
from .names import ALLOWED_LABEL_KEYS, DEFAULT_BUCKETS_MS, CARDINALITY_LIMIT

def _escape(s: str) -> str:
    return s.replace('\\', r'\\').replace('\n', r'\n').replace('"', r'\"')

class _Counter:
    def __init__(self, name: str) -> None:
        self._name = name
        self._values: Dict[Tuple[Tuple[str,str], ...], float] = {}
    def inc(self, labels: Mapping[str,str], v: float = 1.0) -> None:
        key = tuple(sorted(labels.items()))
        self._values[key] = self._values.get(key, 0.0) + v
    def export(self) -> List[str]:
        lines = [f'# TYPE {self._name} counter']
        for labels, v in self._values.items():
            lbl = ",".join(f'{k}="{_escape(str(val))}"' for k, val in labels)
            lines.append(f'{self._name}{{{lbl}}} {v}')
        return lines

class _Gauge:
    def __init__(self, name: str) -> None:
        self._name = name
        self._values: Dict[Tuple[Tuple[str,str], ...], float] = {}
    def set(self, labels: Mapping[str,str], v: float) -> None:
        key = tuple(sorted(labels.items()))
        self._values[key] = v
    def export(self) -> List[str]:
        lines = [f'# TYPE {self._name} gauge']
        for labels, v in self._values.items():
            lbl = ",".join(f'{k}="{_escape(str(val))}"' for k, val in labels)
            lines.append(f'{self._name}{{{lbl}}} {v}')
        return lines

class _Histogram:
    def __init__(self, name: str, buckets_ms: List[int]) -> None:
        self._name = name
        self._b = sorted(buckets_ms)
        self._counts: Dict[Tuple[Tuple[str,str], ...], List[int]] = {}
        self._sums: Dict[Tuple[Tuple[str,str], ...], float] = {}
    def observe(self, labels: Mapping[str,str], value_ms: float) -> None:
        key = tuple(sorted(labels.items()))
        if key not in self._counts:
            self._counts[key] = [0]*(len(self._b)+1)  # +Inf bucket
            self._sums[key] = 0.0
        # find bucket
        idx = len(self._b)
        for i, le in enumerate(self._b):
            if value_ms <= le:
                idx = i
                break
        self._counts[key][idx] += 1
        self._sums[key] += value_ms
    def export(self) -> List[str]:
        lines = [f'# TYPE {self._name} histogram']
        for labels, counts in self._counts.items():
            base = ",".join(f'{k}="{_escape(str(val))}"' for k, val in labels)
            cumsum = 0
            for i, le in enumerate(self._b):
                cumsum += counts[i]
                lines.append(f'{self._name}_bucket{{{base},le="{le}"}} {cumsum}')
            cumsum += counts[-1]
            lines.append(f'{self._name}_bucket{{{base},le="+Inf"}} {cumsum}')
            lines.append(f'{self._name}_sum{{{base}}} {self._sums[labels]}')
            lines.append(f'{self._name}_count{{{base}}} {cumsum}')
        return lines

class Metrics:
    """Простой реестр метрик + экспорт в формате Prometheus."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._common_labels: Dict[str,str] = {}
        self._counters: Dict[str,_Counter] = {}
        self._gauges: Dict[str,_Gauge] = {}
        self._histograms: Dict[str,_Histogram] = {}

    # API
    def set_common_labels(self, labels: Mapping[str,str]) -> None:
        with self._lock:
            self._common_labels = {k: str(v) for k, v in labels.items() if k in ALLOWED_LABEL_KEYS}

    def inc_counter(self, name: str, labels: Mapping[str,str]) -> None:
        with self._lock:
            lbl = self._merge_labels(labels)
            self._get_counter(name).inc(lbl, 1.0)

    def set_gauge(self, name: str, value: float, labels: Mapping[str,str]) -> None:
        with self._lock:
            lbl = self._merge_labels(labels)
            self._get_gauge(name).set(lbl, float(value))

    def observe_histogram(self, name: str, value_ms: float, labels: Mapping[str,str]) -> None:
        with self._lock:
            lbl = self._merge_labels(labels)
            self._get_histogram(name).observe(lbl, float(value_ms))

    def export_prometheus(self) -> str:
        lines: List[str] = []
        with self._lock:
            for d in (self._counters, self._gauges, self._histograms):
                for obj in d.values():
                    lines.extend(obj.export())
        return "\n".join(lines) + "\n"

    # internals
    def _merge_labels(self, labels: Mapping[str,str]) -> Dict[str,str]:
        merged = dict(self._common_labels)
        for k, v in labels.items():
            if k in ALLOWED_LABEL_KEYS:
                merged[k] = str(v)
        # кардинальность контролируется на уровне вызывающего кода в ядре
        return merged

    def _get_counter(self, name: str) -> _Counter:
        if name not in self._counters:
            self._counters[name] = _Counter(name)
        return self._counters[name]

    def _get_gauge(self, name: str) -> _Gauge:
        if name not in self._gauges:
            self._gauges[name] = _Gauge(name)
        return self._gauges[name]

    def _get_histogram(self, name: str) -> _Histogram:
        if name not in self._histograms:
            self._histograms[name] = _Histogram(name, DEFAULT_BUCKETS_MS)
        return self._histograms[name]
