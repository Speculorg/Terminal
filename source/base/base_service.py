from __future__ import annotations
from typing import Optional
import time
from interfaces import IService, IRunProfile
from .base_deps import BaseDeps, BaseDepsFactory
from .base_health import BaseHealth
from entities import HealthStatusEnum


class BaseService(IService):
    """Каркас сервиса. Принимает профиль запуска из main.py."""
    def __init__(self, run_profile: Optional[IRunProfile] = None) -> None:
        deps = BaseDepsFactory.build()
        self._deps = deps
        self.run_profile: Optional[IRunProfile] = run_profile
        self._cfg = deps.configs
        self._logger = deps.logger
        self._metrics = deps.metrics
        self._fs = deps.fs
        self._markers = deps.markers
        self._registrar = deps.registrar
        self._health = BaseHealth()
        self.initialize()


    # Жизненный цикл
    def initialize(self) -> None:
        self._logger.info("service.initialize", svc=self._cfg.context.name)
        self.start()

    def start(self) -> None:
        if not self.run_profile:
            self._logger.error("service.start.no_profile", svc=self._cfg.context.name)
            return

        # Проверка обязательных маркеров сервиса
        ok, missing = self._markers.require(self.run_profile.required_markers, self._cfg.context.name) if getattr(self.run_profile, "required_markers", None) else (True, set())
        if not ok:
            self._logger.error("service.start.precondition", svc=self._cfg.context.name, details={"missing": sorted(list(missing))})
            return

        # Запуск FSM отложен до реализации демонов. Пока — публикация health.
        self._health.status = HealthStatusEnum.PASSING
        self._health.heartbeat_ts = int(time.time())
        self._logger.info("service.start", svc=self._cfg.context.name, details={"port": self._cfg.context.port})

    def stop(self) -> None:
        try:
            # дерегистрация если есть
            if self._registrar:
                self._registrar.deregister(self._cfg.context.name)  # type: ignore
        except Exception:
            pass
        self._logger.info("service.stop", svc=self._cfg.context.name)
