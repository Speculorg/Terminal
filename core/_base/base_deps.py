from __future__ import annotations
from typing import Callable, List, Optional

from _interfaces import (
    IConfigs,
    IDeps,
    IDepsFactory,
    IFS,
    ILogger,
    IMarkers,
    INet,
    IRegistrar,
    ITLS,
)


class BaseDeps(IDeps):
    """
    Базовый контейнер зависимостей (без FSM).

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
        self.cfg = cfg
        self.log = log
        self.fs = fs
        self.markers = markers
        self.net = net
        self.tls = tls
        self.registrar = registrar

        self._closed = False
        self._close_hooks = close_hooks or []

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        for fn in reversed(self._close_hooks):
            try:
                fn()
            except Exception:
                pass


class BaseDepsFactory(IDepsFactory):
    """
    Базовая фабрика Deps.
    
    """

    def build(self) -> IDeps:
        raise NotImplementedError
