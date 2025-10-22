from __future__ import annotations
import threading
from typing import Callable

def start_periodic(fn: Callable[[], None], *, period_ms: int, stop_event: threading.Event) -> threading.Thread:
    """Простейший периодический исполнитель. Останавливается по stop_event."""
    t = threading.Thread(target=_runner, args=(fn, period_ms, stop_event), daemon=True)
    t.start()
    return t

def _runner(fn: Callable[[], None], period_ms: int, stop_event) -> None:
    import time
    interval = max(0.001, period_ms/1000.0)
    while not stop_event.is_set():
        try:
            fn()
        except Exception:
            # Без падения воркера
            pass
        stop_event.wait(interval)
