from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from entities.state_enum import StateEnum
from entities.run_mode_enum import RunModeEnum
from entities.health_status_enum import HealthStatusEnum

@dataclass
class StateCtx:
    current: StateEnum
    previous: Optional[StateEnum]
    since_ts: int

class FSM:
    def __init__(self, svc: str, cfg, logger, markers, kv, metrics) -> None:
        self.svc = svc
        self.cfg = cfg
        self.logger = logger
        self.markers = markers
        self.kv = kv
        self.metrics = metrics
        self.ctx = StateCtx(current=StateEnum.STARTING, previous=None, since_ts=0)
        self.run_mode: RunModeEnum = RunModeEnum.NORMAL

    def set_run_mode(self, mode: RunModeEnum) -> None:
        self.run_mode = mode

    def start(self) -> None:
        self._enter(StateEnum.STARTING)
        self._enter(StateEnum.BOOTSTRAPPING)
        if self.run_mode in (RunModeEnum.FIRST, RunModeEnum.RECOVERY):
            self._enter(StateEnum.INITIALIZING)
        self._enter(StateEnum.SECURING)
        self._enter(StateEnum.TLS_TRANSITION)
        self._enter(StateEnum.REGISTERING)
        self._enter(StateEnum.RUNNING)

    def stop(self) -> None:
        self._enter(StateEnum.STOPPING)

    def _enter(self, new_state: StateEnum) -> None:
        self.ctx.previous = self.ctx.current
        self.ctx.current = new_state
        # log
        self.logger.info("state.enter", svc=self.svc, state=new_state.name)
        # metrics
        try:
            self.metrics.counter("terminal_fsm_counter").inc({"svc": self.svc, "state": new_state.name, "op": "enter", "result": "ok"})
        except Exception:
            pass
        # publish only in RUNNING
        if new_state is StateEnum.RUNNING:
            payload = {
                "svc": self.svc,
                "version": self.cfg.global_.version,
                "state": new_state.name,
                "status": HealthStatusEnum.PASSING.name,
            }
            idx, _ = self.kv.states.read()
            self.kv.states.cas(payload, idx)
