# Пакет контрактов ядра
"""
speculorg.terminal.core._interfaces
===================================

Порты (контракты) для компонентов ядра.
"""

from .i_deps import IDeps, IDepsFactory
from .i_configs import IConfigs
from .i_logger import ILogger
from .i_fs import IFS
from .i_markers import IMarkers
from .i_net import INet
from .i_tls import ITLS
from .i_registrar import IRegistrar
from .i_fsm import IFSM
from .i_policy import IPolicy
from .i_run_profile import IRunProfile
from .i_service import IService

__all__ = [
    "IDeps",
    "IDepsFactory",
    "IConfigs",
    "ILogger",
    "IFS",
    "IMarkers",
    "INet",
    "ITLS",
    "IRegistrar",
    "IFSM",
    "IPolicy",
    "IRunProfile",
    "IService",
]
