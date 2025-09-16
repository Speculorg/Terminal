# source\core\runtime\tls\signal_reloader.py

from __future__ import annotations
import os
import signal
from typing import Optional

from core.logging import get_logger
from core.runtime.tls.tls_reload import TLSReloader

log = get_logger("tls.reloader.signal")


class SignalTLSReloader(TLSReloader):
    """
    TLSReloader для внешних бинарников, поддерживающих горячую перезагрузку по сигналу.
    Например: Traefik/Nginx/Hitch и т.п.

    Варианты:
      - передать pid (число),
      - или указать pidfile (путь к файлу, где хранится PID).
    """

    def __init__(self, *, pid: Optional[int] = None, pidfile: Optional[str] = None, sig: int = signal.SIGHUP) -> None:
        if not pid and not pidfile:
            raise ValueError("Either pid or pidfile must be provided")
        self._pid = int(pid) if pid else None
        self._pidfile = pidfile
        self._sig = sig

    def _read_pidfile(self) -> Optional[int]:
        if not self._pidfile:
            return None
        try:
            with open(self._pidfile, "r", encoding="utf-8", errors="replace") as f:
                s = (f.readline() or "").strip()
            return int(s) if s else None
        except Exception:
            return None

    def _resolve_pid(self) -> Optional[int]:
        if self._pid:
            return self._pid
        return self._read_pidfile()

    def notify_version(self, version: str) -> None:
        pid = self._resolve_pid()
        if not pid:
            log.warning("evt=tls.reload.skip reason=no_pid")
            return
        try:
            os.kill(pid, self._sig)
            log.info("evt=tls.signal.sent pid=%s sig=%s version=%s", pid, self._sig, version)
        except Exception as exc:  # noqa: BLE001
            log.warning("evt=tls.signal.fail pid=%s sig=%s err=%s", pid, self._sig, exc)
