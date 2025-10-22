from __future__ import annotations
import time
from datetime import datetime, timezone

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def utc_ts_ms() -> int:
    return int(utc_now().timestamp() * 1000)

def sleep_ms(ms: int) -> None:
    if ms <= 0:
        return
    time.sleep(ms/1000.0)
