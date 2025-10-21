from __future__ import annotations
from dataclasses import dataclass
from base import BaseService, BaseDeps
from interfaces import IRunProfile
from core.configs import Configs
from adapters.logging import JsonLogger
from adapters.metrics import PrometheusMetrics
from core.net import Net
from core.fs import FS
from core.markers import Markers
from core.fsm import FSM
from core.registrar import Registrar
from adapters.registrar import ConsulRegistrar
from core.kv import KV
from adapters.kv import ConsulKV
from core.tls import TLSReloader, TLSWatch, TLSProbe

@dataclass
class VaultRunProfile(IRunProfile):
    required_markers: set[str]

class VaultService(BaseService):
    def __init__(self, deps: BaseDeps) -> None:
        super().__init__(deps)
        # Требуемые маркеры задаём именами файлов, без префикса пути и svc
        self.run_profile = VaultRunProfile(required_markers={'init.done','unseal.done','pki.done'})

def build_deps() -> BaseDeps:
    cfg = Configs()
    logger = JsonLogger(cfg)
    metrics = PrometheusMetrics()
    # Экспорт метрик
    try:
        metrics.start_http_exporter(port=int(cfg.metrics.port), path=cfg.metrics.path)
    except Exception:
        # повторный вызов безопасен; игнорируем если уже запущен
        pass
    net = Net(cfg)
    fs = FS(cfg)
    markers = Markers(cfg, fs=fs)
    kv = KV(cfg, client=ConsulKV(cfg))
    registrar = Registrar(cfg, logger, client=ConsulRegistrar(cfg))
    # В TERM-1 TLS-слой упрощён
    tls_reloader = TLSReloader(cfg, logger)
    tls_watch = TLSWatch(cfg, logger)
    tls_probe = TLSProbe(cfg, logger, fs)
    fsm = FSM(cfg, logger, metrics, kv, markers, registrar)  # заглушка/тонкая реализация
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

if __name__ == "__main__":
    deps = build_deps()
    svc = VaultService(deps)
    svc.initialize()
    svc.start()
