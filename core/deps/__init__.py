# Пакет сборки зависимостей
"""
speculorg.terminal.core.deps
============================

Контейнер зависимостей (Deps) и фабрика его сборки (DepsFactory).
"""


from .deps import Deps
from .factory import DepsFactory

__all__ = ["Deps", "DepsFactory"]
