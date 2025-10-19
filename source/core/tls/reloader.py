from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

class TLSReloader:
    def __init__(self, cfg, logger):
        self.cfg = cfg
        self.logger = logger

    def reload_ssl_context(self) -> bool:
        # TERM-1: заглушка. Реальный reload добавим при интеграции с конкретным сервером.
        self.logger.info("tls.reload", svc=self.cfg.context.name, strategy=str(self.cfg.tls.reloader_strategy))
        return True

    def fallback_restart(self) -> None:
        self.logger.warn("tls.fallback_restart", svc=self.cfg.context.name)
