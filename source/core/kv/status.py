# source\core\kv\status.py

from __future__ import annotations
import time
from typing import Any, Dict, Optional

from .base import KVClient
from . import paths
from .utils import cas_update_json
from core.runtime.status import ServiceStatus


class StatusFacade:
    """
    Фасад для записи "живых" статусов сервисов в Consul KV.

    Инварианты:
      - только один ключ на сервис: status/<svc>/status
      - структура хранится в JSON, обновляется через CAS (идемпотентно)
      - поля: service, ts, phase, status, meta, heartbeat, tls_active
    """

    def __init__(self, client: KVClient) -> None:
        self._c = client

    # ---- ключи ----
    def _key_status(self, svc: str) -> str:
        return paths.status_key(svc)

    # ---- операции верхнего уровня ----

    def update(self, svc: str, st: ServiceStatus, *, meta: Optional[Dict[str, Any]] = None) -> bool:
        """
        Атомарно обновляет phase и status (+ service, ts, meta) одним CAS-патчем.
        """
        key = self._key_status(svc)
        now = int(time.time())

        def _patch(cur: Dict[str, Any]) -> Dict[str, Any]:
            cur = dict(cur or {})
            cur.setdefault("service", svc)
            cur["ts"] = now
            cur["phase"] = st.value          # строковое значение фазы (например, "RUNNING")
            cur["status"] = st.name          # имя enum (например, "RUNNING")
            if meta is not None:
                # не перетираем полностью, а мягко обновляем
                m = dict(cur.get("meta") or {})
                m.update(meta)
                cur["meta"] = m
            return cur

        return cas_update_json(self._c, key, _patch)

    def set_phase(self, svc: str, phase: str, *, meta: Optional[Dict[str, Any]] = None) -> bool:
        """
        Сохранено для обратной совместимости; предпочтительнее использовать update().
        """
        key = self._key_status(svc)
        now = int(time.time())

        def _patch(cur: Dict[str, Any]) -> Dict[str, Any]:
            cur = dict(cur or {})
            cur.setdefault("service", svc)
            cur["ts"] = now
            cur["phase"] = phase
            if meta is not None:
                m = dict(cur.get("meta") or {})
                m.update(meta)
                cur["meta"] = m
            return cur

        return cas_update_json(self._c, key, _patch)

    def set_status(self, svc: str, st: ServiceStatus, *, meta: Optional[Dict[str, Any]] = None) -> bool:
        """
        Сохранено для обратной совместимости; предпочтительнее использовать update().
        """
        key = self._key_status(svc)
        now = int(time.time())

        def _patch(cur: Dict[str, Any]) -> Dict[str, Any]:
            cur = dict(cur or {})
            cur.setdefault("service", svc)
            cur["ts"] = now
            cur["status"] = st.name
            if meta is not None:
                m = dict(cur.get("meta") or {})
                m.update(meta)
                cur["meta"] = m
            return cur

        return cas_update_json(self._c, key, _patch)

    def heartbeat(
        self,
        svc: str,
        *,
        tls_active: bool = False,
        meta: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Обновляет моментальный heartbeat и флаг TLS.
        """
        key = self._key_status(svc)
        now = int(time.time())

        def _patch(cur: Dict[str, Any]) -> Dict[str, Any]:
            cur = dict(cur or {})
            cur.setdefault("service", svc)
            cur["heartbeat"] = now
            cur["tls_active"] = bool(tls_active)
            if meta is not None:
                m = dict(cur.get("meta") or {})
                m.update(meta)
                cur["meta"] = m
            return cur

        return cas_update_json(self._c, key, _patch)
