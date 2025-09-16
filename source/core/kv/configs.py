# source\core\kv\configs.py

"""
core.kv.configs
Чтение/запись несекретных конфигураций (global и per-service) с поддержкой
идемпотентных ensure/set_if_absent (CAS + backoff).
"""

from __future__ import annotations
from typing import Any, Optional, Tuple, Dict

from .base import KV
from . import paths
from .utils import cas_update_json
from core.logging import get_logger

log = get_logger("kv.configs")


class ConfigsFacade:
    def __init__(self, kv: KV) -> None:
        self.kv = kv

    # ---- global ----

    def get_domain_root(self) -> Tuple[Optional[str], Optional[int]]:
        return self.kv.get_text(paths.CONFIG_GLOBAL_DOMAIN_ROOT)

    def set_domain_root(self, domain: str, *, cas: Optional[int] = None) -> bool:
        return self.kv.put_text(paths.CONFIG_GLOBAL_DOMAIN_ROOT, domain, cas=cas)

    def ensure_domain_root(self, domain: str, *, tries: int = 10) -> bool:
        key = paths.CONFIG_GLOBAL_DOMAIN_ROOT

        def _patch(cur: Optional[str]) -> str:
            return cur if (cur is not None and str(cur).strip()) else str(domain)

        return cas_update_json(
            lambda: self.kv.get_text(key),
            lambda obj, cas: self.kv.put_text(key, str(obj or ""), cas=cas),
            _patch,
            tries=tries,
        )

    def get_config_hash(self) -> Tuple[Optional[str], Optional[int]]:
        return self.kv.get_text(paths.CONFIG_GLOBAL_CONFIG_HASH)

    def set_config_hash(self, sha256_hex: str, *, cas: Optional[int] = None) -> bool:
        return self.kv.put_text(paths.CONFIG_GLOBAL_CONFIG_HASH, sha256_hex, cas=cas)

    def ensure_config_hash(self, sha256_hex: str, *, tries: int = 10) -> bool:
        key = paths.CONFIG_GLOBAL_CONFIG_HASH

        def _patch(cur: Optional[str]) -> str:
            return cur if (cur is not None and str(cur).strip()) else str(sha256_hex)

        return cas_update_json(
            lambda: self.kv.get_text(key),
            lambda obj, cas: self.kv.put_text(key, str(obj or ""), cas=cas),
            _patch,
            tries=tries,
        )

    # ---- per-service ----

    def get_svc_text(self, svc: str, name: str) -> Tuple[Optional[str], Optional[int]]:
        return self.kv.get_text(paths.config_svc_key(svc, name))

    def set_svc_text(self, svc: str, name: str, value: str, *, cas: Optional[int] = None) -> bool:
        return self.kv.put_text(paths.config_svc_key(svc, name), value, cas=cas)

    def ensure_svc_text(self, svc: str, name: str, value: str, *, tries: int = 10) -> bool:
        key = paths.config_svc_key(svc, name)

        def _patch(cur: Optional[str]) -> str:
            return cur if (cur is not None and str(cur).strip()) else str(value)

        return cas_update_json(
            lambda: self.kv.get_text(key),
            lambda obj, cas: self.kv.put_text(key, str(obj or ""), cas=cas),
            _patch,
            tries=tries,
        )

    def get_svc_json(self, svc: str, name: str) -> Tuple[Optional[Any], Optional[int]]:
        return self.kv.get_json(paths.config_svc_key(svc, name))

    def set_svc_json(self, svc: str, name: str, obj: Any, *, cas: Optional[int] = None) -> bool:
        return self.kv.put_json(paths.config_svc_key(svc, name), obj, cas=cas)

    def ensure_svc_json(self, svc: str, name: str, default_obj: Any, *, tries: int = 10) -> bool:
        key = paths.config_svc_key(svc, name)

        def _patch(cur: Optional[Any]) -> Any:
            # если уже есть валидное значение - оставляем; иначе пишем default_obj
            return default_obj if cur is None else cur

        return cas_update_json(
            lambda: self.kv.get_json(key),
            lambda obj, cas: self.kv.put_json(key, obj, cas=cas),
            _patch,
            tries=tries,
        )
