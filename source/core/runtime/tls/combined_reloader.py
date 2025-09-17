# source\core\runtime\tls\combined_reloader.py

from __future__ import annotations
from typing import Iterable, List

from core.runtime.tls.tls_reload import TLSReloader
from core.logging import get_logger

log = get_logger("tls.combined")


class CombinedTLSReloader(TLSReloader):
    """
    Мультиплексор для нескольких реализаций TLSReloader.
    Пример: SignalTLSReloader (SIGHUP внешнему процессу) + ClientTLSReloader (обновить SSLContext).
    """

    def __init__(self, reloaders: Iterable[TLSReloader]) -> None:
        self._reloaders: List[TLSReloader] = list(reloaders)

    def notify_version(self, version: str) -> None:
        for r in self._reloaders:
            try:
                r.notify_version(version)
            except Exception as exc:  # noqa: BLE001
                log.warning("evt=tls.reloader.child.fail cls=%s err=%s", r.__class__.__name__, exc)
