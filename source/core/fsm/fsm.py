from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import time

from entities.state_enum import StateEnum
from entities.run_mode_enum import RunModeEnum
from entities.health_status_enum import HealthStatusEnum
from entities.error_code_enum import ErrorCodeEnum

@dataclass
class StateCtx:
    current: StateEnum
    previous: Optional[StateEnum]
    since_ts: int  # unix seconds
    heartbeat_ts: Optional[int] = None
    last_error: Optional[ErrorCodeEnum] = None

class FSM:
    def __init__(self, svc: str, cfg, logger, markers, kv, metrics, registrar=None):
        self.registrar = registrar
        self.svc = svc
        self.cfg = cfg
        self.logger = logger
        self.markers = markers
        self.kv = kv
        self.metrics = metrics
        self._run_mode: Optional[RunModeEnum] = None
        now = int(time.time())
        self.ctx = StateCtx(current=StateEnum.STARTING, previous=None, since_ts=now)

    # external API
    def set_run_mode(self, mode: RunModeEnum) -> None:
        self._run_mode = mode

    # Lifecycle
    def start(self) -> None:
        # STARTING
        self._on_enter(StateEnum.STARTING)
        # prerequisites
        if not self._policies().fsm.check_prereq():
            self._to_error(ErrorCodeEnum.ERR_PRECONDITION); return
        self._transition(StateEnum.BOOTSTRAPPING)

        # BOOTSTRAPPING
        if self._run_mode == RunModeEnum.FIRST:
            self._transition(self._policies().fsm.first_run())
        elif self._run_mode == RunModeEnum.RECOVERY:
            self._transition(self._policies().fsm.recovery_run())
        else:
            self._transition(self._policies().fsm.normal_run())

        # INITIALIZING (optional)
        if self.ctx.current is StateEnum.INITIALIZING:
            self._transition(self._policies().fsm.bootstrap_gate())

        # SECURING
        if not self._policies().tls.check_ready():
            self._transition(StateEnum.DEGRADED)
            return
        self._transition(StateEnum.TLS_TRANSITION)

        # TLS_TRANSITION
        if not self._policies().tls.https_probes_ok():
            self._transition(StateEnum.DEGRADED)
            return
        self._transition(self._policies().fsm.switch_https())

        # REGISTERING
        if not self._policies().registrar.on_register():
            self._transition(StateEnum.DEGRADED)
            return
        self._transition(self._policies().fsm.on_register_ok())

        # RUNNING single tick (TERM-1 minimal)
        self._tick()
        # остаёмся в RUNNING, дальнейшая оркестрация будет расширена на следующих этапах

    # helpers
    def _policies(self):
        # лениво импортируем фабрику, чтобы избежать циклов импортов
        from core.policies import PoliciesFactory
        return PoliciesFactory(self.cfg, self.logger, self.registrar, self.kv, self.metrics, self.markers)

    def _on_enter(self, st: StateEnum) -> None:
        # Update ctx
        now = int(time.time())
        prev = self.ctx.current if hasattr(self, "ctx") and self.ctx else None
        self.ctx = StateCtx(current=st, previous=prev, since_ts=now, heartbeat_ts=self.ctx.heartbeat_ts if prev else None)
        # Logging
        self.logger.info({
            "svc": self.svc,
            "state": st.name,
            "message": f"enter {st.name}",
            "deadline_ms": self._state_deadline_ms(st),
        })
        # Metrics
        self.metrics.gauge("terminal_fsm_gauge").set({"svc": self.svc, "state": st.name, "op": "snapshot", "result": "ok"}, 1)
        # Publish
        self._publish_state()

    def _transition(self, to_state: StateEnum) -> None:
        if self.ctx.current is to_state:
            return
        old = self.ctx.current
        self._on_exit(old)
        self._on_enter(to_state)
        self._state_changed(old, to_state, reason="policy")

    def _on_exit(self, st: StateEnum) -> None:
        self.logger.debug({
            "svc": self.svc,
            "state": st.name,
            "message": f"exit {st.name}",
        })

    def _state_changed(self, old: StateEnum, new: StateEnum, reason: str) -> None:
        self.logger.info({
            "svc": self.svc, "state": new.name, "event": "state_changed",
            "details": {"from": old.name, "to": new.name, "reason": reason}
        })

    def _tick(self) -> None:
        st = self._policies().fsm.on_tick()
        # Heartbeat в RUNNING
        if self.ctx.current.name == 'RUNNING' and self.registrar is not None:
            if self._policies().registrar.try_heartbeat(self.svc):
                self.ctx.heartbeat_ts = int(time.time())
                self._publish_state()
        self._transition(st)

    def _publish_state(self) -> None:
        # only RUNNING goes to KV according to plan
        if self.ctx.current is not StateEnum.RUNNING:
            return
        now = int(time.time())
        payload = {
            "svc": self.svc,
            "version": self.cfg.global_.version,
            "state": self.ctx.current.name,
            "status": self._health_status_for(self.ctx.current).name,
            "ts": now,
            "since_ts": self.ctx.since_ts,
            "heartbeat_ts": self.ctx.heartbeat_ts,
            "owner": self.svc,
            "last_error": self.ctx.last_error.name if self.ctx.last_error else None,
        }
        idx, _ = self.kv.states.read()
        ok = self.kv.states.cas(payload, idx)
        self.metrics.counter("terminal_kv_counter").inc({"svc": self.svc, "op": "cas", "result": "done" if ok else "collision"})

    def _health_status_for(self, state: StateEnum) -> HealthStatusEnum:
        # Map by plan
        if state is StateEnum.RUNNING:
            return HealthStatusEnum.PASSING
        if state in (StateEnum.PAUSED,):
            return HealthStatusEnum.MAINTENANCE
        if state in (StateEnum.ERROR, StateEnum.STOPPING, StateEnum.STOPPED):
            return HealthStatusEnum.CRITICAL
        # default early states and degraded
        return HealthStatusEnum.WARNING

    def _state_deadline_ms(self, state: StateEnum) -> int:
        fsm = self.cfg.fsm
        mapping = {
            StateEnum.STARTING: fsm.state_starting_timeout_ms,
            StateEnum.BOOTSTRAPPING: fsm.state_bootstrapping_timeout_ms,
            StateEnum.INITIALIZING: fsm.state_initializing_timeout_ms,
            StateEnum.SECURING: fsm.state_securing_timeout_ms,
            StateEnum.TLS_TRANSITION: fsm.state_tls_transition_timeout_ms,
            StateEnum.REGISTERING: fsm.state_registering_timeout_ms,
            StateEnum.RUNNING: fsm.state_running_tick_timeout_ms,
        }
        return mapping.get(state, fsm.state_starting_timeout_ms)

    def _to_error(self, code: ErrorCodeEnum) -> None:
        self.ctx.last_error = code
        self._transition(StateEnum.ERROR)
