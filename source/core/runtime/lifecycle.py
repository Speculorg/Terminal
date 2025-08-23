# source\core\runtime\lifecycle.py


"""
Lightweight lifecycle helpers for services.
- Signal wiring -> shutdown Event
- Exponential backoff
- Periodic task runner
"""

from __future__ import annotations
import asyncio
import random
import signal
from typing import Awaitable, Callable, Optional


def install_signal_shutdown_flag(shutdown_event: asyncio.Event, on_signal: Optional[Callable[[signal.Signals], None]] = None) -> None:
    """
    Register SIGTERM/SIGINT handlers to set shutdown flag in the current event loop.
    """
    loop = asyncio.get_event_loop()
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: _on_signal(shutdown_event, s, on_signal))
    except NotImplementedError:
        # On Windows or embedded loops signals may be unsupported — ignore.
        pass


def _on_signal(shutdown_event: asyncio.Event, s: signal.Signals, on_signal: Optional[Callable[[signal.Signals], None]]) -> None:
    if on_signal:
        try:
            on_signal(s)
        except Exception:
            pass
    shutdown_event.set()


async def sleep_backoff(attempt: int, base: float = 0.5, cap: float = 5.0, jitter: float = 0.1) -> None:
    """
    Exponential backoff with optional jitter.
    delay = min(cap, base * 2^(attempt-1)) * (1 +/- jitter)
    """
    exp = base * (2 ** max(0, attempt - 1))
    exp = min(cap, exp)
    j = 1.0 + random.uniform(-jitter, jitter) if jitter > 0 else 1.0
    await asyncio.sleep(exp * j)


class Periodic:
    """
    Periodically run an async callable until cancelled.
    Usage:
        p = Periodic(1.0, coro_fn)
        p.start()
        ...
        await p.stop()
    """
    def __init__(self, interval: float, func: Callable[[], Awaitable[None]]) -> None:
        self.interval = float(interval)
        self.func = func
        self._task: Optional[asyncio.Task] = None
        self._stopped = asyncio.Event()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopped.clear()
        self._task = asyncio.create_task(self._runner())

    async def stop(self) -> None:
        if not self._task:
            return
        self._stopped.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def _runner(self) -> None:
        try:
            while not self._stopped.is_set():
                try:
                    await self.func()
                finally:
                    await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            pass
