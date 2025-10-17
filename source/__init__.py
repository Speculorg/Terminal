# TERM-1 Stage 0: package stub (no-op)
# source/__init__.py
"""
Инициализация корневого пакета Speculorg.Terminal.
Разрешает короткие импорты вида `from interfaces import ...`
"""

# Импортируем ключевые подпакеты для автоподключения
from importlib import import_module

__all__ = [
    "interfaces",
    "types",
    "entities",
    "services",
    "core",
    "base",
]

# Динамическая подгрузка подпакетов
for _pkg in __all__:
    try:
        globals()[_pkg] = import_module(f"source.{_pkg}")
    except ModuleNotFoundError:
        pass
