from __future__ import annotations
from base.base_configs import BaseConfigs
from .model import Model

class Configs(BaseConfigs):
    """Единый фасад настроек. Наследуется от BaseConfigs.
    Принимает готовую модель и выполняет базовую валидацию.
    """
    def __init__(self, model: Model) -> None:
        super().__init__(model)
