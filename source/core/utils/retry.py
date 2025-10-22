from __future__ import annotations
from typing import Iterator, Tuple
from .backoff import exp_jitter_backoff_ms
from .time import utc_ts_ms, sleep_ms

def retry_window(deadline_ts_ms: int, *, base:int=2, unit_ms:int=100, cap_ms:int=10_000) -> Iterator[Tuple[int,int]]:
    """Итератор попыток до дедлайна. Возвращает (attempt, sleep_ms) для каждой попытки.
    Останавливается, когда next_sleep выходит за дедлайн.
    """
    attempt = 0
    while True:
        now = utc_ts_ms()
        if now >= deadline_ts_ms:
            break
        sleep = exp_jitter_backoff_ms(attempt, base=base, unit_ms=unit_ms, cap_ms=cap_ms)
        if now + sleep >= deadline_ts_ms:
            break
        yield attempt, sleep
        sleep_ms(sleep)
        attempt += 1
