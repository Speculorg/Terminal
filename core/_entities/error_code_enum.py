"""
speculorg.terminal.core._entities.error_code_enum
=================================================

Перечисление кодов ошибок.
"""

from enum import Enum

class ErrorCodeEnum(str, Enum):
    ERR_TIMEOUT = "ERR_TIMEOUT"
    ERR_PRECONDITION = "ERR_PRECONDITION"
    ERR_REGISTRY = "ERR_REGISTRY"
    ERR_TLS_CHAIN = "ERR_TLS_CHAIN"
    ERR_TLS_RELOAD = "ERR_TLS_RELOAD"
    ERR_PORT = "ERR_PORT"
    ERR_NET = "ERR_NET"
    ERR_KV = "ERR_KV"
    ERR_CAS = "ERR_CAS"
    ERR_PROC = "ERR_PROC"
    ERR_CONFIG = "ERR_CONFIG"
    ERR_JSON = "ERR_JSON"
    ERR_IO = "ERR_IO"
    ERR_PERMS = "ERR_PERMS"
    ERR_UNEXPECTED = "ERR_UNEXPECTED"
