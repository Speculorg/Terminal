from __future__ import annotations
from typing import Optional

from interfaces import IService
from core.configs import Configs
from adapters.logging import JsonLogger
from adapters.metrics import PrometheusMetrics
from core.net import Net
from core.fs import FS
from core.markers import Markers
from core.kv import KV
from adapters.kv import ConsulKV
from core.fsm import FSM
from core.policies import MarkerPolicy
from core.registrar import Registrar
from adapters.registrar import ConsulRegistrar

class BaseService(IService):
    """Каркас сервиса и composition root. Минимальный цикл без сетевых проб на ранних стадиях."""
    def __init__(self) -> None:
        # Конфиги и базовые фасады
        self._cfg = Configs()
        self._logger = JsonLogger(self._cfg)
        self._metrics = PrometheusMetrics()
        # Экспорт метрик
        self._metrics.start_http_exporter(port=int(self._cfg.metrics.port), path=self._cfg.metrics.path)
        # Ядро
        self._net = Net(self._cfg)
        self._fs = FS(self._cfg)
        self._markers = Markers(self._cfg, fs=self._fs)
        # Адаптеры
        self._kv_client = ConsulKV(self._cfg)
        self._registrar_client = ConsulRegistrar(self._cfg, self._logger)
        # Порты
        self._kv = KV(self._kv_client, svc=self._cfg.context.name)
        self._registrar = Registrar(cfg=self._cfg, logger=self._logger, client=self._registrar_client)
        # FSM (подключим позже)
        self._fsm: Optional[FSM] = None
        self.run_profile = None  # переопределяется в сервисе

    # ---- IService ----
    def initialize(self) -> None:
        # На старте только подготовка локальных зависимостей. Без сетевых операций.
        self._logger.info("service.init", svc=self._cfg.context.name, version=self._cfg.version)

    def start(self) -> None:
        # Заглушка цикла до интеграции FSM. Позволяет сервисам стартовать и экспонировать метрики/health.
        self._logger.info("service.start", svc=self._cfg.context.name)

    def stop(self) -> None:
        self._logger.info("service.stop", svc=self._cfg.context.name)
