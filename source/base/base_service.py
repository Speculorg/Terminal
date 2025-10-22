from __future__ import annotations
from typing import Optional
from dataclasses import dataclass
import time
from interfaces import IService
from .base_deps import BaseDeps
from .base_health import BaseHealth
from entities import HealthStatusEnum, StateEnum

# Локальный профиль запуска для простых случаев
@dataclass(frozen=True)
class _DefaultRunProfile:
    required_markers: set[str]

class BaseService(IService):
    """Каркас сервиса.
    По умолчанию сам собирает зависимости через BaseDeps(IDeps).
    Допускает DI: deps можно передать снаружи (тесты).
    FSM оркестрирует стадии, здесь только делегирование.
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
        self.run_profile = _DefaultRunProfile(required_markers=set())

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
            metrics.start_http_exporter(host=str(cfg.metrics.host), port=int(cfg.metrics.port), path=cfg.metrics.path)
        except Exception:
            pass

        net = Net(cfg)
        fs = FS(cfg)
        markers = Markers(cfg, fs=fs)
        kv = KV(ConsulKV(cfg), svc=cfg.context.name)
        registrar = Registrar(cfg, logger=logger, client=ConsulRegistrar(cfg, logger))
        tls_reloader = TLSReloader(cfg, logger)
        tls_watch = TLSWatch(cfg, logger, fs)
        tls_probe = TLSProbe(cfg, logger, fs)
        fsm = FSM(cfg, logger, markers, kv, metrics, registrar=registrar)
        
        # /health: используем in-memory BaseHealth
        self._health = BaseHealth(state=StateEnum.STARTING, status=HealthStatusEnum.WARNING, since_ts=int(time.time()))

        # Обновляем health при смене состояния и при heartbeat
        _orig_on_enter = fsm.on_enter
        def _on_enter_with_health(state: StateEnum) -> None:
            _orig_on_enter(state)
            self._health.state = state
            self._health.since_ts = int(time.time())
            if state is StateEnum.RUNNING:
                self._health.status = HealthStatusEnum.PASSING
            elif state is StateEnum.DEGRADED:
                self._health.status = HealthStatusEnum.WARNING
            elif state in (StateEnum.PAUSED, StateEnum.STOPPING, StateEnum.STOPPED):
                self._health.status = HealthStatusEnum.MAINTENANCE
            elif state is StateEnum.ERROR:
                self._health.status = HealthStatusEnum.CRITICAL
            else:
                self._health.status = HealthStatusEnum.WARNING
        fsm.on_enter = _on_enter_with_health

        _orig_hb = registrar.heartbeat
        def _hb_proxy(svc: str) -> bool:
            ok = _orig_hb(svc)
            if ok:
                self._health.heartbeat_ts = int(time.time())
            return ok
        registrar.heartbeat = _hb_proxy

        try:
            metrics.set_health_path("/health")
            metrics.set_health_provider(lambda: (lambda snap=self._health.snapshot(): dict(snap, svc=cfg.context.name, version=cfg.global_.version))())
        except Exception:
            pass


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

    def initialize(self) -> None:
        self._logger.info("service.init", svc=self._cfg.context.name, version=self._cfg.global_.version)

    def start(self) -> None:
        if hasattr(self._fsm, "required_markers"):
            self._fsm.required_markers = getattr(self.run_profile, "required_markers", set())
        if hasattr(self._fsm, "svc"):
            self._fsm.svc = self._cfg.context.name
        sg = getattr(self.run_profile, "stage_gates", None)
        if sg is not None and hasattr(self._fsm, "stage_gates"):
            from entities.state_enum import StateEnum
            stage_map = {}
            for k, v in sg.items():
                state = k if isinstance(k, StateEnum) else StateEnum[str(k)]
                stage_map[state] = list(v)
            self._fsm.stage_gates = stage_map
        
        # TLS file-watch: реагирует на изменения PEM только в RUNNING
        try:
            certs_dir = str(self._cfg.fs.certs_dir)
            watch_paths = [f"{certs_dir}/privkey.pem", f"{certs_dir}/cert.pem", f"{certs_dir}/fullchain.pem", f"{certs_dir}/ca.crt"]
            def _on_tls_change():
                # Проверка цепочки и hot-reload выполняются только в RUNNING
                try:
                    from entities.state_enum import StateEnum
                    if getattr(self._fsm, "ctx", None) and self._fsm.ctx.current is StateEnum.RUNNING:
                        if self._tls_probe.validate_chain(f"{certs_dir}/cert.pem", f"{certs_dir}/fullchain.pem", f"{certs_dir}/ca.crt"):
                            self._tls_reloader.reload_ssl_context()
                            self._logger.info("tls.reload.on_change", svc=self._cfg.context.name)
                        else:
                            self._logger.warn("tls.reload.skip.invalid_chain", svc=self._cfg.context.name)
                    else:
                        self._logger.info("tls.watch.change.ignored", svc=self._cfg.context.name)
                except Exception as e:
                    self._logger.warn("tls.watch.change.error", svc=self._cfg.context.name, err=type(e).__name__)
            self._tls_watch.start_file_watch(watch_paths, _on_tls_change)
        except Exception as e:
            self._logger.warn("tls.watch.start.error", svc=self._cfg.context.name, err=type(e).__name__)

        self._fsm.run()

    def stop(self) -> None:
        # Остановка вспомогательных подсистем
        try:
            if getattr(self, "_tls_watch", None):
                self._tls_watch.stop()
        except Exception:
            pass
        try:
            if getattr(self, "_metrics", None):
                self._metrics.stop_http_exporter()
        except Exception:
            pass
        # Очистка временных файлов
        try:
            from core.policies.fs_policy import FSPolicy
            if getattr(self, "_cfg", None) and getattr(self, "_fs", None):
                FSPolicy(self._cfg, self._logger, self._metrics if hasattr(self, "_metrics") else None, self._fs).on_flush()
        except Exception:
            pass

        # Дерегистрация в Consul
        try:
            if getattr(self, "_registrar", None):
                self._registrar.deregister(self._cfg.context.name)
        except Exception:
            pass
        self._logger.info("service.stop", svc=self._cfg.context.name)
