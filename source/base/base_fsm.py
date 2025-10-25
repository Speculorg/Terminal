from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from interfaces import IFSM, IDeps, IRunProfile
from entities import StateEnum

@dataclass
class _DefaultRunProfile(IRunProfile):
    required_markers: set[str]

class BaseFSM(IFSM):
    """Минимальная FSM-обвязка. Детальная логика в core/policies и core/fsm."""
    def __init__(self, deps: IDeps, profile: IRunProfile | None = None) -> None:
        self._d = deps
        self._p = profile or _DefaultRunProfile(required_markers=set())
        self._state: StateEnum = StateEnum.STARTING

    # API
    def state(self) -> StateEnum:
        return self._state

    def start(self) -> None:
        self._enter(StateEnum.STARTING)
        # Простейшие требования: наличие нужных маркеров
        svc = self._d.configs.context.name
        ok = True
        for m in getattr(self._p, "required_markers", set()):
            if not self._d.markers.exists(svc, m):
                ok = False
                break
        if ok:
            self._enter(StateEnum.RUNNING)
        else:
            self._enter(StateEnum.DEGRADED)

    def tick(self) -> None:
        # Публикация метрики состояния
        self._publish_state_metric()

    def stop(self) -> None:
        self._enter(StateEnum.STOPPING)
        self._enter(StateEnum.STOPPED)

    # helpers
    def _publish_state_metric(self) -> None:
        try:
            self._d.metrics.gauge("service_state").set({"svc": self._d.configs.context.name}, float(self._state_index()))
        except Exception:
            pass

    def _enter(self, st: StateEnum) -> None:
        self._state = st
        try:
            self._d.logger.info("fsm.enter", svc=self._d.configs.context.name, state=st.name, event="fsm.enter")
        except Exception:
            pass

    def _state_index(self) -> int:
        order = [
            StateEnum.STARTING, StateEnum.BOOTSTRAPPING, StateEnum.INITIALIZING,
            StateEnum.SECURING, StateEnum.TLS_TRANSITIONRANSITION, StateEnum.REGISTERING,
            StateEnum.RUNNING, StateEnum.PAUSED, StateEnum.DEGRADED, StateEnum.ERROR,
            StateEnum.STOPPING, StateEnum.STOPPED,
        ]
        return order.index(self._state)
