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
    - INITIALIZING: не запускает демон (только вычисление RunMode через MarkerPolicy).
    - BOOTSTRAPPING:
        - RunMode.FIRST  -> стартуем HTTP (если задан start_cmd["http"])
        - RunMode.NORMAL -> стартуем HTTPS
    - SECURING: гарантируем HTTPS
    - RUNNING: контролируем, что процесс жив, и применяем auto-reload TLS при изменении PEM файлов.
    - STOPPING: останавливаем процесс.

    TLS reload:
    - Если задан DAEMON_TLS_RELOAD_SIGNAL (например SIGHUP), при изменении TLS bundle отправляем сигнал процессу.
    - Иначе выполняем restart процесса (внутри контейнера, без рестарта контейнера).
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

        # start_cmd: https обязателен, http опционален
        https_cmd = list(start_cmd.get(DaemonMode.HTTPS.value, ()) or ())
        http_cmd = list(start_cmd.get(DaemonMode.HTTP.value, ()) or ())

        if not https_cmd:
            raise ValueError("run_profile.start_cmd must include non-empty 'https' command")

        self._cmd_http: Optional[list[str]] = http_cmd if http_cmd else None
        self._cmd_https: list[str] = https_cmd

        self._current_mode: Optional[DaemonMode] = None

        # TLS reload settings
        self._tls = tls
        self._tls_bundle = list(tls_bundle or ())
        self._tls_poll_ms = int(self._cfg.get("TLS_WATCH_POLL_INTERVAL_MS", 500) or 500)
        self._tls_next_check_ms = 0
        self._tls_last_fp: Optional[str] = None

        self._reload_signal = self._parse_signal(str(self._cfg.get("DAEMON_TLS_RELOAD_SIGNAL", "") or ""))

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
            # По требованиям: INITIALIZING не поднимает демон.
            return self.ok(details={"skip": True})

        if state == StateEnum.BOOTSTRAPPING:
            desired = self._desired_mode_bootstrapping()
            return self._ensure_mode(desired)

        if state == StateEnum.SECURING:
            return self._ensure_mode(DaemonMode.HTTPS)

        if state == StateEnum.RUNNING:
            if not self._runner.is_alive():
                return self.fail(error_code=ErrorCodeEnum.ERR_PROC, reason="daemon_process_dead")

            # TLS auto-reload (best-effort)
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

    def _desired_mode_bootstrapping(self) -> DaemonMode:
        """
        Определяем желаемый режим демона на стадии BOOTSTRAPPING.

        Источник истины: run_mode_ref["run_mode"], выставляется MarkerPolicy в INITIALIZING.
        """
        raw = self._run_mode_ref.get("run_mode", RunModeEnum.NORMAL)
        run_mode: RunModeEnum
        if isinstance(raw, RunModeEnum):
            run_mode = raw
        else:
            s = str(raw).strip().upper()
            if "FIRST" in s:
                run_mode = RunModeEnum.FIRST
            elif "NORMAL" in s:
                run_mode = RunModeEnum.NORMAL
            else:
                run_mode = RunModeEnum.NORMAL

        if run_mode == RunModeEnum.FIRST:
            return DaemonMode.HTTP

        return DaemonMode.HTTPS

    def _ensure_mode(self, mode: DaemonMode):
        try:
            desired_cmd = self._cmd_https if mode == DaemonMode.HTTPS else (self._cmd_http or [])
            if not desired_cmd:
                # Явная ошибка RunProfile: объявили необходимость HTTP (RunMode.FIRST),
                # но не предоставили start_cmd['http'].
                return self.fail(error_code=ErrorCodeEnum.ERR_CONFIG, reason=f"daemon_cmd_missing:{mode.value}")

            if not self._runner.is_alive():
                self._runner.start(spec=DaemonSpec(cmd=desired_cmd))
                self._current_mode = mode
                self._log.event(EventCodeEnum.DAEMON_START, fields={"svc": self._cfg.service_name, "mode": mode.value})
                return self.ok(details={"daemon_started": True, "mode": mode.value})

            # если живой процесс, но режим должен измениться -> restart
            if self._current_mode is not None and self._current_mode != mode:
                # если команды идентичны — рестарт не нужен
                cur_cmd = self._cmd_https if self._current_mode == DaemonMode.HTTPS else (self._cmd_http or [])
                if list(cur_cmd) == list(desired_cmd):
                    self._current_mode = mode
                    return self.ok(details={"daemon_alive": True, "mode": mode.value, "note": "cmd_identical_no_restart"})

                self._runner.restart(spec=DaemonSpec(cmd=desired_cmd), stop_timeout_ms=5000)
                self._current_mode = mode
                code = EventCodeEnum.DAEMON_SWITCH_HTTPS if mode == DaemonMode.HTTPS else EventCodeEnum.DAEMON_SWITCH_HTTP
                self._log.event(code, fields={"svc": self._cfg.service_name, "mode": mode.value})
                return self.ok(details={"daemon_restarted": True, "mode": mode.value})

            # режим уже нужный
            self._current_mode = mode
            return self.ok(details={"daemon_alive": True, "mode": mode.value})

        except Exception as e:
            return self.retry(reason=f"daemon_start_error:{type(e).__name__}")

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
        h.update(("\n".join(items)).encode("utf-8"))
        return h.hexdigest()

    def _reload_tls(self) -> None:
        """
        Best-effort: попытаться применить новые PEM.

        Факт: ядро умеет только два механизма:
        - отправить сигнал (если задан DAEMON_TLS_RELOAD_SIGNAL)
        - выполнить restart процесса

        Как конкретный демон реагирует на сигнал — ответственность его конфигурации/документации.
        """
        try:
            sig = self._reload_signal
            if sig is not None:
                self._runner.send_signal(sig)
                self._log.event(
                    EventCodeEnum.TLS_RELOAD,
                    fields={"svc": self._cfg.service_name, "strategy": "signal", "signal": int(sig)},
                )
                return

            mode = self._current_mode or DaemonMode.HTTPS
            cmd = self._cmd_https if mode == DaemonMode.HTTPS else (self._cmd_http or self._cmd_https)
            self._runner.restart(spec=DaemonSpec(cmd=cmd), stop_timeout_ms=5000)
            self._log.event(
                EventCodeEnum.TLS_RELOAD,
                fields={"svc": self._cfg.service_name, "strategy": "restart", "mode": mode.value},
            )

        except Exception:
            return
