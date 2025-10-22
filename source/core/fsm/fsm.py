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
    last_error: Optional[ErrorCodeEnum] = None

class FSM:
    """FSM без сетевых проб на ранних стадиях.
    Гейты по файловым маркерам (из профиля сервиса).
    В REGISTERING выполняет регистрацию с ретраями.
    В RUNNING держит heartbeat и публикует состояние в KV (CAS с ретраями).
    """
    def __init__(self, cfg, logger, markers, kv, metrics, registrar=None):
        self.cfg = cfg
        self.logger = logger
        self.markers = markers
        self.kv = kv
        self.metrics = metrics
        self.registrar = registrar
        self.ctx = StateCtx(current=StateEnum.STARTING, previous=None, since_ts=int(time.time()))
        # Подставляются BaseService перед run()
        self.required_markers: Set[str] = set()
        self.stage_gates: Dict[StateEnum, List[Tuple[str,str]]] = {}
        self.svc: Optional[str] = None
        self.run_mode: Optional[RunModeEnum] = None
        # publish throttling
        self._last_publish_ts: int = 0

    def on_enter(self, state: StateEnum) -> None:
        now = int(time.time())
        self.ctx.previous = self.ctx.current
        self.ctx.current = state
        self.ctx.since_ts = now
        self.logger.info("fsm.enter", svc=self.svc, state=state.name)

    # ---------- KV state publish with CAS retries ----------
    def _publish_state_once(self) -> bool:
        try:
            idx, _old = self.kv.states.read()
        except Exception as e:
            self.logger.warn("kv.states.read.error", svc=self.svc, err=type(e).__name__)
            return False

        payload = {
            "svc": self.svc,
            "state": self.ctx.current.name,
            "since": int(self.ctx.since_ts),
            "version": self.cfg.global_.version,
            "tags": list(self.cfg.context.tags),
            "ts": int(time.time()),
        }
        try:
            ok = self.kv.states.cas(payload, modify_index=int(idx or 0))
            if ok:
                self.logger.info("kv.states.cas.ok", svc=self.svc)
            else:
                self.logger.warn("kv.states.cas.conflict", svc=self.svc)
            return ok
        except Exception as e:
            self.logger.warn("kv.states.cas.error", svc=self.svc, err=type(e).__name__)
            return False

    def _publish_state(self) -> None:
        if self.ctx.current is not StateEnum.RUNNING:
            return
        now_ms = int(time.time()*1000)
        min_gap = int(self.cfg.fsm.state_publish_min_interval_ms)
        if self._last_publish_ts and now_ms - self._last_publish_ts < min_gap:
            return

        # CAS retries with backoff
        maxr = max(1, int(self.cfg.kv.cas_max_retries))
        factor = max(1, int(self.cfg.kv.cas_backoff_factor))
        delay = 0.2
        for attempt in range(1, maxr+1):
            if self._publish_state_once():
                self._last_publish_ts = now_ms
                return
            time.sleep(delay)
            delay *= factor

    # ---------- Registrar retries ----------
    def _register_with_retry(self) -> bool:
        if not self.registrar:
            return True
        attempts = max(1, int(self.cfg.registrar.max_rereg_attempts_per_window))
        cooldown = max(1, int(self.cfg.registrar.reregistration_cooldown_sec))
        for i in range(1, attempts+1):
            if self.registrar.register(self.svc):
                return True
            self.logger.warn("registrar.retry", svc=self.svc, attempt=i, cooldown_s=cooldown)
            time.sleep(cooldown)
        return False

    def _detect_run_mode(self) -> RunModeEnum:
        from core.policies.marker_policy import MarkerPolicy
        svc = self.svc or self.cfg.context.name
        rm = MarkerPolicy.detect_run_mode(self.required_markers, self.markers, svc=svc)
        self.logger.info("fsm.run_mode", svc=svc, run_mode=rm.name, required=sorted(self.required_markers))
        return rm

    def _require_stage_gates(self, state: StateEnum) -> bool:
        gates = self.stage_gates.get(state, [])
        if not gates:
            return True
        missing: list[tuple[str,str]] = []
        for gs, name in gates:
            if not self.markers.exists(gs, name):
                missing.append((gs, name))
        if missing:
            self.logger.warn("fsm.gate.wait", svc=self.svc, state=state.name, missing=[f"{gs}/{nm}" for gs,nm in missing])
            return False
        return True

    def _require_markers(self) -> tuple[bool, set[str]]:
        svc = self.svc or self.cfg.context.name
        return self.markers.require(self.required_markers, svc=svc)

    def _loop_running(self) -> None:
        hb_period = max(1, int(self.cfg.registrar.heartbeat_period_sec))
        tick_ms = max(200, int(self.cfg.fsm.state_running_tick_timeout_ms))
        next_hb = int(time.time())  # немедленный первый heartbeat
        while True:
            now = int(time.time())
            if self.registrar and now >= next_hb:
                self.registrar.heartbeat(self.svc)
                next_hb = now + hb_period
            self._publish_state()
            time.sleep(tick_ms / 1000.0)

    
    def run(self) -> None:
        # STARTING -> BOOTSTRAPPING
        self.on_enter(StateEnum.STARTING)
        self.on_enter(StateEnum.BOOTSTRAPPING)

        if not self._require_stage_gates(StateEnum.BOOTSTRAPPING):
            return

        self.run_mode = self._detect_run_mode()

        if self.run_mode in (RunModeEnum.FIRST, RunModeEnum.RECOVERY):
            self.on_enter(StateEnum.INITIALIZING)
            if not self._require_stage_gates(StateEnum.INITIALIZING):
                return
            ok, missing = self._require_markers()
            if not ok:
                self.logger.warn("fsm.wait_markers", svc=self.svc, missing=sorted(missing))
                return
            self.logger.info("fsm.markers.ready", svc=self.svc)

        # SECURING
        self.on_enter(StateEnum.SECURING)
        if not self._require_stage_gates(StateEnum.SECURING):
            return

        # TLS_TRANSITION
        self.on_enter(StateEnum.TLS_TRANSITION)
        # минимальная проверка PEM-файлов
        try:
            certs_dir = str(self.cfg.fs.certs_dir)
            cert = f"{certs_dir}/cert.pem"
            fullchain = f"{certs_dir}/fullchain.pem"
            ca = f"{certs_dir}/ca.crt"
            if not self.tls_probe.validate_chain(cert, fullchain, ca):
                self.logger.warn("tls.transition.wait_pem", svc=self.svc, dir=certs_dir)
                return
            # пробуем выполнить hot-reload контекста (идемпотентно)
            self.tls_reloader.reload_ssl_context()
        except Exception as e:
            self.logger.warn("tls.transition.error", svc=self.svc, err=type(e).__name__)
            return

        # REGISTERING
        if not self._require_stage_gates(StateEnum.REGISTERING):
            return
        self.on_enter(StateEnum.REGISTERING)

        if not self._register_with_retry():
            self.logger.warn("fsm.register.fail", svc=self.svc)
            return

        if not self._require_stage_gates(StateEnum.RUNNING):
            return

        self.on_enter(StateEnum.RUNNING)
        self._publish_state()
        self._loop_running()
    