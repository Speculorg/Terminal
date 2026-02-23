"""
speculorg.terminal.core._entities.event_code_enum
==================================================

Перечисление кодов событий.
"""

from enum import Enum


class EventCodeEnum(str, Enum):
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"

    SERVICE_RUN_START = "service.run.start"
    SERVICE_RUN_EXIT_OK = "service.run.exit.ok"
    SERVICE_RUN_EXIT_FAIL = "service.run.exit.fail"
    SERVICE_RESTART = "service.restart"
    SERVICE_STOP = "service.stop"
    SERVICE_PAUSE = "service.pause"
    SERVICE_RESUME = "service.resume"

    CONFIGS_LOAD_START = "configs.load.start"
    CONFIGS_LOAD_OK = "configs.load.ok"
    CONFIGS_LOAD_FAIL = "configs.load.fail"

    DEPS_BUILD_START = "deps.build.start"
    DEPS_BUILD_OK = "deps.build.ok"
    DEPS_BUILD_FAIL = "deps.build.fail"

    FSM_RUN_START = "fsm.run.start"
    FSM_RUN_FAIL = "fsm.run.fail"
    FSM_ENTER = "fsm.enter"
    FSM_TRANSITION = "fsm.transition"
    FSM_STATE_PUBLISH = "fsm.state.publish"

    POLICY_RUN_START = "policy.run.start"
    POLICY_RUN_OK = "policy.run.ok"
    POLICY_RUN_RETRY = "policy.run.retry"
    POLICY_RUN_FAIL = "policy.run.fail"

    DAEMON_START = "daemon.start"
    DAEMON_STOP = "daemon.stop"
    DAEMON_RESTART = "daemon.restart"
    DAEMON_SWITCH_MODE = "daemon.switch"

    TLS_VALIDATE = "tls.validate"
    TLS_RELOAD = "tls.reload"
    TLS_ROTATE = "tls.rotate"

    MARKER_SET = "marker.set"
    MARKER_DELETE = "marker.delete"
    FS_ENSURE_LAYOUT = "fs.ensure_layout"
    FS_ATOMIC_READ = "fs.atomic_read"
    FS_ATOMIC_WRITE = "fs.atomic_write"

    REGISTRAR_REGISTER = "registrar.register"
    REGISTRAR_HEARTBEAT = "registrar.heartbeat"