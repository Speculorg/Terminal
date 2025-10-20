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
        self._values[key] = self._values.get(key, 0.0) + float(v)

    def export(self) -> List[str]:
        out: List[str] = []
        for labels, val in self._values.items():
            lab = ','.join([f'{k}="{_escape(v)}"' for k,v in labels])
            out.append(f'{self._name}{{{lab}}} {val:.6f}')
        return out

class _Gauge:
    def __init__(self, name: str) -> None:
        self._name = name
        self._values: Dict[Tuple[Tuple[str,str], ...], float] = {}

    def set(self, labels: Mapping[str,str], v: float) -> None:
        key = tuple(sorted(labels.items()))
        self._values[key] = float(v)

    def export(self) -> List[str]:
        out: List[str] = []
        for labels, val in self._values.items():
            lab = ','.join([f'{k}="{_escape(v)}"' for k,v in labels])
            out.append(f'{self._name}{{{lab}}} {val:.6f}')
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
            values_sorted = sorted(values)
            lab_base = ','.join([f'{k}="{_escape(v)}"' for k,v in labels])
            count = 0
            for b in self._buckets:
                count = sum(1 for v in values_sorted if v <= b)
                out.append(f'{self._name}_bucket{{{lab_base},le="{b}"}} {count}')
            # +Inf
            out.append(f'{self._name}_bucket{{{lab_base},le="+Inf"}} {len(values_sorted)}')
            # sum and count
            out.append(f'{self._name}_sum{{{lab_base}}} {sum(values_sorted):.6f}')
            out.append(f'{self._name}_count{{{lab_base}}} {len(values_sorted)}')
        return out

class Metrics:
    """Минимальный реестр счётчиков/датчиков/гистограмм + экспорт в формате Prometheus."""
    def __init__(self) -> None:
        self._counters: Dict[str, _Counter] = {}
        self._gauges: Dict[str, _Gauge] = {}
        self._histograms: Dict[str, _Histogram] = {}
        self._allowed = set(ALLOWED_LABEL_KEYS)
        self._card_limit = CARDINALITY_LIMIT
        self._buckets = list(DEFAULT_BUCKETS_MS)

    # --- builders ---
    def counter(self, name: str) -> _Counter:
        return self._counters.setdefault(name, _Counter(name))

    def gauge(self, name: str) -> _Gauge:
        return self._gauges.setdefault(name, _Gauge(name))

    def histogram(self, name: str) -> _Histogram:
        return self._histograms.setdefault(name, _Histogram(name, self._buckets))

    # --- export ---
    def export_prometheus(self) -> str:
        lines: List[str] = []
        for reg in (self._counters, self._gauges, self._histograms):
            for obj in reg.values():
                lines.extend(obj.export())
        return "\n".join(lines) + "\n"
