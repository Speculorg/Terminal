from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from interfaces import IConfigs, ILogger, IFS, IMarker, IKV, IRegistrar, INet, IMetrics, IDeps, ITLSProbe, ITLSReloader, ITLSWatch, IFSM
from base.base_net import BaseNet  # type: ignore

from core.configs import Configs, load_model
from core.fs import Paths, MarkersStore, ensure_layout
from core.fsm import FSM  # type: ignore

from adapters.logging import JsonLogger
from adapters.kv import ConsulKV
from adapters.registrar import ConsulRegistrar
from adapters.metrics import PromMetrics


@dataclass
class BaseDeps(IDeps):
    cfg: IConfigs
    logger: ILogger
    fs: IFS
    markers: IMarker
    fsm: IFSM
    registrar: IRegistrar
    net: INet
    metrics: IMetrics
    tls_reloader: ITLSReloader
    tls_watch: ITLSWatch
    tls_probe: ITLSProbe
    kv: IKV

    def close(self) -> None:
        # ресурсы для закрытия отсутствуют
        pass

class BaseDepsFactory:
    @staticmethod
    def build(env_file_path: Optional[str] = None) -> BaseDeps:
        model, merged_env = load_model(env_file_path)
        cfg = Configs(model)
        paths = Paths.from_cfg(cfg)
        ensure_layout(paths)
        logger = JsonLogger(cfg)
        markers = MarkersStore(paths)
        fsm = FSM
        registrar = ConsulRegistrar(cfg, logger)
        net = BaseNet(cfg)
        metrics = PromMetrics()
        tls_reloader = type("NoopReloader",(object,),{"reload":lambda self: None})()
        tls_watch = type("NoopWatch",(object,),{"start_watch":lambda self,paths,debounce_ms: None})()
        tls_probe = type("NoopProbe",(object,),{"validate_chain":lambda self,cert,full,ca: None})()
        kv = ConsulKV(cfg)
        return BaseDeps(
            cfg=cfg,
            logger=logger,
            fs=paths,
            markers=markers,
            net=net,
            fsm=fsm,                    # type: ignore
            registrar=registrar,        # type: ignore
            tls_reloader=tls_reloader,  # type: ignore
            tls_watch=tls_watch,        # type: ignore
            tls_probe=tls_probe,        # type: ignore
            kv=kv,                      # type: ignore
            metrics=metrics,            # type: ignore
        )
