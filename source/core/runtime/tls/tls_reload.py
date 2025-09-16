# source\core\runtime\tls_reload.py

"""
Интерфейс "горячей" перезагрузки TLS-материалов.

Сервис, поддерживающий безрестартное обновление ключей/цепочек,
должен предоставить реализацию TLSReloader и передать её через deps.tls_reloader.
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class TLSReloader(Protocol):
    """
    Контракт "горячей" перезагрузки сертификатов/ключей.

    Реализация должна атомарно подменять используемые контексты TLS
    (например, переподнять SSLContext, перечитать файлы, выполнить SIGHUP и т.п.)
    без остановки основного процесса/потока.
    """

    def notify_version(self, version: str) -> None:
        """
        Сообщить о новой версии TLS-бандла.
        Реализация сама решает, нужно ли перечитывать/валидировать/подменять контексты.
        """
        ...
