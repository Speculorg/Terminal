from __future__ import annotations
from typing import Dict, List
from entities import StateEnum
from .marker_policy import MarkerPolicy
from .init_policy import InitPolicy
from .daemon_policy import DaemonPolicy
from .port_ready_policy import PortReadyPolicy
from .tls_policy import TLSPolicy
from .register_policy import RegisterPolicy

def build_policies(logger, cfg, fs, markers, net, profile, *, restart_cb=None, resolve_port_cb=None) -> Dict[StateEnum, List]:
    return {
        StateEnum.STARTING: [],
        StateEnum.BOOTSTRAPPING: [
            MarkerPolicy(logger, markers, profile, StateEnum.BOOTSTRAPPING, strict=False),
            InitPolicy(logger, cfg, fs, markers, net, StateEnum.BOOTSTRAPPING),
        ],
        StateEnum.INITIALIZING: [
            MarkerPolicy(logger, markers, profile, StateEnum.INITIALIZING, strict=True),
        ],
        StateEnum.SECURING: [
            MarkerPolicy(logger, markers, profile, StateEnum.SECURING, strict=True),
        ],
        StateEnum.TLS_TRANSITION: [
            MarkerPolicy(logger, markers, profile, StateEnum.TLS_TRANSITION, strict=True),
            TLSPolicy(logger, cfg, markers, net, profile, resolve_port_cb, restart_cb),
            PortReadyPolicy(logger, cfg, net, profile, mode="https"),
        ],
        StateEnum.REGISTERING: [
            MarkerPolicy(logger, markers, profile, StateEnum.REGISTERING, strict=True),
            RegisterPolicy(logger),
        ],
        StateEnum.RUNNING: [],
    }
