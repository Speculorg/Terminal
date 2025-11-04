from __future__ import annotations
from typing import Iterable, Optional

class BaseTLSReloader:
    """Каркас перезагрузки TLS (заглушка)."""
    def __init__(self, cfg, logger) -> None:
        self.cfg = cfg
        self.logger = logger

    def reload(self) -> bool:
        # Ничего не делаем на TERM-1
        self.logger.info("tls.reload.stub", svc=self.cfg.context.name)
        return True

class BaseTLSWatch:
    """Каркас наблюдателя TLS (заглушка)."""
    def __init__(self, cfg, logger, fs) -> None:
        self.cfg = cfg
        self.logger = logger
        self.fs = fs

    def start_watch(self, paths: Iterable[str], *, debounce_ms: int = 500) -> None:
        # Ничего не делаем на TERM-1
        self.logger.info("tls.watch.stub", svc=self.cfg.context.name, details={"paths": list(paths), "debounce_ms": debounce_ms})

class BaseTLSProbe:
    """Каркас проверки цепочки TLS (заглушка)."""
    def __init__(self, cfg, logger, fs) -> None:
        self.cfg = cfg
        self.logger = logger
        self.fs = fs

    def validate_chain(self, cert_path: str, fullchain_path: str, ca_path: str) -> bool:
        # Всегда ОК на TERM-1
        self.logger.info("tls.validate.stub", svc=self.cfg.context.name)
        return True
