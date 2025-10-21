from __future__ import annotations
from typing import Optional
from interfaces import IService
from .base_deps import BaseDeps
from entities import StateEnum, RunModeEnum

class BaseService(IService):
    """Каркас сервиса.
    Не создаёт зависимости сам. Получает их через BaseDeps(IDeps).
    Жизненный цикл и FSM будут подключены на следующем шаге.
    """
    def __init__(self, deps: BaseDeps) -> None:
        self.deps = deps
        self._cfg = deps.configs
        self._logger = deps.logger
        self._metrics = deps.metrics
        self._net = deps.net
        self._fs = deps.fs
        self._markers = deps.markers
        self._kv = deps.kv
        self._registrar = deps.registrar
        self._tls_reloader = deps.tls_reloader
        self._tls_watch = deps.tls_watch
        self._tls_probe = deps.tls_probe
        self._fsm = deps.fsm
        self.run_profile = None  # переопределяется в конкретном сервисе

    # ---- IService ----
    def initialize(self) -> None:
        # Только локальная подготовка. Без сети.
        self._logger.info("service.init", svc=self._cfg.context.name, version=self._cfg.global_.version)

    def start(self) -> None:
        # Заглушка до полной интеграции FSM/политик.
        self._logger.info("service.start", svc=self._cfg.context.name)

    def stop(self) -> None:
        self._logger.info("service.stop", svc=self._cfg.context.name)
