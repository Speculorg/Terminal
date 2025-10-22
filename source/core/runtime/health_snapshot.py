from __future__ import annotations
from typing import Dict, Any

class HealthSnapshot:
    """In-memory health. Никакой записи на диск."""
    def __init__(self) -> None:
        self._data: Dict[str, Any] = {
            "state": None,
            "health": {"status": None},
            "since_ts": 0,
            "heartbeat_ts": None,
            "svc": "",
            "version": "",
            "details": {},
        }

    def set_basic(self, *, state: str, status: str, since_ts: int, svc: str, version: str) -> None:
        self._data.update({"state": state, "since_ts": since_ts, "svc": svc, "version": version})
        self._data["health"]["status"] = status

    def set_heartbeat(self, ts: int) -> None:
        self._data["heartbeat_ts"] = ts

    def set_details(self, details: Dict[str, Any]) -> None:
        self._data["details"] = dict(details)

    def snapshot(self) -> Dict[str, Any]:
        return dict(self._data)
