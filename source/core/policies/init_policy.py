from __future__ import annotations
import importlib.util, sys
from typing import Optional
from entities.state_enum import StateEnum

class InitPolicy:
    """Абстрактная политика первичных действий.
    Загружает services/<svc>/config/init.py и вызывает обработчик состояния:
      - on_bootstrapping(cfg, logger, fs, markers, net) -> Optional[StateEnum]
      - on_initializing(cfg, logger, fs, markers, net) -> Optional[StateEnum]
      - on_securing(cfg, logger, fs, markers, net) -> Optional[StateEnum]
    Нет знаний о конкретных сервисах.
    """
    def __init__(self, cfg, logger, fs, markers, net):
        self.cfg = cfg
        self.logger = logger
        self.fs = fs
        self.markers = markers
        self.net = net

    def _load_module(self):
        svc = self.cfg.context.name
        mod_path = f"{self.cfg.paths.root}/services/{svc}/config/init.py"
        spec = importlib.util.spec_from_file_location(f"{svc}_init", mod_path)
        if not spec or not spec.loader:
            raise ImportError(f"init module not found: {mod_path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"{svc}_init"] = mod
        spec.loader.exec_module(mod)
        return mod

    def apply(self, state: StateEnum) -> Optional[StateEnum]:
        try:
            mod = self._load_module()
        except Exception as e:
            try:
                self.logger.warn("init.module.load.error", svc=self.cfg.context.name, details={"state": state.name, "error": str(e)})
            except Exception:
                pass
            return None
        name_map = {
            StateEnum.BOOTSTRAPPING: "on_bootstrapping",
            StateEnum.INITIALIZING: "on_initializing",
            StateEnum.SECURING: "on_securing",
        }
        func_name = name_map.get(state)
        if not func_name or not hasattr(mod, func_name):
            return None
        try:
            fn = getattr(mod, func_name)
            nxt = fn(self.cfg, self.logger, self.fs, self.markers, self.net)
            return nxt if isinstance(nxt, StateEnum) else None
        except Exception as e:
            try:
                self.logger.warn("init.apply.error", svc=self.cfg.context.name, details={"state": state.name, "error": str(e)})
            except Exception:
                pass
            return None
