from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from interfaces import IConfigs, ILogger, IFS, IMarker, IKV, IRegistrar, INet, IMetrics, IDeps, ITLSProbe, ITLSReloader, ITLSWatch, IFSM

@dataclass
class BaseDeps(IDeps):
    """Простой контейнер зависимостей. Экземпляры создаются в composition-root."""
    configs: IConfigs
    logger: ILogger
    fs: IFS
    markers: IMarker
    kv: IKV
    registrar: IRegistrar
    net: INet
    metrics: IMetrics
    tls_reloader: ITLSReloader
    tls_watch: ITLSWatch
    tls_probe: ITLSProbe
    fsm: IFSM

    def close(self) -> None:
        # крючок для аккуратного завершения, если появятся ресурсы
        pass
