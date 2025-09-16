# source\core\kv\markers.py

"""
core.kv.markers
Фасад для маркеров (идемпотентные флажки) с подпространствами:
- Специализированные: KV.marker.consul.*, KV.marker.vault.*, KV.marker.traefik.*
- Универсальные для любого сервиса: KV.marker.svc("<name>").initialized/registered/mtls_ready

Все записи выполняются через CAS с backoff.
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Tuple

from .base import KV
from . import paths
from .utils import cas_update_json, ensure_bool_marker, now_iso
from core.logging import get_logger

log = get_logger("kv.markers")


# ----------------------------- Внутренний «булевый» маркер -----------------------------

class _BoolMarker:
    """
    Объект-обёртка над конкретным bool-маркером.
    Пример использования:
        KV.marker.consul.initialized.ensure()
        KV.marker.vault.pki_root_ready.ensure()
        KV.marker.svc("gateway").registered.ensure()
    """

    def __init__(self, kv: KV, key_marker: str) -> None:
        self._kv = kv
        self._key = key_marker

    def _get_json_both_prefixes(self) -> Tuple[Optional[Any], Optional[int]]:
        """Совместимость: читаем и 'marker/*', и старый 'markers/*'."""
        val, idx = self._kv.get_json(self._key)
        if val is not None or idx is not None:
            return val, idx
        legacy = self._key.replace(paths.MARKER + "/", paths.LEGACY_MARKERS + "/", 1)
        return self._kv.get_json(legacy)

    def ensure(self, *, tries: int = 10) -> bool:
        """Идемпотентно установить marker=True (CAS + retry)."""
        return ensure_bool_marker(
            lambda: self._get_json_both_prefixes(),
            lambda obj, cas: self._kv.put_json(self._key, obj, cas=cas),
            tries=tries,
        )

    def get(self) -> Tuple[Optional[Any], Optional[int]]:
        return self._get_json_both_prefixes()


# ----------------------------- Универсальные маркеры для любого сервиса -----------------------------

def _svc_flag_key(svc: str, flag: str) -> str:
    """
    Генерация ключа маркера в неймспейсе marker/<svc>/<flag>.
    Если появится фабрика путей в paths, плавно переключимся на неё.
    """
    mk = getattr(paths, "marker_svc_flag", None)
    if callable(mk):
        return mk(svc, flag)  # type: ignore[misc]
    return f"{paths.MARKER}/{svc}/{flag}"


class _GenericSvcMarkers:
    """
    Неймспейс для произвольного сервиса:
        ns = KV.marker.svc("gateway")
        ns.initialized.ensure()
        ns.registered.ensure()
        ns.mtls_ready.ensure()
        # а также любые нестандартные флаги:
        ns.flag("catalog_synchronized").ensure()
    """

    def __init__(self, kv: KV, svc: str) -> None:
        self._kv = kv
        self._svc = svc
        # Предопределённые флаги
        self.initialized = _BoolMarker(kv, _svc_flag_key(svc, "initialized"))
        self.registered = _BoolMarker(kv, _svc_flag_key(svc, "registered"))
        self.mtls_ready = _BoolMarker(kv, _svc_flag_key(svc, "mtls_ready"))

    def flag(self, name: str) -> _BoolMarker:
        """Произвольный флаг в пространстве marker/<svc>/<name>."""
        return _BoolMarker(self._kv, _svc_flag_key(self._svc, name))


# ----------------------------- Подпространства для конкретных сервисов -----------------------------

class _ConsulMarkers:
    def __init__(self, kv: KV) -> None:
        self.initialized = _BoolMarker(kv, paths.M_CONSUL_INITIALIZED)
        self.mtls_ready = _BoolMarker(kv, paths.M_CONSUL_MTLS_READY)
        self.catalog_synchronized = _BoolMarker(kv, paths.M_CONSUL_CATALOG_SYNCED)


class _VaultMarkers:
    def __init__(self, kv: KV) -> None:
        self.initialized = _BoolMarker(kv, paths.M_VAULT_INITIALIZED)
        self.pki_root_ready = _BoolMarker(kv, paths.M_VAULT_PKI_ROOT_READY)
        self.pki_int_ready = _BoolMarker(kv, paths.M_VAULT_PKI_INT_READY)
        self.pki_leaf_ready = _BoolMarker(kv, paths.M_VAULT_PKI_LEAF_READY)

    # Специализированный marker JSON со статусом сертификатов
    def publish_certs_status(self, *, version: str | int, meta: Optional[Dict[str, Any]] = None, tries: int = 10) -> bool:
        """
        Пишет JSON:
        {
          "version": "<int|hash>",
          "updated_at": "<iso>",
          "meta": {...}
        }
        """
        key = paths.M_VAULT_CERTS_STATUS

        def _upd(_: Optional[Any]) -> Any:
            return {
                "version": str(version),
                "updated_at": now_iso(),
                "meta": dict(meta or {}),
            }

        ok = cas_update_json(
            lambda: self._kv.get_json(key),
            lambda obj, cas: self._kv.put_json(key, obj, cas=cas),
            _upd,
            tries=tries,
        )
        if not ok:
            log.error("evt=marker.certs_status.write.fail key=%s", key)
        return ok

    def get_certs_status(self) -> Tuple[Optional[Any], Optional[int]]:
        return self._kv.get_json(paths.M_VAULT_CERTS_STATUS)

    @property
    def _kv(self) -> KV:
        # берём kv из одного из _BoolMarker (initialized)
        return self.initialized._kv  # type: ignore[attr-defined]


class _TraefikMarkers:
    def __init__(self, kv: KV) -> None:
        self.initialized = _BoolMarker(kv, paths.M_TRAEFIK_INITIALIZED)
        self.registered = _BoolMarker(kv, paths.M_TRAEFIK_REGISTERED)
        self.consul_catalog_available = _BoolMarker(kv, paths.M_TRAEFIK_CONSUL_CATALOG_OK)


# ----------------------------- Публичный фасад -----------------------------

class MarkersFacade:
    """
    Внешний фасад маркеров. Доступ к именованным маркерам:
        KV.marker.consul.initialized.ensure()
        KV.marker.vault.pki_root_ready.ensure()
        KV.marker.traefik.registered.ensure()
        KV.marker.svc("<name>").initialized.ensure()
    Сохранены и generic-методы для совместимости.
    """

    def __init__(self, kv: KV) -> None:
        self._kv = kv
        # Подпространства
        self.consul = _ConsulMarkers(kv)
        self.vault = _VaultMarkers(kv)
        self.traefik = _TraefikMarkers(kv)

    # ----- Универсальный неймспейс для любого сервиса -----

    def svc(self, name: str) -> _GenericSvcMarkers:
        return _GenericSvcMarkers(self._kv, name)

    # ----- generic helpers (совместимость) -----

    def ensure_true(self, key_marker: str, *, tries: int = 10) -> bool:
        """Идемпотентно установить marker=True (CAS + retry)."""
        return ensure_bool_marker(
            lambda: self._get_json_both_prefixes(key_marker),
            lambda obj, cas: self._kv.put_json(key_marker, obj, cas=cas),
            tries=tries,
        )

    def get(self, key_marker: str) -> Tuple[Optional[Any], Optional[int]]:
        return self._get_json_both_prefixes(key_marker)

    # ----- внутреннее -----

    def _get_json_both_prefixes(self, key_marker: str) -> Tuple[Optional[Any], Optional[int]]:
        """Совместимость: читаем и 'marker/*', и 'markers/*'."""
        val, idx = self._kv.get_json(key_marker)
        if val is not None or idx is not None:
            return val, idx
        legacy = key_marker.replace(paths.MARKER + "/", paths.LEGACY_MARKERS + "/", 1)
        return self._kv.get_json(legacy)
