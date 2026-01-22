from __future__ import annotations

from typing import Any, Mapping, Optional

from _interfaces import IConfigs


class BaseConfigs(IConfigs):
    """
    Базовый фасад конфигурации.

    Принцип: этот класс должен быть *рабочим по умолчанию* и не требовать переопределений.

    Ожидаемые (duck-typing) атрибуты наследника:
    - _model: pydantic model (v2: model_dump()) или объект с полями `context.name`
    - _raw_env: dict[str, str] с объединёнными env значениями
    """

    # --- IConfigs ---

    def as_dict(self) -> Mapping[str, Any]:
        model = getattr(self, "_model", None)
        if model is None:
            return {}

        # pydantic v2
        try:
            return model.model_dump()  # type: ignore[attr-defined]
        except Exception:
            pass

        # pydantic v1
        try:
            return model.dict()  # type: ignore[attr-defined]
        except Exception:
            pass

        # fallback
        try:
            return dict(model)  # type: ignore[arg-type]
        except Exception:
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        raw = getattr(self, "_raw_env", None)
        if isinstance(raw, dict):
            return raw.get(key, default)
        return default

    @property
    def service_name(self) -> str:
        # 1) model.context.name
        model = getattr(self, "_model", None)
        try:
            ctx = getattr(model, "context", None)
            name = getattr(ctx, "name", None)
            if name:
                return str(name)
        except Exception:
            pass

        # 2) raw env SERVICE_NAME
        try:
            v = self.get("SERVICE_NAME", None)
            if v:
                return str(v)
        except Exception:
            pass

        return "unknown"
