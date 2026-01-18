from __future__ import annotations
from pathlib import Path
from typing import Callable, List, Optional

from _base import BaseDepsFactory
from _entities import EventCodeEnum
from _interfaces import (
    IConfigs,
    IDeps,
    IFS,
    ILogger,
    IMarkers,
    INet,
    IRegistrar,
    ITLS,
)

from .deps import Deps


class DepsFactory(BaseDepsFactory):
    """
    Фабрика DI сборки Deps.

    Важно:
    - Сборка детерминированная и идемпотентная.
    - Порядок сборки фиксирован: Configs → Logger → FS → Markers → Net → TLS → Registrar
    - Реальные реализации пока задаются через методы build_* и будут расширяться адаптерами в следующих шагах.
    """

    def build(self) -> IDeps:
        close_hooks: List[Callable[[], None]] = []

        cfg = self.build_configs()
        log = self.build_logger(cfg=cfg)

        log.event(EventCodeEnum.DEPS_BUILD_START, fields={"svc": cfg.service_name})

        try:
            fs = self.build_fs(cfg=cfg, log=log, close_hooks=close_hooks)
            markers = self.build_markers(cfg=cfg, log=log, fs=fs)
            net = self.build_net(cfg=cfg, log=log)
            tls = self.build_tls(cfg=cfg, log=log, fs=fs)
            registrar = self.build_registrar(cfg=cfg, log=log, net=net)

            deps = Deps(
                cfg=cfg,
                log=log,
                fs=fs,
                markers=markers,
                net=net,
                tls=tls,
                registrar=registrar,
                close_hooks=close_hooks,
            )

            log.event(EventCodeEnum.DEPS_BUILD_OK, fields={"svc": cfg.service_name})
            return deps

        except Exception as e:
            try:
                log.event(
                    EventCodeEnum.DEPS_BUILD_FAIL,
                    level="ERROR",
                    message=str(e),
                    fields={"svc": getattr(cfg, "service_name", "unknown")},
                )
            except Exception:
                pass
            # пробуем закрыть то, что уже было собрано
            for fn in reversed(close_hooks):
                try:
                    fn()
                except Exception:
                    pass
            raise

    # --- build steps (override points) ---

    def build_configs(self) -> IConfigs:
        raise NotImplementedError

    def build_logger(self, *, cfg: IConfigs) -> ILogger:
        raise NotImplementedError

    def build_fs(self, *, cfg: IConfigs, log: ILogger, close_hooks: List[Callable[[], None]]) -> IFS:
        raise NotImplementedError

    def build_markers(self, *, cfg: IConfigs, log: ILogger, fs: IFS) -> IMarkers:
        raise NotImplementedError

    def build_net(self, *, cfg: IConfigs, log: ILogger) -> INet:
        raise NotImplementedError

    def build_tls(self, *, cfg: IConfigs, log: ILogger, fs: IFS) -> ITLS:
        raise NotImplementedError

    def build_registrar(self, *, cfg: IConfigs, log: ILogger, net: INet) -> IRegistrar:
        raise NotImplementedError
