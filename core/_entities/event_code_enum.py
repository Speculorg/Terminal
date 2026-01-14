"""
speculorg.terminal.core._entities.event_code_enum
==================================================

Перечисление кодов событий.
"""
from enum import Enum


class EventCodeEnum(Enum):
    """
    Коды событий, используемые для логирования и мониторинга.
    """
    # События сервиса
    SERVICE_RUN_START = "service.run.start"
    SERVICE_RUN_EXIT_OK = "service.run.exit.ok"
    SERVICE_RUN_EXIT_FAIL = "service.run.exit.fail"
    SERVICE_CONSTRUCT_FAIL = "service.construct.fail"

    # События FSM
    FSM_STATE_TRANSITION = "fsm.state.transition"
    FSM_STATE_DEADLINE_EXCEEDED = "fsm.state.deadline.exceeded"
    FSM_POLICY_RESULT = "fsm.policy.result"

    # События зависимостей
    DEPS_BUILD_START = "deps.build.start"
    DEPS_BUILD_DONE = "deps.build.done"
    DEPS_CLOSE_START = "deps.close.start"
    DEPS_CLOSE_DONE = "deps.close.done"

    # События файловой системы
    FS_ENSURE_LAYOUT_DONE = "fs.ensure_layout.done"
    FS_ENSURE_LAYOUT_SKIP = "fs.ensure_layout.skip"

    # События маркеров
    MARKER_CREATE = "marker.create"
    MARKER_CHECK = "marker.check"
    MARKER_MISSING = "marker.missing"

    # События TLS
    TLS_CERT_RELOAD_TRIGGERED = "tls.cert.reload.triggered"
    TLS_CERT_RELOAD_SUCCESS = "tls.cert.reload.success"
    TLS_CERT_RELOAD_FAILED = "tls.cert.reload.failed"

    # События процесса демона
    DAEMON_START_ATTEMPT = "daemon.start.attempt"
    DAEMON_STARTED = "daemon.started"
    DAEMON_STOP_ATTEMPT = "daemon.stop.attempt"
    DAEMON_STOPPED = "daemon.stopped"
    DAEMON_MONITOR_STATUS = "daemon.monitor.status"
