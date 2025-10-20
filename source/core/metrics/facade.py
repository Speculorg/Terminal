from __future__ import annotations
from typing import Dict, Tuple, Any, Optional, List, Mapping
from .names import ALLOWED_LABEL_KEYS, DEFAULT_BUCKETS_MS, CARDINALITY_LIMIT

LabelMap = Mapping[str, str]

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
        out = [f"# TYPE {self._name} counter"]
        for labels, v in self._values.items():
            lbl = ",".join([f'{k}="{_escape(val)}"' for k, val in labels])
            out.append(f"{self._name}{{{lbl}}} {v}")
        return out

class _Gauge:
    def __init__(self, name: str) -> None:
        self._name = name
        self._values: Dict[Tuple[Tuple[str,str], ...], float] = {}

    def set(self, labels: Mapping[str,str], v: float) -> None:
        key = tuple(sorted(labels.items()))
        self._values[key] = float(v)

    def export(self) -> List[str]:
        out = [f"# TYPE {self._name} gauge"]
        for labels, v in self._values.items():
            lbl = ",".join([f'{k}="{_escape(val)}"' for k, val in labels])
            out.append(f"{self._name}{{{lbl}}} {v}")
        return out

class _Histogram:
    def __init__(self, name: str, buckets: List[int]) -> None:
        self._name = name
        self._buckets = list(buckets)
        self._values: Dict[Tuple[Tuple[str,str], ...], List[float]] = {}

    def observe(self, labels: Mapping[str,str], v_ms: float) -> None:
        key = tuple(sorted(labels.items()))
        self._values.setdefault(key, []).append(float(v_ms))

    def export(self) -> List[str]:
        out: List[str] = []
        for labels, values in self._values.items():
            counts = []
            for b in self._buckets:
                counts.append(sum(1 for v in values if v <= b))
            # buckets
            for b, c in zip(self._buckets, counts):
                lbl = ",".join([f'{k}="{_escape(val)}"' for k, val in labels] + [f'le="{b}"'])
                out.append(f"{self._name}_bucket{{{lbl}}} {c}")
            # +Inf
            lbl_inf = ",".join([f'{k}="{_escape(val)}"' for k, val in labels] + ['le="+Inf"'])
            out.append(f"{self._name}_bucket{{{lbl_inf}}} {len(values)}")
            # sum and count
            lbl_base = ",".join([f'{k}="{_escape(val)}"' for k, val in labels])
            out.append(f"{self._name}_sum{{{lbl_base}}} {sum(values)}")
            out.append(f"{self._name}_count{{{lbl_base}}} {len(values)}")
        return out

class Metrics:
    """Встроенный реестр метрик. Без внешних зависимостей."""
    def __init__(self) -> None:
        self._counters: Dict[str, _Counter] = {}
        self._gauges: Dict[str, _Gauge] = {}
        self._histograms: Dict[str, _Histogram] = {}
        # Ограничение кардинальности обеспечивается на уровне клиентов (см. adapters)

    # User API
    def inc_counter(self, name: str, labels: LabelMap) -> None:
        self._validate_labels(labels)
        self._get_counter(name).inc(labels)

    def set_gauge(self, name: str, value: float, labels: LabelMap) -> None:
        self._validate_labels(labels)
        self._get_gauge(name).set(labels, value)

    def observe_histogram(self, name: str, value_ms: float, labels: LabelMap) -> None:
        self._validate_labels(labels)
        self._get_histogram(name).observe(labels, value_ms)

    # Export
    def export_prometheus(self) -> str:
        lines: List[str] = []
        for c in self._counters.values():
            lines.extend(c.export())
        for g in self._gauges.values():
            lines.extend(g.export())
        for h in self._histograms.values():
            lines.extend(h.export())
        return "\n".join(lines) + "\n"

    # Internals
    def _validate_labels(self, labels: LabelMap) -> None:
        for k in labels.keys():
            if k not in ALLOWED_LABEL_KEYS:
                raise ValueError(f"label '{k}' is not allowed")

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
