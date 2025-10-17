from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from entities import StateEnum, HealthStatusEnum

@dataclass
class BaseHealth:
    state: StateEnum = StateEnum.STARTING
    status: HealthStatusEnum = HealthStatusEnum.WARNING
    since_ts: int = 0
    heartbeat_ts: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "status": self.status.value,
            "since_ts": self.since_ts,
            "heartbeat_ts": self.heartbeat_ts,
            "details": self.details,
        }
