from __future__ import annotations
from typing import Optional
from interfaces import IService, IRunProfile
from .base_deps import BaseDeps
from .base_fsm import BaseFSM

# Фасады и адаптеры. Имена соответствуют принятой структуре.
from adapters.logging import JsonLogger
from adapters.metrics import PrometheusMetrics
from adapters.net import NetAdapter
from adapters.fs import LocalFS
from adapters.kv import ConsulKV
from adapters.registrar import ConsulRegistrar
from adapters.tls import TLSReloader, TLSWatch, TLSProbe
from core.configs import Configs
from core.markers import Markers

class BaseService(IService):
    """
    Базовый каркас сервиса.
    Реализует IService. Инкапсулирует composition root и FSM-оркестрацию.
    """
    def __init__(self, profile: IRunProfile) -> None:
        self._profile = profile
        self._deps: Optional[BaseDeps] = None

    def initialize(self) -> None:
        self._deps = self._build_deps()
        fsm = BaseFSM(self._deps, self._profile)
        # dataclass frozen, присваиваем поле через object.__setattr__
        object.__setattr__(self._deps, "fsm", fsm)

    def start(self) -> None:
        assert self._deps is not None, "initialize() must be called first"
        self._deps.logger.info("service start", svc=self._svc())
        self._deps.fsm.run()

    def pause(self) -> None:
        assert self._deps is not None
        self._deps.logger.info("service pause", svc=self._svc())

    def resume(self) -> None:
        assert self._deps is not None
        self._deps.logger.info("service resume", svc=self._svc())

    def restart(self) -> None:
        assert self._deps is not None
        self._deps.logger.info("service restart", svc=self._svc())
        self.stop()
        self.initialize()
        self.start()

    def stop(self) -> None:
        assert self._deps is not None
        self._deps.logger.info("service stop", svc=self._svc())

    # Composition root
    def _build_deps(self) -> BaseDeps:
        cfg = Configs()  # автозагрузка файла + overlay env
        logger = JsonLogger(cfg)
        metrics = PrometheusMetrics(cfg)
        net = NetAdapter(cfg)
        fs = LocalFS(cfg)
        markers = Markers(cfg, fs)
        kv = ConsulKV(cfg)
        registrar = ConsulRegistrar(cfg)
        tls_reloader = TLSReloader(cfg)
        tls_watch = TLSWatch(cfg)
        tls_probe = TLSProbe(cfg)
        # Временный placeholder для поля fsm, заполним в initialize()
        fsm_placeholder = BaseFSM  # type: ignore[assignment]
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
            fsm=fsm_placeholder,  # type: ignore[arg-type]
        )

    def _svc(self) -> str:
        assert self._deps is not None
        return self._deps.configs.context.name  # type: ignore[attr-defined]
