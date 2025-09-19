# source/core/runtime/tls/reloaders.py

from __future__ import annotations
import signal
from typing import Callable, Optional

from core.logging import get_logger
from core.runtime.tls.tls_reload import TLSReloader


log = get_logger("tls.reloader")


class NoopTLSReloader(TLSReloader):
    """Пустой reloader — только логируем факт смены версии."""

    def notify_version(self, version: str) -> None:
        log.info("evt=tls.reload.noop version=%s", version)


class ProcSignalTLSReloader(TLSReloader):
    """
    Отправляет сигнал (`SIGHUP` по умолчанию) дочернему процессу сервиса.
    Требует функцию-доставщик процесса (например, `lambda: self._child`).
    """

    def __init__(self, name: str, proc_getter: Callable[[], Optional[object]], signum: int = signal.SIGHUP) -> None:
        self._name = name
        self._proc_getter = proc_getter
        self._signum = signum

    def notify_version(self, version: str) -> None:
        proc = None
        try:
            proc = self._proc_getter()
        except Exception as exc:  # noqa: BLE001
            log.warning("evt=tls.reload.proc_getter.fail name=%s err=%s", self._name, exc)

        if proc and getattr(proc, "poll", lambda: None)() is None:
            try:
                proc.send_signal(self._signum)
                log.info("evt=tls.reload.signal name=%s signum=%s version=%s", self._name, self._signum, version)
            except Exception as exc:  # noqa: BLE001
                log.warning("evt=tls.reload.signal.fail name=%s err=%s", self._name, exc)
        else:
            log.warning("evt=tls.reload.signal.skip name=%s reason=no-proc", self._name)


class CallbackTLSReloader(TLSReloader):
    """
    Вызывает произвольный callback при смене версии сертификатов.
    Подходит для сценариев «управляемый рестарт по изменению certs/version».
    """

    def __init__(self, name: str, callback: Callable[[str], None]) -> None:
        self._name = name
        self._callback = callback

    def notify_version(self, version: str) -> None:
        try:
            self._callback(version)
            log.info("evt=tls.reload.callback name=%s version=%s", self._name, version)
        except Exception as exc:  # noqa: BLE001
            log.warning("evt=tls.reload.callback.fail name=%s err=%s", self._name, exc)
