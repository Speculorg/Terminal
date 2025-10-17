"""
Interfaces package: stable behavioral contracts (no implementations).
TERM-1: Stage 1 (Interfaces)
"""
from .i_service import IService
from .i_run_profile import IRunProfile
from .i_deps import IDeps
from .i_configs import IConfigs
from .i_registrar import IRegistrar
from .i_fs import IFS
from .i_marker import IMarker
from .i_kv import IKV
from .i_logger import ILogger
from .i_metrics import IMetrics
from .i_health_check import IHealthCheck
from .i_net import INet
from .i_fsm import IFSM
from .i_tls import ITLSReloader, ITLSWatch, ITLSProbe

__all__ = [
    "IService", "IRunProfile", "IDeps", "IConfigs", "IRegistrar",
    "IFS", "IMarker", "IKV", "ILogger", "IMetrics", "IHealthCheck",
    "INet", "IFSM", "ITLSReloader", "ITLSWatch", "ITLSProbe",
]
