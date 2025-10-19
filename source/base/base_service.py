from __future__ import annotations
from typing import Optional

from interfaces.i_service import IService
from core.configs import Configs
from adapters.logging.json_logger import JsonLogger
from adapters.metrics import PrometheusMetrics
from core.net import Net
from core.fs import FS
from core.markers import Markers
from core.policies import PoliciesFactory
from core.policies import MarkerPolicy

# KV (Этап 7)
from adapters.kv import ConsulKV
from core.kv import KV
from core.fsm import FSM

class BaseService(IService):
    """Единый каркас сервиса.
    Инкапсулирует composition root и простейший жизненный цикл.
    Без сетевых проб на ранних стадиях. Гейты по файловым маркерам реализуются в реализациях сервисов.
    """
    def __init__(self) -> None:
        # Конфиги
        self._cfg = Configs()
        # Логер
        self._logger = JsonLogger(self._cfg)
        # Метрики
        self._metrics = PrometheusMetrics(self._cfg)
        # Сеть
        self._net = Net()
        # Файловая система и маркеры
        self._fs = FS(self._cfg)
        self._markers = Markers(self._cfg, fs=self._fs)
        # KV
        ikv = ConsulKV(self._cfg)
        self._kv = KV(ikv, svc=self._cfg.context.name)
        self._fsm = FSM(self._cfg.context.name, self._cfg, self._logger, self._markers, self._kv, self._metrics)

        # Внутренние флаги
        self._started: bool = False

    # ---- IService ----
    def initialize(self) -> None:
        self._logger.info("initialize", svc=self.svc)
        # Инициализация HTTP-экспортера метрик по настройке
        enable_http = bool(getattr(self._cfg.metrics, "export_http", False))
        if enable_http:
            host = getattr(self._cfg.metrics, "host", "0.0.0.0")
            port = int(getattr(self._cfg.metrics, "port", 9000))
            path = getattr(self._cfg.metrics, "path", "/metrics")
            try:
                self._metrics.start_http_exporter(host=host, port=port, path=path)
                self._logger.info("metrics http exporter started", svc=self.svc, host=host, port=port, path=path)
            except Exception as e:
                self._logger.warn("metrics http exporter failed", svc=self.svc, error=str(e))

    def start(self) -> None:
        self._logger.info("start", svc=self.svc)
                # Определение режима запуска по обязательным маркерам профиля
        required = set()
        if hasattr(self, "run_profile") and hasattr(self.run_profile, "required_markers"):
            required = set(self.run_profile.required_markers)
        mode = MarkerPolicy.detect_run_mode(required, self._markers)
        self._fsm.set_run_mode(mode)
        self._fsm.start()
        self._started = True

    def pause(self) -> None:
        self._logger.info("pause", svc=self.svc)

    def resume(self) -> None:
        self._logger.info("resume", svc=self.svc)

    def restart(self) -> None:
        self._logger.info("restart", svc=self.svc)
        self.stop()
        self.initialize()
        self.start()

    def stop(self) -> None:
        self._logger.info("stop", svc=self.svc)
        try:
            self._metrics.stop_http_exporter()
        except Exception:
            pass
        self._started = False

    # ---- Шорткаты ----
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
    def svc(self) -> str: return self._cfg.context.name
