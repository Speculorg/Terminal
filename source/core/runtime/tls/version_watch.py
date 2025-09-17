# source\core\runtime\tls\version_watch.py

from __future__ import annotations
import asyncio
from typing import Optional

from core.kv import KV
from core.logging import get_logger
from core.runtime.tls.tls_reload import TLSReloader


class CertsVersionWatcher:
    """
    Пуллинг-ватчер ключа certs/version в Consul KV.
    При изменении версии вызывает TLSReloader.notify_version(...).
    """
    def __init__(
        self,
        kv: KV,
        reloader: TLSReloader,
        key: str,
        interval_s: float = 2.0,
        logger=None,
    ) -> None:
        self.kv = kv
        self.reloader = reloader
        self.key = key
        self.interval_s = float(interval_s)
        self.log = logger or get_logger("tls.version_watch")
        self._last_version: Optional[str] = None

    async def run(self, stop_event: asyncio.Event) -> None:
        self.log.info(
            "evt=tls.watch.start key=%s interval_s=%.3f",
            self.key, self.interval_s
        )
        try:
            while not stop_event.is_set():
                try:
                    version, _ = self.kv.get_text(self.key)
                    if version and version != self._last_version:
                        prev = self._last_version
                        self._last_version = version
                        self.log.info("evt=certs.version.changed prev=%s next=%s", prev or "-", version)
                        try:
                            self.reloader.notify_version(version)
                        except Exception as exc:  # noqa: BLE001
                            self.log.warning("evt=tls.reloader.notify.fail err=%s", exc)
                except Exception as exc:  # noqa: BLE001
                    self.log.warning("evt=tls.watch.iter.err err=%s", exc)

                # Ждём или прерываемся по стоп-сигналу
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.interval_s)
                except asyncio.TimeoutError:
                    pass
        finally:
            self.log.info("evt=tls.watch.stop")
