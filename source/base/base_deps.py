from __future__ import annotations
from dataclasses import dataclass
from interfaces import (
    IDeps, IConfigs, ILogger, IMetrics, INet, IFS, IMarker,
    IKV, IRegistrar, IFSM, ITLSReloader, ITLSWatch, ITLSProbe
)

@dataclass(frozen=True)
class BaseDeps(IDeps):
    configs: IConfigs
    logger: ILogger
    metrics: IMetrics
    net: INet
    fs: IFS
    markers: IMarker
    kv: IKV
    registrar: IRegistrar
    tls_reloader: ITLSReloader
    tls_watch: ITLSWatch
    tls_probe: ITLSProbe
    fsm: IFSM  # assigned by BaseService after construction
