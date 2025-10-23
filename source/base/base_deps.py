from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from interfaces import IConfigs, ILogger, IFS, IMarker, IKV, IRegistrar, INet, IMetrics, IDeps

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

    def close(self) -> None:
        # крючок для аккуратного завершения, если появятся ресурсы
        pass
