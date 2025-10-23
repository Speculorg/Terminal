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
        key = tuple(sorted((k,v) for k,v in labels.items() if k in ALLOWED_LABEL_KEYS))
        self._values[key] = self._values.get(key, 0.0) + float(v)

    def export(self) -> List[str]:
        lines: List[str] = []
        for labels, val in self._values.items():
            lbl = ",".join(f'{k}="{_escape(v)}"' for k,v in labels)
            lines.append(f"{self._name}{{{lbl}}} {val}")
        return lines

class _Gauge:
    def __init__(self, name: str) -> None:
        self._name = name
        self._values: Dict[Tuple[Tuple[str,str], ...], float] = {}

    def set(self, labels: Mapping[str,str], v: float) -> None:
        key = tuple(sorted((k,v) for k,v in labels.items() if k in ALLOWED_LABEL_KEYS))
        self._values[key] = float(v)

    def export(self) -> List[str]:
        lines: List[str] = []
        for labels, val in self._values.items():
            lbl = ",".join(f'{k}="{_escape(v)}"' for k,v in labels)
            lines.append(f"{self._name}{{{lbl}}} {val}")
        return lines

class _Histogram:
    def __init__(self, name: str, buckets: Tuple[int,...]) -> None:
        self._name = name
        self._buckets = buckets
        self._counts: Dict[Tuple[Tuple[str,str], ...], Dict[int,int]] = {}

    def observe(self, labels: Mapping[str,str], v_ms: float) -> None:
        key = tuple(sorted((k,v) for k,v in labels.items() if k in ALLOWED_LABEL_KEYS))
        bucket_counts = self._counts.setdefault(key, {b:0 for b in self._buckets})
        for b in self._buckets:
            if v_ms <= b:
                bucket_counts[b] += 1

    def export(self) -> List[str]:
        lines: List[str] = []
        for labels, counts in self._counts.items():
            for b, c in counts.items():
                lbl = ",".join(f'{k}="{_escape(v)}"' for k,v in labels) + f',le="{b}"'
                lines.append(f"{self._name}_bucket{{{lbl}}} {c}")
        return lines

class Metrics:
    def __init__(self, buckets_ms: Tuple[int,...] = DEFAULT_BUCKETS_MS) -> None:
        self._counters: Dict[str, _Counter] = {}
        self._gauges: Dict[str, _Gauge] = {}
        self._histograms: Dict[str, _Histogram] = {}
        self._buckets = buckets_ms

    # --- factories ---
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
        return "\\n".join(lines) + "\\n"
