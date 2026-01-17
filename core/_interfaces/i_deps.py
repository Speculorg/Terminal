from __future__ import annotations
from typing import Protocol, runtime_checkable

from _interfaces.i_configs import IConfigs
from _interfaces.i_fs import IFS
from _interfaces.i_logger import ILogger
from _interfaces.i_markers import IMarkers
from _interfaces.i_net import INet
from _interfaces.i_registrar import IRegistrar
from _interfaces.i_tls import ITLS


@runtime_checkable
class IDeps(Protocol):
    """
    Контейнер зависимостей ядра (без FSM).
    Собирается фабрикой и живёт столько же, сколько процесс сервиса.
    """

    cfg: IConfigs
    log: ILogger
    fs: IFS
    markers: IMarkers
    net: INet
    tls: ITLS
    registrar: IRegistrar

    def close(self) -> None:
        """Освободить ресурсы (файлы/сокеты/сессии). Должно быть идемпотентно."""
        ...


@runtime_checkable
class IDepsFactory(Protocol):
    """
    Фабрика сборки контейнера зависимостей.
    Сборка должна быть детерминированной и происходить в фиксированном порядке.
    """

    def build(self) -> IDeps:
        ...
