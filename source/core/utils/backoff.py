from __future__ import annotations
import random

def exp_jitter_backoff_ms(attempt: int, *, base: int = 2, unit_ms: int = 100, cap_ms: int = 10_000) -> int:
    """Экспоненциальный backoff с джиттером. attempt>=0."""
    if attempt < 0:
        attempt = 0
    delay = min(cap_ms, unit_ms * (base ** attempt))
    # полнодисперсионный джиттер [0, delay]
    return int(random.random() * max(1, delay))
