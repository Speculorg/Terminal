from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Set, Dict, List, Tuple
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

class FSM:
    """Минимальная рабочая FSM под публикации и регистрацию.
    Политики и детекции run_mode будут позже.
    """
    def __init__(self, cfg, logger, markers, kv, metrics, registrar=None):
        self.cfg = cfg
        self.logger = logger
        self.markers = markers
        self.kv = kv
        self.metrics = metrics
        self.registrar = registrar
        self.ctx = StateCtx(current=StateEnum.STARTING, previous=None, since_ts=int(time.time()))
        self.required_markers: Set[str] = set()
        self.stage_gates: Dict[StateEnum, List[Tuple[str,str]]] = {}
        self.svc: Optional[str] = None
        self.run_mode: Optional[RunModeEnum] = None
        self._last_publish_ts: int = 0

    def on_enter(self, state: StateEnum) -> None:
        # enforce stage gates before state switch
        gates = list(self.stage_gates.get(state, [])) if isinstance(self.stage_gates, dict) else []
        if gates:
            missing_all = []
            for svc, name in gates:
                ok, missing = self.markers.require({name}, svc=svc)
                if not ok:
                    missing_all.extend([f"{svc}/{m}" for m in sorted(missing)])
            if missing_all:
                self.logger.error("fsm.gate_blocked", svc=self.svc or self.cfg.context.name, state=state.name, details={"missing": missing_all})
                raise RuntimeError(f"stage gates not satisfied: {missing_all}")
        now = int(time.time())
        self.ctx.previous = self.ctx.current
        self.ctx.current = state
        self.ctx.since_ts = now
        self.logger.info("fsm.enter", svc=self.svc or self.cfg.context.name, state=state.name, event="fsm.enter")

    def _publish_state_once(self) -> bool:
        try:
            idx, _old = self.kv.states.read()
        except Exception as e:
            self.logger.warn("kv.states.read.error", svc=self.svc or self.cfg.context.name, event="kv.read", details={"exc": type(e).__name__})
            return False

        payload = {
            "svc": self.svc or self.cfg.context.name,
            "state": self.ctx.current.name,
            "since": int(self.ctx.since_ts),
            "version": self.cfg.global_.version,
            "tags": list(self.cfg.context.tags),
            "ts": int(time.time()),
        }
        try:
            ok = self.kv.states.cas(payload, modify_index=int(idx or 0))
            if ok:
                self.logger.info("kv.states.cas.ok", svc=self.svc or self.cfg.context.name, event="kv.cas")
            else:
                self.logger.warn("kv.states.cas.conflict", svc=self.svc or self.cfg.context.name, event="kv.cas")
            return ok
        except Exception as e:
            self.logger.warn("kv.states.cas.error", svc=self.svc or self.cfg.context.name, event="kv.cas", details={"exc": type(e).__name__})
            return False

    def _publish_state(self) -> None:
        # publish to KV only in RUNNING
        if self.ctx.current != StateEnum.RUNNING:
            return
        now_ms = int(time.time() * 1000)
        min_interval = int(self.cfg.fsm.state_publish_min_interval_ms)
        if now_ms - self._last_publish_ts < min_interval:
            return
        maxr = max(1, int(self.cfg.kv.cas_max_retries))
        factor = max(1, int(self.cfg.kv.cas_backoff_factor))
        delay = 0.2
        for attempt in range(1, maxr + 1):
            if self._publish_state_once():
                self._last_publish_ts = now_ms
                return
            time.sleep(delay)
            delay *= factor

    def _register_with_retry(self) -> bool:
        if not self.registrar:
            return True
        attempts = 0
        maxr = max(1, int(self.cfg.registrar.max_rereg_attempts_per_window))
        while attempts < maxr:
            try:
                if self.registrar.register(self.svc or self.cfg.context.name):
                    return True
            except Exception as e:
                self.logger.warn("registrar.register.error", svc=self.svc or self.cfg.context.name, event="registrar.register", details={"exc": type(e).__name__})
            attempts += 1
            time.sleep(max(1, int(self.cfg.registrar.reregistration_cooldown_sec)))
        return False

    def _heartbeat(self) -> None:
        if not self.registrar:
            return
        try:
            if self.registrar.heartbeat(self.svc or self.cfg.context.name):
                self.ctx.heartbeat_ts = int(time.time())
        except Exception as e:
            self.logger.warn("registrar.heartbeat.error", svc=self.svc or self.cfg.context.name, event="registrar.heartbeat", details={"exc": type(e).__name__})

    def start(self) -> None:
        self.svc = self.cfg.context.name
        self.on_enter(StateEnum.STARTING)
        self.on_enter(StateEnum.REGISTERING)
        if self._register_with_retry():
            self.on_enter(StateEnum.RUNNING)
        else:
            self.on_enter(StateEnum.DEGRADED)

    def tick(self) -> None:
        if self.ctx.current == StateEnum.RUNNING:
            self._heartbeat()
        self._publish_state()

    def stop(self) -> None:
        self.on_enter(StateEnum.STOPPING)
        try:
            if self.registrar:
                self.registrar.deregister(self.svc or self.cfg.context.name)
        except Exception:
            pass
        self.on_enter(StateEnum.STOPPED)

    def run(self) -> None:
        """TERM-1: неблокирующий запуск цикла FSM для сервиса.
        Выполняет стартовые переходы и один тик публикации/heartbeat.
        Поведение блокирующего цикла не требуется на уровне каркаса.
        """
        try:
            self.start()
            self.tick()
        except Exception as e:
            # Перевод в ERROR при фатальной ошибке запуска
            try:
                self.on_enter(StateEnum.ERROR)
            except Exception:
                pass
            try:
                self.logger.error('fsm.run.error', svc=self.svc or self.cfg.context.name, event='fsm.run', details={'exc': type(e).__name__})
            except Exception:
                pass
