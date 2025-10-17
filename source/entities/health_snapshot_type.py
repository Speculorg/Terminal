from typing import TypedDict, Optional
from .state_enum import StateEnum
from .health_status_enum import HealthStatusEnum

class HealthSnapshotType(TypedDict, total=False):
    state: StateEnum
    health: dict
    since_ts: int
    heartbeat_ts: Optional[int]
    svc: str
    version: str
    details: dict
