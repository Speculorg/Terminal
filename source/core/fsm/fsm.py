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
    def __init__(self, svc: str, cfg, logger, markers, kv, metrics) -> None:
        self.svc = svc
        self.cfg = cfg
        self.logger = logger
        self.markers = markers
        self.kv = kv
        self.metrics = metrics
        now = int(time.time())
        self.ctx = StateCtx(current=StateEnum.STARTING, previous=None, since_ts=now)
        self.run_mode: RunModeEnum = RunModeEnum.NORMAL
        self._last_publish_ts: int = 0  # rate-limit публикаций

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
        self._enter(StateEnum.STOPPED)

    # --- internal ---
    def _enter(self, new_state: StateEnum) -> None:
        now = int(time.time())
        prev = self.ctx.current
        self.ctx.previous = prev
        self.ctx.current = new_state
        self.ctx.since_ts = now
        # лог
        self.logger.info("state.enter", svc=self.svc, state=new_state.name)
        # метрики
        try:
            self.metrics.counter("terminal_fsm_counter").inc({"svc": self.svc, "state": new_state.name, "op": "enter", "result": "ok"})
        except Exception:
            pass
        # health snapshot (in-memory)
        self._publish_state_snapshot(new_state, now)
        # запись в KV допускается только в RUNNING
        if new_state is StateEnum.RUNNING:
            self._publish_kv_state(now)

    def _health_status_for(self, st: StateEnum) -> HealthStatusEnum:
        if st is StateEnum.RUNNING:
            return HealthStatusEnum.PASSING
        if st in (StateEnum.PAUSED,):
            return HealthStatusEnum.MAINTENANCE
        if st in (StateEnum.ERROR, StateEnum.STOPPING, StateEnum.STOPPED):
            return HealthStatusEnum.CRITICAL
        return HealthStatusEnum.WARNING

    def _publish_state_snapshot(self, st: StateEnum, now: int) -> None:
        try:
            self.metrics.gauge("terminal_fsm_gauge").set({"svc": self.svc, "state": st.name, "op": "snapshot", "result": "ok"}, 1)
        except Exception:
            pass

    def _publish_kv_state(self, now: int) -> None:
        # rate-limit публикаций
        min_interval = int(getattr(self.cfg.fsm, "state_publish_min_interval_ms", 5000)) // 1000
        if now - self._last_publish_ts < max(1, min_interval):
            return
        self._last_publish_ts = now
        payload = {
            "svc": self.svc,
            "version": self.cfg.global.version,
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
        try:
            self.metrics.counter("terminal_kv_counter").inc({"svc": self.svc, "op": "cas", "result": "done" if ok else "collision"})
        except Exception:
            pass
