from __future__ import annotations

# Имена по плану
KV_COUNTER = "terminal_kv_counter"
KV_HISTOGRAM = "terminal_kv_latency_ms"

TLS_COUNTER = "terminal_tls_counter"
TLS_HISTOGRAM = "terminal_tls_latency_ms"

REG_COUNTER = "terminal_registrar_counter"
REG_HISTOGRAM = "terminal_registrar_latency_ms"

NET_COUNTER = "terminal_net_counter"
NET_HISTOGRAM = "terminal_net_latency_ms"

# Разрешённые ключи меток и лимиты
ALLOWED_LABEL_KEYS = ("svc", "state", "op", "result")
RESULT_DONE = "done"
RESULT_ERR = "err"
RESULT_DROPPED = "dropped"
DEFAULT_BUCKETS_MS = [10,25,50,100,250,500,1000,2500,5000,10000,30000,60000]
CARDINALITY_LIMIT = 100
