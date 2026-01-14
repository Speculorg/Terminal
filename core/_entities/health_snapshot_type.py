"""
speculorg.terminal.core._entities.health_snapshot_type
=====================================================

Тип данных для снимка состояния сервиса (HealthSnapshot).
"""
from typing import TypedDict
from .state_enum import StateEnum


class HealthSnapshotType(TypedDict):
    """
    Структура данных для снимка состояния сервиса.
    """
    svc: str
    state: StateEnum
    timestamp: float
    heartbeat_ts: float
    # Другие релевантные метаданные будут добавлены позже