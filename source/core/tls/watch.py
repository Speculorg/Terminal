from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Callable, Iterable

class TLSWatch:
    def __init__(self, cfg, logger, fs):
        self.cfg = cfg
        self.logger = logger
        self.fs = fs

    def start_file_watch(self, paths: Iterable[str], on_change: Callable[[], None]) -> None:
        # TERM-1: упрощённый поллинг по mtime с дебаунсом
        debounce_ms = int(getattr(self.cfg.tls, "watch_debounce_ms", 300))
        poll_ms = int(getattr(self.cfg.tls, "watch_poll_interval_ms", 500))
        last_mtime = {p: self._mtime(p) for p in paths}
        self.logger.info("tls.watch.start", svc=self.cfg.context.name, paths=list(paths))
        # однократная итерация (без фонового потока) — интеграция с runtime пойдёт на TERM-2
        time.sleep(poll_ms/1000.0)
        changed = False
        for p in paths:
            m = self._mtime(p)
            if m != last_mtime[p]:
                changed = True
                last_mtime[p] = m
        if changed:
            time.sleep(debounce_ms/1000.0)
            on_change()

    def _mtime(self, path: str) -> float:
        try:
            return self.fs.mtime(path)
        except Exception:
            return 0.0
