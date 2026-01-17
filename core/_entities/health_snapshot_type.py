"""
speculorg.terminal.core._entities.health_snapshot_type
=====================================================

Тип данных для in-memory снимка состояния сервиса (HealthSnapshot).
"""

from __future__ import annotations
from typing import Optional, TypedDict
from .state_enum import StateEnum

class HealthSnapshotType(TypedDict, total=False):

    svc: str
    version: str
    state: StateEnum

    # publish timestamp (epoch ms)
    ts_ms: int

    # state enter timestamp (epoch ms)
    since_ts_ms: int

    # optional heartbeat timestamp (epoch ms)
    heartbeat_ts_ms: Optional[int]

    # structured health payload, JSON-serializable
    health: dict[str, object]

    # additional structured details, JSON-serializable
    details: dict[str, object]
