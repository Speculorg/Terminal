# source\core\kv\markers.py

"""
core.kv.markers
Фасад для маркеров (идемпотентные флажки).
Все записи выполняются через CAS с backoff.
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Tuple

from .base import KV
from . import paths
from .utils import cas_update_json, ensure_bool_marker, now_iso
from core.logging import get_logger

log = get_logger("kv.markers")


class MarkersFacade:
    def __init__(self, kv: KV) -> None:
        self.kv = kv

    # ----- generic helpers -----
    def _get_json_both_prefixes(self, key_marker: str) -> Tuple[Optional[Any], Optional[int]]:
        """Для совместимости читаем и 'marker/*', и 'markers/*'."""
        val, idx = self.kv.get_json(key_marker)
        if val is not None or idx is not None:
            return val, idx
        legacy = key_marker.replace(paths.MARKER + "/", paths.LEGACY_MARKERS + "/", 1)
        return self.kv.get_json(legacy)

    def _put_json_marker(self, key_marker: str, obj: Any, *, cas: Optional[int] = None) -> bool:
        return self.kv.put_json(key_marker, obj, cas=cas)

    # ----- bool markers -----
    def ensure_true(self, key_marker: str, *, tries: int = 10) -> bool:
        """Идемпотентно установить marker=True (CAS + retry)."""
        return ensure_bool_marker(
            lambda: self._get_json_both_prefixes(key_marker),
            lambda obj, cas: self._put_json_marker(key_marker, obj, cas=cas),
            tries=tries,
        )

    def get(self, key_marker: str) -> Tuple[Optional[Any], Optional[int]]:
        return self._get_json_both_prefixes(key_marker)

    # ----- certs status marker -----
    def publish_certs_status(self, *, version: str | int, meta: Optional[Dict[str, Any]] = None, tries: int = 10) -> bool:
        """
        Пишет JSON:
        {
          "version": "<int|hash>",
          "updated_at": "<iso>",
          "meta": {...}
        }
        """
        key = paths.CERTS_STATUS

        def _upd(old: Optional[Any]) -> Any:
            return {
                "version": str(version),
                "updated_at": now_iso(),
                "meta": meta or {},
            }

        ok = cas_update_json(
            lambda: self.kv.get_json(key),
            lambda obj, cas: self.kv.put_json(key, obj, cas=cas),
            _upd,
            tries=tries,
        )
        if not ok:
            log.error("evt=marker.certs_status.write.fail key=%s", key)
        return ok
