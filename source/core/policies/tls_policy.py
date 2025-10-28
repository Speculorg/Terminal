from __future__ import annotations
from typing import Set, Any
from entities.state_enum import StateEnum

class TLSPolicy:
    @staticmethod
    def _has_mode(run_profile, mode: str) -> bool:
        start_cmd = getattr(run_profile, "start_cmd", None) or {}
        return mode in start_cmd

    @staticmethod
    def _securing_gates(run_profile) -> Set[str]:
        gates: dict[Any, set[str]] = (getattr(run_profile, "stage_gates", {}) or {})
        for k, v in gates.items():
            if (k is StateEnum.SECURING) or (isinstance(k, StateEnum) and k == StateEnum.SECURING):
                return set(v or set())
            if isinstance(k, str) and k.upper() == "SECURING":
                return set(v or set())
        return set()

    @staticmethod
    def decide_initial_mode(markers, run_profile) -> str:
        has_http = TLSPolicy._has_mode(run_profile, "http")
        has_https = TLSPolicy._has_mode(run_profile, "https")
        if has_https and not has_http:
            return "https"
        if has_http and not has_https:
            return "http"
        required = TLSPolicy._securing_gates(run_profile)
        if not required:
            return "http"
        try:
            ok = all(getattr(markers, "exists")(m) for m in required)
        except Exception:
            ok = False
        return "https" if ok else "http"

    def transition_if_ready(self, cfg, logger, markers, net, run_profile, current_mode: str, restart_cb, resolve_port_cb) -> None:
        """Ожидает гейты SECURING и переключает http->https через restart_cb().
        Не использует хардкод маркеров. Тайминги из cfg.fsm/tls.
        """
        # если уже https или https не поддерживается — выходим
        if current_mode != "http":
            return
        has_https = self._has_mode(run_profile, "https")
        if not has_https:
            return
        required = self._securing_gates(run_profile)
        if not required:
            return
        deadline_ms = int(getattr(cfg.fsm, "state_tls_transition_timeout_ms", 5000))
        step_ms = int(getattr(cfg.tls, "watch_poll_interval_ms", 500))
        start_ms = int(__import__("time").time() * 1000)
        # ждём появления всех требуемых маркеров
        while True:
            try:
                ok = all(getattr(markers, "exists")(m) for m in required)
            except Exception:
                ok = False
            now_ms = int(__import__("time").time() * 1000)
            if ok:
                logger.info("tls.transition.trigger", svc=cfg.context.name, details={"required": sorted(required)})
                # перезапуск в https через callback
                restart_cb("https")
                # ожидание готовности https-порта
                https_port = int(resolve_port_cb("https"))
                net.wait_port("localhost", https_port, deadline_ms=max(1000, deadline_ms//2))
                return
            if now_ms - start_ms >= deadline_ms:
                logger.info("tls.transition.skip_timeout", svc=cfg.context.name, details={"required": sorted(required)})
                return
            __import__("time").sleep(max(0.05, step_ms/1000.0))

