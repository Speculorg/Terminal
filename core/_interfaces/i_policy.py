from __future__ import annotations
from typing import Protocol, runtime_checkable

from _entities import PolicyResultType, StateEnum


@runtime_checkable
class IPolicy(Protocol):
    """
    Политика — единица логики проверки/действия в FSM.
    """

    @property
    def name(self) -> str: ...

    def run(self, *, state: StateEnum) -> PolicyResultType:
        ...
