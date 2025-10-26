from __future__ import annotations
from dataclasses import dataclass
from interfaces import IConfigs, ILogger, IRegistrar
from entities import ErrorCodeEnum


@dataclass
class RegistrarPolicy:
    cfg: IConfigs
    logger: ILogger
    registrar: IRegistrar

    def on_register(self, svc: str) -> bool:
        try:
            ok = self.registrar.register(svc)
            if not ok:
                self.logger.warn("registrar.register.failed", svc=svc, details={ "error": "register not_ok" } )
            return ok
        except Exception as e:
            self.logger.warn("registrar.register.exception", svc=svc, details={ "exc": type(e).__name__ } )
            return False

    def on_heartbeat(self, svc: str) -> bool:
        try:
            ok = self.registrar.heartbeat(svc)
            if not ok:
                self.logger.warn("registrar.heartbeat.failed", svc=svc, details={ "error": "not_ok" } )
            return ok
        except Exception as e:
            self.logger.warn("registrar.heartbeat.exception", svc=svc, details={ "exc": type(e).__name__ } )
            return False

    def on_deregister(self, svc: str) -> bool:
        try:
            ok = self.registrar.deregister(svc)
            if not ok:
                self.logger.warn("registrar.deregister.failed", svc=svc, details={ "error": "not_ok" } )
            return ok
        except Exception as e:
            self.logger.warn("registrar.deregister.exception", svc=svc, details={ "exc": type(e).__name__ } )
            return False
