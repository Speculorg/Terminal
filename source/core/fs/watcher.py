from __future__ import annotations
import threading, time, os
from typing import Callable

class _Watcher:
    def __init__(self, paths: list[str], on_change: Callable[[list[str]], None], poll_interval_ms: int) -> None:
        self._paths = list(paths)
        self._cb = on_change
        self._poll = max(50, int(poll_interval_ms)) / 1000.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="fs-watcher", daemon=True)
        self._mtimes: dict[str, float] = {}

    def start(self) -> "_Watcher":
        self._snapshot()
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)

    def _snapshot(self) -> None:
        for p in self._paths:
            try:
                self._mtimes[p] = os.path.getmtime(p)
            except FileNotFoundError:
                self._mtimes[p] = 0.0

    def _run(self) -> None:
        while not self._stop.is_set():
            touched: list[str] = []
            for p in self._paths:
                try:
                    m = os.path.getmtime(p)
                except FileNotFoundError:
                    m = 0.0
                if self._mtimes.get(p, 0.0) != m:
                    self._mtimes[p] = m
                    touched.append(p)
            if touched:
                try:
                    self._cb(touched)
                except Exception:
                    pass
            time.sleep(self._poll)
