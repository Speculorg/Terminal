from __future__ import annotations
from typing import Protocol

class IConfigs(Protocol):
    """
    Типобезопасный фасад настроек.
    Только свойства секций. Источник не раскрывается.
    Типобезопасный фасад настроек.
    Доступ только через секции-атрибуты. Источник данных не раскрывается.
    """
    @property
    def global_(self): ...  # alias для "global" из фасада

    @property
    def context(self): ...

    @property
    def consul(self): ...

    @property
    def vault(self): ...

    @property
    def traefik(self): ...

    @property
    def logging(self): ...

    @property
    def metrics(self): ...

    @property
    def fs(self): ...

    @property
    def tls(self): ...

    @property
    def kv(self): ...

    @property
    def fsm(self): ...

    @property
    def registrar(self): ...

    @property
    def version(self) -> str: ...

    @property
    def domain_root(self) -> str: ...

    @property
    def config_hash(self) -> str: ...