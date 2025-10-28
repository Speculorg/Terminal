# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from typing import Set, Dict, Optional, Iterable
import re

from entities import RunModeEnum
from entities import StateEnum
from interfaces.i_run_profile import IRunProfile
from interfaces.i_marker import IMarker
from interfaces.i_logger import ILogger
from interfaces.i_configs import IConfigs
from .tls_policy import TLSPolicy

_MARKER_RE = re.compile(r"^[a-z0-9]+_[a-z0-9]+\.done$", re.IGNORECASE)
_MARKER_SUFFIX = ".done"

class ERR_PRECONDITION(Exception):
    """Нарушены предусловия входа в состояние (stage gate)."""

def _validate_flat_markers(markers: Iterable[str]) -> Set[str]:
    out: Set[str] = set()
    for m in markers:
        if not isinstance(m, str):
            raise ValueError(f"gate marker must be str, got {type(m).__name__}")
        mm = m.strip()
        if "/" in mm:
            raise ValueError(f"gate marker must be flat without '/', got: {mm}")
        if not mm.endswith(_MARKER_SUFFIX):
            raise ValueError(f"gate marker must end with '{_MARKER_SUFFIX}', got: {mm}")
        if not _MARKER_RE.match(mm):
            # строго требуем <svc>_<name>.done
            raise ValueError(f"gate marker must match '<svc>_<name>.done', got: {mm}")
        out.add(mm)
    return out

@dataclass
class FSMPolicy:
    cfg: IConfigs
    logger: ILogger | None = None
    markers: IMarker | None = None
    profile: IRunProfile | None = None

    # === Входной гейт состояния ===
    def require_stage_gates(self, state: StateEnum) -> None:
        """Строгая проверка stage_gates: только плоские имена '<svc>_<name>.done'. Без конверсий."""
        if self.profile is None:
            return
        gates = getattr(self.profile, "stage_gates", None)
        if not gates:
            return
        required = gates.get(state)  # type: ignore[arg-type]
        if not required:
            return
        req = _validate_flat_markers(required)
        if not req:
            return
        if self.markers is None:
            raise RuntimeError("markers facade is not provided to FSMPolicy")
        ok, missing = self.markers.require(req, svc=self.cfg.context.name)
        if not ok:
            miss = sorted(list(missing))
            if self.logger:
                self.logger.error("fsm.stage_gate.missing", svc=self.cfg.context.name, state=state.name, details={"missing": miss})
            raise ERR_PRECONDITION(f"stage gates missing for {state.name}: {', '.join(miss)}")
        if self.logger:
            self.logger.info("fsm.stage_gate.ok", svc=self.cfg.context.name, state=state.name, details={"required": sorted(list(req))})

    # === STARTING -> BOOTSTRAPPING gate ===
    def check_prereq(self) -> bool:
        # Простая проверка окружения без сетевых проб
        return True

    # === BOOTSTRAPPING transitions by run_mode ===
    def first_run(self) -> StateEnum:
        return StateEnum.INITIALIZING

    def recovery_run(self) -> StateEnum:
        return StateEnum.INITIALIZING

    def normal_run(self) -> StateEnum:
        return StateEnum.SECURING

    # === INITIALIZING -> SECURING gate when one-shot ops done ===
    def bootstrap_gate(self) -> StateEnum:
        return StateEnum.SECURING

    # === TLS_TRANSITION handler ===
    def switch_https(self) -> StateEnum:
        return StateEnum.REGISTERING

    # === REGISTERING -> RUNNING gate ===
    def on_register_ok(self) -> StateEnum:
        return StateEnum.RUNNING

    # === Error handling ===
    def on_error(self, current: StateEnum) -> StateEnum:
        return StateEnum.DEGRADED

    def on_fail(self, current: StateEnum) -> StateEnum:
        return StateEnum.ERROR

    # === RUNNING tick ===
    def on_tick(self) -> StateEnum:
        return StateEnum.RUNNING


    # === TLS transition trigger ===
    def handle_tls_transition(self, cfg: IConfigs, logger: ILogger, markers: IMarker, net, run_profile: IRunProfile, current_mode: str, restart_cb, resolve_port_cb) -> None:
        """Делегирует решение и исполнение TLS-перехода в TLSPolicy."""
        try:
            TLSPolicy().transition_if_ready(cfg, logger, markers, net, run_profile, current_mode, restart_cb, resolve_port_cb)
        except Exception as e:
            try:
                logger.warn("tls.transition.error", svc=cfg.context.name, details={"error": str(e)})
            except Exception:
                pass

# === Pause/Resume/Stop ===
    def pause(self) -> StateEnum:
        return StateEnum.PAUSED

    def resume(self) -> StateEnum:
        return StateEnum.RUNNING

    def stop(self) -> StateEnum:
        return StateEnum.STOPPING

    # === Restart gate ===
    def restart_gate(self) -> StateEnum:
        return StateEnum.STARTING
