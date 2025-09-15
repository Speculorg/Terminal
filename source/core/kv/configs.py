# source\core\kv\configs.py

"""
core.kv.configs
Чтение/запись несекретных конфигураций (global и per-service).
"""

from __future__ import annotations
from typing import Any, Optional, Tuple

from .base import KV
from . import paths
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

    def get_config_hash(self) -> Tuple[Optional[str], Optional[int]]:
        return self.kv.get_text(paths.CONFIG_GLOBAL_CONFIG_HASH)

    def set_config_hash(self, sha256_hex: str, *, cas: Optional[int] = None) -> bool:
        return self.kv.put_text(paths.CONFIG_GLOBAL_CONFIG_HASH, sha256_hex, cas=cas)

    # ---- per-service ----
    def get_svc_text(self, svc: str, name: str) -> Tuple[Optional[str], Optional[int]]:
        return self.kv.get_text(paths.config_svc_key(svc, name))

    def set_svc_text(self, svc: str, name: str, value: str, *, cas: Optional[int] = None) -> bool:
        return self.kv.put_text(paths.config_svc_key(svc, name), value, cas=cas)

    def get_svc_json(self, svc: str, name: str) -> Tuple[Optional[Any], Optional[int]]:
        return self.kv.get_json(paths.config_svc_key(svc, name))

    def set_svc_json(self, svc: str, name: str, obj: Any, *, cas: Optional[int] = None) -> bool:
        return self.kv.put_json(paths.config_svc_key(svc, name), obj, cas=cas)
