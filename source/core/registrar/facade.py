from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import time

from interfaces.i_configs import IConfigs
from interfaces.i_logger import ILogger

@dataclass
class Registrar:
    """Порт регистрации сервисов и TTL-heartbeat.
    Работает поверх client-адаптера (Consul agent HTTP).
    Интерфейс без deadline-параметров. Таймауты берутся из cfg.
    """
    cfg: IConfigs
    logger: ILogger
    client: Any  # duck-typed: register_service(dict), deregister_service(str), pass_ttl(str)

    def _service_id(self, svc: str) -> str:
        return svc

    def register(self, svc: str) -> bool:
        svc_id = self._service_id(svc)
        ttl_sec = int(self.cfg.registrar.ttl_sec)
        hb_period = int(self.cfg.registrar.heartbeat_period_sec)
        # TTL-check id по канону Consul: service:{id}
        check_id = f"service:{svc_id}"
        service_def = {
            "ID": svc_id,
            "Name": svc_id,
            "Port": int(self.cfg.context.port),
            "Tags": list(self.cfg.context.tags),
            "Checks": [{
                "CheckID": check_id,
                "TTL": f"{ttl_sec}s",
                "DeregisterCriticalServiceAfter": f"{int(self.cfg.registrar.deregister_critical_service_after_sec)}s"
            }]
        }
        ok = self.client.register_service(service_def)
        self.logger.info("registrar.register", svc=svc, ok=bool(ok))
        return bool(ok)

    def heartbeat(self, svc: str) -> bool:
        check_id = f"service:{self._service_id(svc)}"
        ok = self.client.pass_ttl(check_id)
        self.logger.info("registrar.heartbeat", svc=svc, ok=bool(ok))
        return bool(ok)

    def deregister(self, svc: str) -> bool:
        svc_id = self._service_id(svc)
        ok = self.client.deregister_service(svc_id)
        self.logger.info("registrar.deregister", svc=svc, ok=bool(ok))
        return bool(ok)
