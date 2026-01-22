from __future__ import annotations

import signal
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from core._base import BasePolicy
from core._entities import ErrorCodeEnum, StateEnum
from core._interfaces import IMarkers

from core.fsm.daemon import DaemonRunner, DaemonSpec


class DaemonMode(str, Enum):
    HTTP = "http"
    HTTPS = "https"


@dataclass(frozen=True, slots=True)
class DaemonStartProfile:
    mode: DaemonMode
    cmd: Sequence[str]


class DaemonPolicy(BasePolicy):
    """
    DaemonPolicy управляет запуском демона.

    Основная идея TERM-1:
    - INITIALIZING/BOOTSTRAPPING: запуск демона в HTTP (loopback-only внутри контейнера)
    - SECURING: переключение демона на HTTPS (после появления certs)
    - RUNNING: контроль, что процесс жив (если умер — FAIL/RETRY по стратегии сервиса)

    Политика опирается на маркер режима запуска:
    - marker: "daemon.mode.https" (наличие -> считаем что должны быть в HTTPS)
    """

    HTTPS_MARKER = "daemon.mode.https"

    def __init__(
        self,
        *,
        runner: DaemonRunner,
        markers: IMarkers,
        start_cmd: Mapping[str, Sequence[str]],
        http_mode: DaemonMode = DaemonMode.HTTP,
        https_mode: DaemonMode = DaemonMode.HTTPS,
    ) -> None:
        super().__init__("DaemonPolicy")
        self._runner = runner
        self._markers = markers
        self._cmd = {str(k): list(v) for k, v in start_cmd.items()}
        self._http = http_mode
        self._https = https_mode

        if self._http.value not in self._cmd or self._https.value not in self._cmd:
            raise ValueError("start_cmd must include 'http' and 'https' keys")

        self._current_mode: DaemonMode = DaemonMode.HTTP

    def _run_impl(self, *, state: StateEnum):
        if state in (StateEnum.INITIALIZING, StateEnum.BOOTSTRAPPING):
            return self._ensure_mode(self._http)

        if state == StateEnum.SECURING:
            # Переходим на HTTPS в состоянии SECURING.
            # Валидность/наличие certs обеспечивает TlsPolicy, поэтому здесь нет дополнительных gate-маркеров.
            return self._ensure_mode(self._https)

        if state == StateEnum.RUNNING:
            if not self._runner.is_alive():
                return self.fail(error_code=ErrorCodeEnum.ERR_PROC, reason="daemon_process_dead")
            return self.ok(details={"daemon_alive": True, "mode": self._current_mode.value})

        if state == StateEnum.STOPPING:
            try:
                self._runner.stop(timeout_ms=5000, sig=signal.SIGTERM)
                return self.ok(details={"daemon_stopped": True})
            except Exception:
                return self.retry(reason="daemon_stop_failed")

        return self.ok(details={"skip": True})

    def _ensure_mode(self, mode: DaemonMode):
        try:
            if not self._runner.is_alive():
                self._runner.start(spec=DaemonSpec(cmd=self._cmd[mode.value]))
                self._current_mode = mode
                return self.ok(details={"daemon_started": True, "mode": mode.value})

            # если живой процесс, но режим должен измениться -> restart
            if self._current_mode != mode:
                self._runner.restart(spec=DaemonSpec(cmd=self._cmd[mode.value]), stop_timeout_ms=5000)
                self._current_mode = mode
                return self.ok(details={"daemon_restarted": True, "mode": mode.value})

            return self.ok(details={"daemon_alive": True, "mode": mode.value})

        except Exception as e:
            return self.retry(reason=f"daemon_start_error:{type(e).__name__}")
