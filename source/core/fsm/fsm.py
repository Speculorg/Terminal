from __future__ import annotations
import time
from typing import Dict, List
from entities import StateEnum
from base.base_fsm import BaseFSM
from interfaces.i_policy import PolicyStatus

class FSM(BaseFSM):
    def __init__(self, cfg, logger, markers, fs, net, kv=None, metrics=None, registrar=None):
        self.cfg, self.logger, self.markers, self.fs, self.net = cfg, logger, markers, fs, net
        self.kv, self.metrics, self.registrar = kv, metrics, registrar
        self.policies: Dict[StateEnum, List] = {}
        self.profile = None
        class Ctx:
            current = StateEnum.STARTING
            previous = None
            since_ts = int(time.time())
        self.ctx = Ctx()
        self.svc = getattr(cfg.context, "name", None)

    def next_state(self, s: StateEnum) -> StateEnum:
        order = [
            StateEnum.STARTING,
            StateEnum.BOOTSTRAPPING,
            StateEnum.INITIALIZING,
            StateEnum.SECURING,
            StateEnum.TLS_TRANSITION,
            StateEnum.REGISTERING,
            StateEnum.RUNNING,
        ]
        try:
            i = order.index(s)
            return order[i+1] if i+1 < len(order) else StateEnum.RUNNING
        except Exception:
            return StateEnum.RUNNING

    def start(self) -> None:
        self.on_enter(StateEnum.STARTING)

    def run(self) -> None:
        safety = 0
        while self.ctx.current not in (StateEnum.RUNNING, StateEnum.ERROR) and safety < 100:
            state = self.ctx.current
            plist = list(self.policies.get(state, []) or [])
            all_ok = True
            for pol in plist:
                res = pol.run()
                if res.status == PolicyStatus.FAIL:
                    self.on_enter(StateEnum.ERROR)
                    all_ok = False
                    break
                if res.status == PolicyStatus.RETRY:
                    all_ok = False
                    time.sleep(0.1)
                    break
            if all_ok:
                self.on_enter(self.next_state(state))
            safety += 1

    def on_enter(self, state: StateEnum) -> None:
        try:
            self.logger.info("fsm.enter", svc=self.svc, state=state.name)
        except Exception:
            pass
        self.ctx.previous = self.ctx.current
        self.ctx.current = state
        self.ctx.since_ts = int(time.time())
        try:
            self.logger.info("fsm.entered", svc=self.svc, state=state.name)
        except Exception:
            pass
