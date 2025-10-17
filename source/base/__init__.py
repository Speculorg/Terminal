"""
Base package: composition root and service carcasses.
TERM-1: Stage 2 (Base)
"""
from .base_service import BaseService
from .base_deps import BaseDeps
from .base_fsm import BaseFSM
from .base_health import BaseHealth

__all__ = ["BaseService", "BaseDeps", "BaseFSM", "BaseHealth"]
