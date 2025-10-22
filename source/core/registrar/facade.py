from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from interfaces import IConfigs, ILogger
from entities import ErrorCodeEnum

@dataclass
class Registrar:
    """Порт регистрации и TTL-heartbeat поверх клиент-адаптера.
    Без deadline-параметров. Окна берутся из cfg.registrar.* и FSM.
    """
    cfg: IConfigs
    logger: ILogger
    client: Any  # duck-typed: register_service(def)->bool, deregister_service(id)->bool, pass_ttl(check_id)->bool

    def _service_id(self, svc: str) -> str:
        return svc

    def _ttl_check_id(self, svc: str) -> str:
        return f"service:{svc}:ttl"

    def _service_def(self, svc: str) -> Dict:
        cs = self.cfg.context
        rs = self.cfg.registrar
        return {
            "ID": self._service_id(svc),
            "Name": svc,
            "Port": int(cs.port),
            "Tags": list(cs.tags),
            "EnableTagOverride": False,
            "Checks": [
                {
                    "CheckID": self._ttl_check_id(svc),
                    "Name": f"{svc} ttl",
                    "TTL": f"{int(rs.ttl_sec)}s",
                    "DeregisterCriticalServiceAfter": f"{int(rs.deregister_critical_service_after_sec)}s",
                }
            ],
        }

    def register(self, svc: str) -> bool:
        try:
            ok = self.client.register_service(self._service_def(svc))
            if not ok:
                self.logger.warn("registrar.register.failed", svc=svc, error=ErrorCodeEnum.ERR_REGISTRY)
            else:
                self.logger.info("registrar.register.ok", svc=svc)
            return ok
        except Exception as e:
            self.logger.warn("registrar.register.exception", svc=svc, error=ErrorCodeEnum.ERR_REGISTRY, details={"exc": type(e).__name__})
            return False

    def heartbeat(self, svc: str) -> bool:
        try:
            ok = self.client.pass_ttl(self._ttl_check_id(svc))
            if not ok:
                self.logger.warn("registrar.heartbeat.failed", svc=svc, error=ErrorCodeEnum.ERR_REGISTRY)
            else:
                self.logger.info("registrar.heartbeat.ok", svc=svc)
            return ok
        except Exception as e:
            self.logger.warn("registrar.heartbeat.exception", svc=svc, error=ErrorCodeEnum.ERR_REGISTRY, details={"exc": type(e).__name__})
            return False

    def deregister(self, svc: str) -> bool:
        try:
            ok = self.client.deregister_service(self._service_id(svc))
            if not ok:
                self.logger.warn("registrar.deregister.failed", svc=svc, error=ErrorCodeEnum.ERR_REGISTRY)
            else:
                self.logger.info("registrar.deregister.ok", svc=svc)
            return ok
        except Exception as e:
            self.logger.warn("registrar.deregister.exception", svc=svc, error=ErrorCodeEnum.ERR_REGISTRY, details={"exc": type(e).__name__})
            return False
