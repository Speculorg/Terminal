from __future__ import annotations
from typing import Optional
from dataclasses import dataclass
from interfaces import IService
from .base_deps import BaseDeps
from entities import StateEnum, RunModeEnum

# Локальный профиль запуска для простых случаев
@dataclass(frozen=True)
class _DefaultRunProfile:
    required_markers: set[str]

class BaseService(IService):
    """Каркас сервиса.
    По умолчанию сам собирает зависимости через BaseDeps(IDeps).
    Допускает DI: deps можно передать снаружи (тесты).
    Простейшая FSM без сетевых проб: гейты по файловым маркерам.
    """
    def __init__(self, deps: Optional[BaseDeps] = None) -> None:
        self.deps = deps or self._build_deps()
        self._cfg = self.deps.configs
        self._logger = self.deps.logger
        self._metrics = self.deps.metrics
        self._net = self.deps.net
        self._fs = self.deps.fs
        self._markers = self.deps.markers
        self._kv = self.deps.kv
        self._registrar = self.deps.registrar
        self._tls_reloader = self.deps.tls_reloader
        self._tls_watch = self.deps.tls_watch
        self._tls_probe = self.deps.tls_probe
        self._fsm = self.deps.fsm
        # run_profile задаёт конкретный сервис в наследнике; по умолчанию пусто
        self.run_profile = _DefaultRunProfile(required_markers=set())
        self.state: StateEnum = StateEnum.STARTING
        self.run_mode: RunModeEnum | None = None

    # ---- Сбор зависимостей (composition root) ----
    def _build_deps(self) -> BaseDeps:
        from core.configs import Configs
        from adapters.logging import JsonLogger
        from adapters.metrics import PrometheusMetrics
        from core.net import Net
        from core.fs import FS
        from core.markers import Markers
        from core.kv import KV
        from adapters.kv import ConsulKV
        from core.registrar import Registrar
        from adapters.registrar import ConsulRegistrar
        from core.tls import TLSReloader, TLSWatch, TLSProbe
        from core.fsm import FSM

        cfg = Configs()

        logger = JsonLogger(cfg)
        metrics = PrometheusMetrics()
        try:
            metrics.start_http_exporter(port=int(cfg.metrics.port), path=cfg.metrics.path)
        except Exception:
            pass  # повторный запуск допустим

        net = Net(cfg)
        fs = FS(cfg)
        markers = Markers(cfg, fs=fs)
        kv = KV(cfg, client=ConsulKV(cfg))
        registrar = Registrar(cfg, logger=logger, client=ConsulRegistrar(cfg))
        tls_reloader = TLSReloader(cfg)
        tls_watch = TLSWatch(cfg)
        tls_probe = TLSProbe(cfg)
        fsm = FSM(cfg, logger=logger, metrics=metrics, net=net, fs=fs, markers=markers, kv=kv, registrar=registrar, tls_reloader=tls_reloader, tls_watch=tls_watch, tls_probe=tls_probe)

        return BaseDeps(
            configs=cfg,
            logger=logger,
            metrics=metrics,
            net=net,
            fs=fs,
            markers=markers,
            kv=kv,
            registrar=registrar,
            tls_reloader=tls_reloader,
            tls_watch=tls_watch,
            tls_probe=tls_probe,
            fsm=fsm
        )

    # ---- IService ----
    def initialize(self) -> None:
        # Только локальная подготовка. Без сети.
        self.state = StateEnum.STARTING
        self._logger.info("service.init", svc=self._cfg.context.name, version=self._cfg.global_.version, state=self.state.name)

    def start(self) -> None:
        # Простейшая FSM по маркерам, без сетевых проб
        from core.policies.marker_policy import MarkerPolicy

        self.state = StateEnum.BOOTSTRAPPING
        self._logger.info("fsm.enter", svc=self._cfg.context.name, state=self.state.name)

        required = getattr(self.run_profile, "required_markers", set())
        self.run_mode = MarkerPolicy.detect_run_mode(required, self._markers, svc=self._cfg.context.name)
        self._logger.info("fsm.run_mode", svc=self._cfg.context.name, run_mode=self.run_mode.name)

        if self.run_mode in (RunModeEnum.FIRST, RunModeEnum.RECOVERY):
            # Останавливаемся в INITIALIZING и ждём маркеры
            self.state = StateEnum.INITIALIZING
            ok, missing = self._markers.require(required, svc=self._cfg.context.name)
            self._logger.warn("fsm.wait_markers", svc=self._cfg.context.name, state=self.state.name, missing=sorted(missing))
            return

        # NORMAL: все обязательные маркеры присутствуют
        self.state = StateEnum.REGISTERING
        self._logger.info("fsm.enter", svc=self._cfg.context.name, state=self.state.name)
        # Регистрацию пока не выполняем, сетевых операций нет
        self.state = StateEnum.RUNNING
        self._logger.info("fsm.enter", svc=self._cfg.context.name, state=self.state.name)

    def stop(self) -> None:
        self._logger.info("service.stop", svc=self._cfg.context.name)
