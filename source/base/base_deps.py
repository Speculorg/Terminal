from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from interfaces import IDeps, IConfigs, ILogger, IFS, IMarker, INet, IFSM
from core.configs.loader_env import load_model
from core.configs import Configs
from core.logging import Logger
from core.fs import FS
from core.markers import Markers
from core.net import Net
from core.fsm import FSM
from core.metrics import PrometheusMetrics
from core.tls import TLSReloader, TLSWatch, TLSProbe  # stubs

@dataclass
class BaseDeps(IDeps):
    cfg: IConfigs
    logger: ILogger
    fs: IFS
    markers: IMarker
    net: INet
    fsm: IFSM
    kv: Optional[object] = None
    registrar: Optional[object] = None
    metrics: Optional[object] = None
    tls_reloader: Optional[object] = None
    tls_watch: Optional[object] = None
    tls_probe: Optional[object] = None

    @property
    def configs(self) -> IConfigs:  # back-compat alias
        return self.cfg

    def close(self) -> None:
        return None

class BaseDepsFactory:
    @staticmethod
    def build() -> BaseDeps:
        model, _ = load_model()
        cfg = Configs(model)
        logger = Logger(cfg)
        fs = FS(cfg)
        fs.ensure_layout()
        markers = Markers(cfg, fs)
        net = Net(cfg)
        metrics = PrometheusMetrics()
        fsm = FSM(cfg, logger, markers, fs, net, kv=None, metrics=metrics, registrar=None)
        tls_reloader = TLSReloader(cfg, logger)
        tls_watch = TLSWatch(cfg, logger, fs)
        tls_probe = TLSProbe(cfg, logger, fs)
        return BaseDeps(cfg=cfg, logger=logger, fs=fs, markers=markers, net=net, fsm=fsm,
                        kv=None, registrar=None, metrics=metrics,
                        tls_reloader=tls_reloader, tls_watch=tls_watch, tls_probe=tls_probe)
