from __future__ import annotations
from typing import Protocol, runtime_checkable
from .i_configs import IConfigs
from .i_logger import ILogger
from .i_metrics import IMetrics
from .i_net import INet
from .i_fs import IFS
from .i_markers import IMarkers
from .i_kv import IKV
from .i_registrar import IRegistrar
from .i_fsm import IFSM
from .i_tls import ITLSReloader, ITLSWatch, ITLSProbe

@runtime_checkable
class IDeps(Protocol):
    configs: IConfigs
    logger: ILogger
    fs: IFS
    markers: IMarkers
    kv: IKV
    registrar: IRegistrar
    net: INet
    metrics: IMetrics
    tls_reloader: ITLSReloader
    tls_watch: ITLSWatch
    tls_probe: ITLSProbe
    fsm: IFSM

    def close(self) -> None: ...
