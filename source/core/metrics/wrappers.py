from __future__ import annotations
from typing import Any
from time import monotonic
from core.metrics.facade import Metrics
from core.metrics.names import (
    KV_COUNTER, KV_HISTOGRAM, REG_COUNTER, REG_HISTOGRAM, NET_COUNTER, NET_HISTOGRAM,
    RESULT_DONE, RESULT_ERR
)

def _wrap_calls(domain: str, obj: Any, metrics: Metrics, svc: str):
    if domain == "kv":
        counter = metrics.counter(KV_COUNTER, help_text="KV operations result counter")
        hist = metrics.histogram(KV_HISTOGRAM, help_text="KV operations latency (ms)")
        ops = {"get", "put", "cas"}
    elif domain == "registrar":
        counter = metrics.counter(REG_COUNTER, help_text="Registrar operations result counter")
        hist = metrics.histogram(REG_HISTOGRAM, help_text="Registrar operations latency (ms)")
        ops = {"register", "deregister", "heartbeat"}
    elif domain == "net":
        counter = metrics.counter(NET_COUNTER, help_text="Net operations result counter")
        hist = metrics.histogram(NET_HISTOGRAM, help_text="Net operations latency (ms)")
        ops = {"wait_port", "probe_http", "probe_https"}
    else:
        raise ValueError("unknown domain: " + domain)

    class _Proxy:
        def __init__(self, inner: Any):
            self._inner = inner

        def __getattr__(self, name: str):
            attr = getattr(self._inner, name)
            if name in ops and callable(attr):
                def _wrapped(*args, **kwargs):
                    start = monotonic()
                    try:
                        res = attr(*args, **kwargs)
                        elapsed = (monotonic() - start) * 1000.0
                        counter.inc({"svc": svc, "op": name, "result": RESULT_DONE})
                        hist.observe({"svc": svc, "op": name, "result": RESULT_DONE}, elapsed)
                        return res
                    except Exception:
                        elapsed = (monotonic() - start) * 1000.0
                        counter.inc({"svc": svc, "op": name, "result": RESULT_ERR})
                        hist.observe({"svc": svc, "op": name, "result": RESULT_ERR}, elapsed)
                        raise
                return _wrapped
            return attr
    return _Proxy(obj)

def wrap_kv(kv: Any, *, svc: str, metrics: Metrics):
    return _wrap_calls("kv", kv, metrics, svc)

def wrap_registrar(registrar: Any, *, svc: str, metrics: Metrics):
    return _wrap_calls("registrar", registrar, metrics, svc)

def wrap_net(net: Any, *, svc: str, metrics: Metrics):
    return _wrap_calls("net", net, metrics, svc)
