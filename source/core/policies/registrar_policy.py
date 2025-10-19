from __future__ import annotations
from dataclasses import dataclass
import time

from interfaces.i_configs import IConfigs
from interfaces.i_logger import ILogger
from interfaces.i_registrar import IRegistrar
from entities.error_code_enum import ErrorCodeEnum

@dataclass
class RegistrarPolicy:
    cfg: IConfigs
    logger: ILogger
    registrar: IRegistrar

    def on_register(self, svc: str) -> bool:
        try:
            if not self.registrar.register(svc):
                self.logger.warn("registrar.register.failed", svc=svc, error=ErrorCodeEnum.ERR_REGISTRY)
                return False
            return True
        except Exception as e:
            self.logger.warn("registrar.register.exception", svc=svc, error=ErrorCodeEnum.ERR_REGISTRY, details={"exc": type(e).__name__})
            return False

    def try_heartbeat(self, svc: str) -> bool:
        try:
            if not self.registrar.heartbeat(svc):
                self.logger.warn("registrar.heartbeat.failed", svc=svc, error=ErrorCodeEnum.ERR_REGISTRY)
                return False
            return True
        except Exception as e:
            self.logger.warn("registrar.heartbeat.exception", svc=svc, error=ErrorCodeEnum.ERR_REGISTRY, details={"exc": type(e).__name__})
            return False

    def on_deregister(self, svc: str) -> bool:
        try:
            if not self.registrar.deregister(svc):
                self.logger.warn("registrar.deregister.failed", svc=svc, error=ErrorCodeEnum.ERR_REGISTRY)
                return False
            return True
        except Exception as e:
            self.logger.warn("registrar.deregister.exception", svc=svc, error=ErrorCodeEnum.ERR_REGISTRY, details={"exc": type(e).__name__})
            return False
