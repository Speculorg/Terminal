from __future__ import annotations
from dataclasses import dataclass
from base.base_fsm import BaseFSM
from typing import Optional, Set, Dict, List, Tuple
import time

from entities import StateEnum, RunModeEnum, HealthStatusEnum, ErrorCodeEnum

from core.policies import TLSPolicy, InitPolicy

@dataclass
class StateCtx:
    current: StateEnum
    previous: Optional[StateEnum]
    since_ts: int  # unix seconds
    heartbeat_ts: Optional[int] = None

class FSM(BaseFSM):
    """Минимальная рабочая FSM под публикации и регистрацию.
    Политики и детекции run_mode будут позже.
    """
    def __init__(self, cfg, logger, markers, fs, net, kv=None, metrics=None, registrar=None):
        self.cfg = cfg
        self.logger = logger
        self.markers = markers
        self.fs = fs
        self.net = net
        self.kv = kv
        self.metrics = metrics
        self.registrar = registrar
        
        self.ctx = StateCtx(current=StateEnum.STARTING, previous=None, since_ts=int(time.time()))
        self.required_markers: Set[str] = set()
        self.stage_gates: Dict[StateEnum, List[Tuple[str,str]]] = {}
        self.svc: Optional[str] = None
        self.run_mode: Optional[RunModeEnum] = None
        self._last_publish_ts: int = 0
        self._tls_restart_cb=None
        self._tls_resolve_port_cb=None
        self._tls_run_profile=None
        self._tls_net=None
        self._tls_current_mode=None
    
    def configure_tls(self, run_profile, net, restart_cb, resolve_port_cb, current_mode: str = "http") -> None:
        self._tls_run_profile = run_profile
        self._tls_net = net
        self._tls_restart_cb = restart_cb
        self._tls_resolve_port_cb = resolve_port_cb
        self._tls_current_mode = current_mode

    def on_enter(self, state: StateEnum) -> None:
        # enforce stage gates before state switch
        gates = list(self.stage_gates.get(state, [])) if isinstance(self.stage_gates, dict) else []
        if gates:
            missing_all = []
            for svc, name in gates:
                ok, missing = self.markers.require({f"{svc}_{name}.done"})
                if not ok:
                    missing_all.extend([f"{svc}/{m}" for m in sorted(missing)])
            if missing_all:
                self.logger.error("fsm.gate_blocked", svc=self.svc or self.cfg.context.name, state=state.name, details={"missing": missing_all})
                raise RuntimeError(f"stage gates not satisfied: {missing_all}")
        now = int(time.time())
        self.ctx.previous = self.ctx.current
        self.ctx.current = state
        
        # Первичные действия на ранних стадиях: делегирование init-модулю сервиса
        if state in (StateEnum.BOOTSTRAPPING, StateEnum.INITIALIZING, StateEnum.SECURING):
            try:
                pol = InitPolicy(self.cfg, self.logger, self.fs, self.markers, self.net)
                nxt = pol.apply(state)
                if nxt and isinstance(nxt, StateEnum) and nxt != state:
                    self.on_enter(nxt)
            except Exception as e:
                try:
                    self.logger.warn("init.error", svc=self.svc or self.cfg.context.name, details={"error": str(e)})
                except Exception:
                    pass

        # Единая проверка stage-gates
        ok, missing = self.precheck_stage_gates(state)
        if not ok:
            try:
                self.logger.info("fsm.stage_gate.missing", svc=self.svc or self.cfg.context.name, details={"state": state.name, "missing": sorted(missing)})
            finally:
                return

        # TLS_TRANSITION: делегируем правила в TLSPolicy
        if state == StateEnum.TLS_TRANSITION:
            try:
                if self._tls_run_profile and self._tls_restart_cb and self._tls_resolve_port_cb and self._tls_net:
                    TLSPolicy().transition_if_ready(self.cfg, self.logger, self.markers, self._tls_net, self._tls_run_profile, self._tls_current_mode or "http", self._tls_restart_cb, self._tls_resolve_port_cb)
            except Exception as e:
                pass
            # Решение результата TLS-перехода: проверим порт https и выполним переход
            try:
                https_port = int(self._tls_resolve_port_cb("https")) if self._tls_resolve_port_cb else None
            except Exception:
                https_port = None
            deadline_ms = int(getattr(self.cfg.fsm, "state_tls_transition_timeout_ms", 5000))
            ok_https = False
            if https_port and self._tls_net:
                try:
                    ok_https = bool(self._tls_net.wait_port("localhost", https_port, deadline_ms=deadline_ms))
                except Exception:
                    ok_https = False
            if ok_https:
                try:
                    self.logger.info("fsm.tls_transition.ok", svc=self.svc or self.cfg.context.name, details={"port": int(https_port)})
                except Exception:
                    pass
                # успех: идём в REGISTERING
                try:
                    self.on_enter(StateEnum.REGISTERING)
                except Exception:
                    pass
            else:
                try:
                    self.logger.info("fsm.tls_transition.timeout", svc=self.svc or self.cfg.context.name, details={"timeout_ms": int(deadline_ms)})
                except Exception:
                    pass
                # неуспех: деградация
                try:
                    self.on_enter(StateEnum.DEGRADED)
                except Exception:
                    pass

                try:
                    self.logger.warn("tls.transition.error", svc=self.svc or self.cfg.context.name, details={"error": str(e)})
                except Exception:
                    pass

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
                if self.registrar and self.registrar.register(self.svc or self.cfg.context.name):
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
            if self.registrar and self.registrar.heartbeat(self.svc or self.cfg.context.name):
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
