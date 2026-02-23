from __future__ import annotations

import hashlib
import signal
import time
from enum import Enum
from pathlib import Path
from typing import Mapping, MutableMapping, Optional, Sequence

from core._base import BasePolicy
from core._entities import ErrorCodeEnum, EventCodeEnum, RunModeEnum, StateEnum
from core._interfaces import IConfigs, ILogger, ITLS

from core.fsm.daemon import DaemonRunner, DaemonSpec


class DaemonMode(str, Enum):
    HTTP = "http"
    HTTPS = "https"


class DaemonPolicy(BasePolicy):
    """
    DaemonPolicy управляет запуском демона внутри контейнера и переключением режимов (HTTP/HTTPS).

    TERM-1 правила:
    - INITIALIZING: не запускает демон (только RunMode через MarkerPolicy).
    - BOOTSTRAPPING:
        - RunMode.FIRST  -> стартуем HTTP (если задан start_cmd["http"])
        - RunMode.NORMAL -> no-op (демон стартуем только на SECURING)
    - SECURING: гарантируем HTTPS (после того как stage_gates разрешат вход в стадию).
    - RUNNING: supervise процесса:
        - если процесс умер — пробуем перезапустить (без рестарта контейнера)
        - при изменении TLS bundle отправляем сигнал (без рестарта процесса)
    - STOPPING: останавливаем процесс.

    Важно:
    - Мы НЕ валим контейнер при падении демона: вместо FAIL делаем RETRY (автосходимость).
    - Троттлинг рестартов задаётся DAEMON_RESTART_BACKOFF_MS (default 500ms).

    TLS reload (TERM-1):
    - Рестарт процесса для подхвата сертификатов запрещён (hot-reload).
    - DaemonPolicy может отправить сигнал (если задан DAEMON_TLS_RELOAD_SIGNAL),
      иначе только логирует "skip" и не предпринимает действий.
    """

    def __init__(
        self,
        *,
        cfg: IConfigs,
        log: ILogger,
        runner: DaemonRunner,
        start_cmd: Mapping[str, Sequence[str]],
        run_mode_ref: MutableMapping[str, object],
        tls: Optional[ITLS] = None,
        tls_bundle: Optional[Sequence[Path]] = None,
    ) -> None:
        super().__init__("DaemonPolicy")
        self._cfg = cfg
        self._log = log
        self._runner = runner
        self._run_mode_ref = run_mode_ref

        https_cmd = list(start_cmd.get(DaemonMode.HTTPS.value, ()) or ())
        http_cmd = list(start_cmd.get(DaemonMode.HTTP.value, ()) or ())
        self._cmd_https: Sequence[str] = tuple(str(x) for x in https_cmd)
        self._cmd_http: Sequence[str] = tuple(str(x) for x in http_cmd)

        self._current_mode: Optional[DaemonMode] = None

        self._tls = tls
        self._tls_bundle: Sequence[Path] = tuple(tls_bundle or ())
        self._tls_poll_ms = int(cfg.get("TLS_WATCH_POLL_INTERVAL_MS", 500) or 500)
        self._tls_next_check_ms: int = 0
        self._tls_last_fp: Optional[str] = None

        self._reload_signal = self._parse_signal(cfg.get("DAEMON_TLS_RELOAD_SIGNAL", "") or "")

        self._restart_backoff_ms = int(cfg.get("DAEMON_RESTART_BACKOFF_MS", 500) or 500)
        self._next_restart_ms: int = 0

    @staticmethod
    def _parse_signal(raw: str) -> Optional[int]:
        v = (raw or "").strip()
        if not v:
            return None
        m = {
            "SIGHUP": signal.SIGHUP,
            "SIGUSR1": signal.SIGUSR1,
            "SIGUSR2": signal.SIGUSR2,
        }
        return m.get(v.upper())

    def _run_impl(self, *, state: StateEnum):
        if state == StateEnum.INITIALIZING:
            return self.ok(details={"skip": True})

        if state == StateEnum.BOOTSTRAPPING:
            run_mode = self._get_run_mode()
            if run_mode == RunModeEnum.NORMAL:
                # В NORMAL демон поднимаем только на SECURING (после stage_gates и готового TLS).
                return self.ok(details={"skip": True, "reason": "bootstrapping_noop_in_normal"})
            return self._ensure_mode(DaemonMode.HTTP)

        if state == StateEnum.SECURING:
            return self._ensure_mode(DaemonMode.HTTPS)

        if state == StateEnum.RUNNING:
            # supervise: если процесс умер — пробуем поднять обратно
            if not self._runner.is_alive():
                return self._recover_in_running()

            self._maybe_reload_tls()
            return self.ok(details={"daemon_alive": True, "mode": (self._current_mode or DaemonMode.HTTPS).value})

        if state == StateEnum.STOPPING:
            try:
                self._runner.stop(timeout_ms=5000, sig=signal.SIGTERM)
                self._log.event(EventCodeEnum.DAEMON_STOP, fields={"svc": self._cfg.service_name})
                return self.ok(details={"daemon_stopped": True})
            except Exception:
                return self.retry(reason="daemon_stop_failed")

        return self.ok(details={"skip": True})

    def _recover_in_running(self):
        now_ms = int(time.time() * 1000)
        if now_ms < self._next_restart_ms:
            return self.retry(reason="daemon_dead_wait_backoff", details={"next_restart_ms": self._next_restart_ms})

        self._next_restart_ms = now_ms + max(50, self._restart_backoff_ms)

        # В RUNNING мы должны поддерживать HTTPS (TERM-1).
        desired_mode = self._current_mode or DaemonMode.HTTPS
        desired_cmd = self._cmd_https if desired_mode == DaemonMode.HTTPS else (self._cmd_http or self._cmd_https)

        try:
            self._runner.start(spec=DaemonSpec(cmd=desired_cmd))
            self._current_mode = desired_mode
            self._log.event(EventCodeEnum.DAEMON_RESTART, fields={"svc": self._cfg.service_name, "mode": desired_mode.value})
            return self.retry(reason="daemon_restarted_after_death", details={"mode": desired_mode.value})
        except Exception as e:
            # Не FAIL: держим контейнер живым, чтобы видеть логи и дать системе шанс автосойтись.
            return self.retry(reason=f"daemon_restart_error:{type(e).__name__}", details={"mode": desired_mode.value})

    def _get_run_mode(self) -> RunModeEnum:
        raw = self._run_mode_ref.get("run_mode", RunModeEnum.NORMAL)
        if isinstance(raw, RunModeEnum):
            return raw
        s = str(raw).strip().upper()
        if "FIRST" in s:
            return RunModeEnum.FIRST
        if "NORMAL" in s:
            return RunModeEnum.NORMAL
        return RunModeEnum.NORMAL

    def _ensure_mode(self, mode: DaemonMode):
        desired_cmd = self._cmd_https if mode == DaemonMode.HTTPS else (self._cmd_http or [])
        if not desired_cmd:
            return self.fail(error_code=ErrorCodeEnum.ERR_CONFIG, reason=f"daemon_cmd_missing:{mode.value}")

        try:
            if not self._runner.is_alive():
                self._runner.start(spec=DaemonSpec(cmd=desired_cmd))
                self._current_mode = mode
                self._log.event(EventCodeEnum.DAEMON_START, fields={"svc": self._cfg.service_name, "mode": mode.value})
                return self.ok(details={"daemon_started": True, "mode": mode.value})

            if self._current_mode is not None and self._current_mode != mode:
                cur_cmd = self._cmd_https if self._current_mode == DaemonMode.HTTPS else (self._cmd_http or [])
                if list(cur_cmd) == list(desired_cmd):
                    self._current_mode = mode
                    return self.ok(details={"daemon_alive": True, "mode": mode.value, "note": "cmd_identical_no_restart"})

                self._runner.restart(spec=DaemonSpec(cmd=desired_cmd), stop_timeout_ms=5000)
                self._current_mode = mode
                self._log.event(EventCodeEnum.DAEMON_SWITCH_MODE, fields={"svc": self._cfg.service_name, "mode": mode.value})
                return self.ok(details={"daemon_restarted": True, "mode": mode.value})

            self._current_mode = mode
            return self.ok(details={"daemon_alive": True, "mode": mode.value})

        except Exception as e:
            return self.retry(reason=f"daemon_start_error:{type(e).__name__}", details={"mode": mode.value})

    def _maybe_reload_tls(self) -> None:
        if not self._tls_bundle:
            return

        now_ms = int(time.time() * 1000)
        if now_ms < self._tls_next_check_ms:
            return

        self._tls_next_check_ms = now_ms + max(50, self._tls_poll_ms)

        fp = self._bundle_fp(self._tls_bundle)
        if self._tls_last_fp is None:
            self._tls_last_fp = fp
            return

        if fp == self._tls_last_fp:
            return

        self._tls_last_fp = fp
        self._reload_tls()

    def _bundle_fp(self, paths: Sequence[Path]) -> str:
        items: list[str] = []
        for p in sorted((Path(x) for x in paths), key=lambda x: str(x)):
            try:
                if not p.exists():
                    items.append(f"{p}:")
                else:
                    if self._tls is not None:
                        items.append(f"{p}:{self._tls.fingerprint(p)}")
                    else:
                        stat = p.stat()
                        items.append(f"{p}:{stat.st_mtime_ns}:{stat.st_size}")
            except Exception:
                items.append(f"{p}:")
        h = hashlib.sha256()
        h.update(("\\n".join(items)).encode("utf-8"))
        return h.hexdigest()

    def _reload_tls(self) -> None:
        if not self._runner.is_alive():
            return

        # TERM-1: только hot-reload, рестарт запрещён.
        if self._reload_signal is None:
            self._log.event(
                EventCodeEnum.TLS_RELOAD,
                fields={"svc": self._cfg.service_name, "action": "skip", "reason": "no_signal_configured"},
            )
            return

        try:
            self._runner.send_signal(int(self._reload_signal))
            self._log.event(
                EventCodeEnum.TLS_RELOAD,
                fields={"svc": self._cfg.service_name, "action": "signal", "sig": int(self._reload_signal)},
            )
        except Exception:
            self._log.event(
                EventCodeEnum.TLS_RELOAD,
                fields={"svc": self._cfg.service_name, "action": "skip", "reason": "signal_failed"},
            )