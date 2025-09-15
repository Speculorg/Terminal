# source\core\kv\status.py

"""
core.kv.status
Фасад записи статусов/фаз сервисов (CAS, идемпотентные апдейты).
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Tuple

from .base import KV
from . import paths
from .utils import cas_update_json, now_iso
from core.logging import get_logger
from core.runtime.status import ServiceStatus

log = get_logger("kv.status")


class StatusFacade:
    def __init__(self, kv: KV) -> None:
        self.kv = kv

    def _key(self, svc: str) -> str:
        return paths.status_key(svc)

    def get(self, svc: str) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
        return self.kv.get_json(self._key(svc))

    def _update(self, svc: str, patch: Dict[str, Any], *, tries: int = 10) -> bool:
        key = self._key(svc)

        def _upd(old: Optional[Dict[str, Any]]) -> Dict[str, Any]:
            base = old.copy() if isinstance(old, dict) else {}
            base.setdefault("service", svc)
            base["ts"] = now_iso()
            for k, v in patch.items():
                base[k] = v
            return base

        return cas_update_json(
            lambda: self.kv.get_json(key),
            lambda obj, cas: self.kv.put_json(key, obj, cas=cas),
            _upd,
            tries=tries,
        )

    # ----- shortcuts -----
    def set_phase(self, svc: str, phase: str, *, meta: Optional[Dict[str, Any]] = None) -> bool:
        patch: Dict[str, Any] = {"phase": str(phase)}
        if meta:
            patch["meta"] = meta
        return self._update(svc, patch)

    def set_status(self, svc: str, status: ServiceStatus, *, meta: Optional[Dict[str, Any]] = None) -> bool:
        patch: Dict[str, Any] = {"status": status.value}
        if meta:
            patch["meta"] = meta
        return self._update(svc, patch)

    def heartbeat(self, svc: str, *, tls_active: Optional[bool] = None, meta: Optional[Dict[str, Any]] = None) -> bool:
        patch: Dict[str, Any] = {"heartbeat": now_iso()}
        if tls_active is not None:
            patch["tls_active"] = bool(tls_active)
        if meta:
            patch["meta"] = meta
        return self._update(svc, patch)
