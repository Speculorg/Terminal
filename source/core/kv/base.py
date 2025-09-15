# source\core\kv\base.py

"""
core.kv.base

Единая абстракция KV и aggregate-root для подсистем состояния (markers/status/certs/configs).
- Единый SoT (Source of Truth).
- CAS/идемпотентность через utils.cas_update_json().
- Только стандартная библиотека.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional, Protocol, Tuple, runtime_checkable

from core.logging import get_logger

log = get_logger("kv.base")


@dataclass(frozen=True)
class KVEntry:
    value: Optional[bytes]
    modify_index: Optional[int]


@runtime_checkable
class KVClient(Protocol):
    """Минимальный протокол клиента KV-хранилища (Consul и др.)."""

    # ----- raw bytes -----
    def get_raw(self, key: str) -> KVEntry: ...
    def put_raw(self, key: str, value: bytes, *, cas: Optional[int] = None) -> bool: ...
    def delete(self, key: str) -> bool: ...

    # ----- text helpers -----
    def get_text(self, key: str) -> Tuple[Optional[str], Optional[int]]: ...
    def put_text(self, key: str, text: str, *, cas: Optional[int] = None) -> bool: ...

    # ----- json helpers -----
    def get_json(self, key: str) -> Tuple[Optional[Any], Optional[int]]: ...
    def put_json(self, key: str, obj: Any, *, cas: Optional[int] = None) -> bool: ...


class KV:
    """
    Facade/Aggregate-root:
    - инкапсулирует клиент;
    - предоставляет прямые геттеры/сеттеры;
    - агрегирует разделы: Marker/Status/Cert/Config.
    """
    def __init__(self, client: KVClient):
        self.client: KVClient = client

        # Отложенный импорт, чтобы исключить циклы
        from .markers import MarkersFacade
        from .status import StatusFacade
        from .certs import CertsFacade
        from .configs import ConfigsFacade

        self.marker = MarkersFacade(self)  # marker/*
        self.status = StatusFacade(self)   # status/*
        self.cert = CertsFacade(self)      # cert/*
        self.config = ConfigsFacade(self)  # config/*

    # ---- low-level passthroughs ----
    def get_raw(self, key: str) -> KVEntry:
        return self.client.get_raw(key)

    def put_raw(self, key: str, value: bytes, *, cas: Optional[int] = None) -> bool:
        return self.client.put_raw(key, value, cas=cas)

    def delete(self, key: str) -> bool:
        return self.client.delete(key)

    # ---- typed helpers ----
    def get_text(self, key: str) -> Tuple[Optional[str], Optional[int]]:
        return self.client.get_text(key)

    def put_text(self, key: str, text: str, *, cas: Optional[int] = None) -> bool:
        return self.client.put_text(key, text, cas=cas)

    def get_json(self, key: str) -> Tuple[Optional[Any], Optional[int]]:
        return self.client.get_json(key)

    def put_json(self, key: str, obj: Any, *, cas: Optional[int] = None) -> bool:
        return self.client.put_json(key, obj, cas=cas)
