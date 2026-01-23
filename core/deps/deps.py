from __future__ import annotations
from typing import Callable, List, Optional

from core._base import BaseDeps
from core._interfaces import (
    IConfigs,
    IFS,
    ILogger,
    IMarkers,
    INet,
    IRegistrar,
    ITLS,
)


class Deps(BaseDeps):
    """
    Стандартный контейнер зависимостей ядра.
    Используется всеми сервисами (TERM-1).
    """

    def __init__(
        self,
        *,
        cfg: IConfigs,
        log: ILogger,
        fs: IFS,
        markers: IMarkers,
        net: INet,
        tls: ITLS,
        registrar: IRegistrar,
        close_hooks: Optional[List[Callable[[], None]]] = None,
    ) -> None:
        super().__init__(
            cfg=cfg,
            log=log,
            fs=fs,
            markers=markers,
            net=net,
            tls=tls,
            registrar=registrar,
            close_hooks=close_hooks,
        )
