from __future__ import annotations
from typing import Protocol, runtime_checkable, Mapping, Any


@runtime_checkable
class IConfigs(Protocol):
    """
    Единая точка доступа к конфигурации сервиса.

    В TERM-1 источники: env + configs.env + файлы в secrets_dir.
    Конкретная структура будет оформлена в core/configs/model.py.
    """

    def as_dict(self) -> Mapping[str, Any]:
        """Дать конфигурацию как JSON-совместимый словарь (для логов/диагностики)."""
        ...

    def get(self, key: str, default: Any = None) -> Any:
        """Упрощённый доступ к значениям по ключу (для ранних стадий/миграций)."""
        ...

    @property
    def service_name(self) -> str:
        """Имя сервиса (для логов/health/регистрации)."""
        ...
