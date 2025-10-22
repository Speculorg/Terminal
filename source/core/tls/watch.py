from __future__ import annotations
import os
import time
import threading
from typing import Callable, Iterable

class TLSWatch:
    def __init__(self, cfg, logger, fs):
        self.cfg = cfg
        self.logger = logger
        self.fs = fs
        self._watch_thread = None
        self._stop = False

    def _mtime(self, path: str) -> float:
        try:
            return os.path.getmtime(path)
        except Exception:
            return 0.0

    def start_file_watch(self, paths: Iterable[str], on_change: Callable[[], None]) -> None:
        # Упрощённый поллинг по mtime с дебаунсом. Отсутствие файла не является ошибкой.
        debounce_ms = int(getattr(self.cfg.tls, "watch_debounce_ms", 300))
        poll_ms = int(getattr(self.cfg.tls, "watch_poll_interval_ms", 500))
        paths = list(paths)
        last_mtime = {p: self._mtime(p) for p in paths}
        last_fire_ts = 0.0

        def worker():
            nonlocal last_mtime, last_fire_ts
            self.logger.info("tls.watch.start", svc=self.cfg.context.name, files=len(paths))
            while not self._stop:
                changed = False
                for p in paths:
                    m = self._mtime(p)
                    if m != last_mtime.get(p, 0.0):
                        last_mtime[p] = m
                        changed = True
                if changed:
                    now = time.time() * 1000.0
                    if now - last_fire_ts >= debounce_ms:
                        last_fire_ts = now
                        try:
                            on_change()
                        except Exception as e:
                            self.logger.warn("tls.watch.callback.error", svc=self.cfg.context.name, err=type(e).__name__)
                time.sleep(max(0.05, poll_ms/1000.0))
            self.logger.info("tls.watch.stop", svc=self.cfg.context.name)

        if self._watch_thread is None:
            self._stop = False
            t = threading.Thread(target=worker, name=f"tls-watch-{self.cfg.context.name}", daemon=True)
            t.start()
            self._watch_thread = t

    def stop(self) -> None:
        self._stop = True
        t = self._watch_thread
        if t and t.is_alive():
            t.join(timeout=1.0)
