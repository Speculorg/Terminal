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
    """Каркас сервиса. Собирает зависимости и поднимает инфраструктуру.

    Без сетевых проб на ранних стадиях. Дедлайны берутся из cfg.fsm.*.

    """
    def __init__(self) -> None:
        self._cfg = Configs()
        self._logger = JsonLogger(self._cfg)
        self._metrics = PrometheusMetrics()
        # HTTP-экспорт метрик
        try:
            self._metrics.start_http_exporter(host="0.0.0.0", port=int(self._cfg.metrics.port), path=str(self._cfg.metrics.path))
            self._logger.info("metrics http exporter started", svc=self.svc, port=int(self._cfg.metrics.port), path=str(self._cfg.metrics.path))
        except Exception as e:
            self._logger.warn("metrics http exporter failed", svc=self.svc, error=str(e))

        self._net = Net(self._cfg)            # Net(cfg)
        self._fs = FS(self._cfg)
        self._markers = Markers(self._cfg, fs=self._fs)
        # Адаптеры
        self._kv_client = ConsulKV(self._cfg)
        self._registrar_client = ConsulRegistrar(self._cfg)
        # Порты
        self._kv = KV(self._kv_client, svc=self._cfg.context.name)
        self._registrar = Registrar(cfg=self._cfg, logger=self._logger, client=self._registrar_client)
        # FSM (пока тонкая обвязка)
        self._fsm: Optional[FSM] = None
        self.run_profile = None  # переопределяется в сервисе

    # ---- IService ----
    def initialize(self) -> None:
        # На старте только подготовка локальных зависимостей. Без сетевых проверок.
        self._logger.info("initialize", svc=self.svc)

    def start(self) -> None:
        self._logger.info("start", svc=self.svc)
        # Здесь позже будет запуск FSM и регистрация. Пока только лог.
        return

    def pause(self) -> None:
        self._logger.info("pause", svc=self.svc)

    def resume(self) -> None:
        self._logger.info("resume", svc=self.svc)

    def restart(self) -> None:
        self._logger.info("restart", svc=self.svc)

    def stop(self) -> None:
        self._logger.info("stop", svc=self.svc)

    # ---- Properties ----
    @property
    def cfg(self) -> Configs: return self._cfg
    @property
    def logger(self) -> JsonLogger: return self._logger
    @property
    def metrics(self) -> PrometheusMetrics: return self._metrics
    @property
    def net(self) -> Net: return self._net
    @property
    def fs(self) -> FS: return self._fs
    @property
    def markers(self) -> Markers: return self._markers
    @property
    def kv(self) -> KV: return self._kv
    @property
    def registrar(self) -> Registrar: return self._registrar

    @property
    def svc(self) -> str: return self._cfg.context.name
