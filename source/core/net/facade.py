from __future__ import annotations
from base.base_net import BaseNet
from interfaces import IConfigs

class Net(BaseNet):
    def __init__(self, cfg: IConfigs) -> None:
        super().__init__(cfg)
