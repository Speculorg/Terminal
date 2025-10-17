from __future__ import annotations
from interfaces import IFSM, IDeps, IRunProfile
from entities import StateEnum

class BaseFSM(IFSM):
    """
    Минимальная FSM-обвязка. Детальная логика в core/policies.
    """
    def __init__(self, deps: IDeps, profile: IRunProfile) -> None:
        self._d = deps
        self._p = profile
        self._state: StateEnum = StateEnum.STARTING

    def run(self) -> None:
        self.publish_state()
        self.on_enter(StateEnum.BOOTSTRAPPING)
        self.on_enter(StateEnum.INITIALIZING)
        self.on_enter(StateEnum.SECURING)
        self.on_enter(StateEnum.TLS_TRANSITION)
        self.on_enter(StateEnum.REGISTERING)
        self.on_enter(StateEnum.RUNNING)
        self.publish_state()

    def on_enter(self, state: StateEnum) -> None:
        self._state = state
        self._d.logger.info("enter state", svc=self._svc(), state=state.value)
        self.publish_state()

    def publish_state(self) -> None:
        self._d.metrics.gauge("service_state").set({"svc": self._svc()}, float(self._state_index()))
        self._d.logger.debug("publish state", svc=self._svc(), state=self._state.value)

    def _svc(self) -> str:
        return self._d.configs.context.name  # type: ignore[attr-defined]

    def _state_index(self) -> int:
        order = [
            StateEnum.STARTING, StateEnum.BOOTSTRAPPING, StateEnum.INITIALIZING,
            StateEnum.SECURING, StateEnum.TLS_TRANSITION, StateEnum.REGISTERING,
            StateEnum.RUNNING, StateEnum.PAUSED, StateEnum.DEGRADED, StateEnum.ERROR,
            StateEnum.STOPPING, StateEnum.STOPPED,
        ]
        return order.index(self._state)
