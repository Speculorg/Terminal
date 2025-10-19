from __future__ import annotations

class TLSProbe:
    def __init__(self, cfg, logger, fs):
        self.cfg = cfg
        self.logger = logger
        self.fs = fs

    def validate_chain(self, cert_path: str, fullchain_path: str, ca_path: str) -> bool:
        # TERM-1: упрощённая проверка — наличие файлов. Криптография добавим на TERM-2.
        ok = True
        for p in (cert_path, fullchain_path, ca_path):
            if not self.fs.exists(p):
                self.logger.error("tls.validate.missing", svc=self.cfg.context.name, path=p)
                ok = False
        return ok
