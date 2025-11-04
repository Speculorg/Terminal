from __future__ import annotations
import time
from typing import Optional, Sequence, Tuple, List, Dict, Any
from entities import StateEnum

class BaseFSM:
    """Базовый каркас FSM.
    Делает проверку stage-gates перед входом в состояние и публикует логи.
    Фасад обязан определить поля: cfg, logger, markers, svc, stage_gates, _publish_state().
    """

    svc: Optional[str] = None
    stage_gates: Dict[StateEnum, Sequence[str]] = {}

    def run(self) -> None:
        try:
            if hasattr(self, "start"):
                self.start()  # type: ignore[attr-defined]
            if hasattr(self, "tick"):
                self.tick()   # type: ignore[attr-defined]
        except Exception as e:
            try:
                self.on_enter(StateEnum.ERROR)
            except Exception:
                pass
            try:
                self.logger.error('fsm.run.error', svc=self.svc or self.cfg.context.name, event='fsm.run', details={'exc': type(e).__name__})  # type: ignore[attr-defined]
            except Exception:
                pass

    def _flat_gate_names(self, items: Sequence) -> List[str]:
        names: List[str] = []
        for it in items or ():
            try:
                if isinstance(it, tuple) and len(it) == 2:
                    names.append(str(it[1]))
                else:
                    names.append(str(it))
            except Exception:
                continue
        return names

    def precheck_stage_gates(self, state: StateEnum) -> Tuple[bool, List[str]]:
        req_seq = (self.stage_gates or {}).get(state, ()) or ()
        req = self._flat_gate_names(req_seq)
        missing = [m for m in req if not self.markers.exists(m)]  # type: ignore[attr-defined]
        return (len(missing) == 0, missing)

    def on_enter(self, state: StateEnum) -> None:
        try:
            self.logger.info("fsm.enter", svc=self.svc or self.cfg.context.name, state=state.name)  # type: ignore[attr-defined]
        except Exception:
            pass

        ok, missing = self.precheck_stage_gates(state)
        if not ok:
            try:
                self.logger.info("fsm.stage_gate.missing", svc=self.svc or self.cfg.context.name, state=state.name, details={"missing": sorted(missing)})  # type: ignore[attr-defined]
            finally:
                return

        self._on_enter_impl(state)

        try:
            self.publish_state()
        except Exception:
            pass

    def _on_enter_impl(self, state: StateEnum) -> None:
        raise NotImplementedError

    def publish_state(self) -> None:
        if hasattr(self, "_publish_state"):
            self._publish_state()  # type: ignore[attr-defined]
