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
    """Каркас сервиса. Инкапсулирует composition root и ЖЦ."""
    def __init__(self) -> None:
        # Composition root
        self._cfg = Configs()
        self._logger = JsonLogger(self._cfg)
        self._metrics = PrometheusMetrics(self._cfg)
        self._net = Net(self._cfg)
        self._fs = FS(self._cfg)
        self._markers = Markers(self._cfg)
        self._kv = KV(self._cfg, ConsulKV(self._cfg, self._logger))
        self._registrar = Registrar(self._cfg, self._logger, ConsulRegistrar(self._cfg, self._logger))
        # FSM
        self._fsm = FSM(self.svc, self._cfg, self._logger, self._markers, self._kv, self._metrics, registrar=self._registrar)
        # Внутренние флаги
        self._started: bool = False

    # ---- IService ----
    def initialize(self) -> None:
        self._logger.info("initialize", svc=self.svc)
        # HTTP-экспорт метрик (если включён)
        enable_http = bool(getattr(self._cfg.metrics, "export_http", False))
        if enable_http:
            host = getattr(self._cfg.metrics, "host", "0.0.0.0")
            port = int(getattr(self._cfg.metrics, "port", 8000))
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
        self.start()

    def stop(self) -> None:
        self._logger.info("stop", svc=self.svc)
        try:
            self._registrar.deregister(self.svc)
        except Exception:
            pass
        self._started = False

    # ---- deps accessors ----
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
