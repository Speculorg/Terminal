from __future__ import annotations
from typing import Protocol, runtime_checkable

from core._entities import HealthSnapshotType


@runtime_checkable
class IService(Protocol):
    """
    Контракт управления тонким сервисом (entrypoint/main вызывает только run()).
    """

    def run(self) -> None: ...

    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def restart(self) -> None: ...
    def stop(self) -> None: ...

    def get_state(self) -> HealthSnapshotType: ...
