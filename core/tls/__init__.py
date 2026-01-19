# Пакет TLS
"""
speculorg.terminal.core.tls
===========================

Фасад для работы с TLS (TLS).
"""


from .paths import TlsPaths
from .tls import TLS

__all__ = ["TLS", "TlsPaths"]
