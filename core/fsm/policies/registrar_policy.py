from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from core._base import BasePolicy
from core._entities import StateEnum
from core._interfaces import IConfigs, ILogger, IMarkers, INet, IRegistrar
from core.tls.paths import TlsPaths


@dataclass(frozen=True, slots=True)
class RegistrarSpec:
    service: str
    address: str
    port: int
    tags: Sequence[str] = ()
    check_id: Optional[str] = None
    ttl_seconds: Optional[int] = None


class RegistrarPolicy(BasePolicy):
    """
    RegistrarPolicy регистрирует сервис и поддерживает TTL heartbeat.

    TERM-1 (автосходимость):
    - REGISTERING: блокирующая регистрация (RETRY пока не зарегистрировались)
    - RUNNING: не блокирует состояние (всегда OK), работает с backoff и самовосстановлением

    Дополнение для Consul (строгий readiness self-check):
    - перед саморегистрацией выполняется readiness:
        * tcp_wait(host, https_port)
        * https_get(/v1/status/leader)
        * https_get(/v1/agent/self) с X-Consul-Token
    - ready marker (consul_ready) выставляется только после успешного readiness
    """

    def __init__(
        self,
        *,
        cfg: IConfigs,
        registrar: IRegistrar,
        spec: RegistrarSpec,
        markers: IMarkers | None = None,
        net: INet | None = None,
        log: ILogger | None = None,
        ready_marker: str | None = None,
    ) -> None:
        super().__init__("RegistrarPolicy")
        self._cfg = cfg
        self._registrar = registrar
        self._spec = spec

        self._markers = markers
        self._ready_marker = (ready_marker or f"{spec.service}_ready") if markers is not None else None

        self._net = net
        self._log = log

        self._check_id = spec.check_id or f"service:{spec.service}:ttl"

        self._registered: bool = False
        self._last_register_mon: float = 0.0
        self._last_heartbeat_mon: float = 0.0
        self._next_register_mon: float = 0.0
        self._next_heartbeat_mon: float = 0.0
        self._register_fail_streak: int = 0
        self._heartbeat_fail_streak: int = 0

        self._window_start_mon: float = time.monotonic()
        self._window_attempts: int = 0

        self._consul_readiness_started: bool = False
        self._consul_readiness_ok: bool = False
        self._consul_last_debug_mon: float = 0.0

    def _cfg_int(self, key: str, default: int) -> int:
        try:
            return int(self._cfg.get(key, default) or default)
        except Exception:
            return int(default)

    @staticmethod
    def _backoff_sec(streak: int, *, base: float, cap: float) -> float:
        v = base * (2 ** max(0, streak))
        return cap if v > cap else v

    @staticmethod
    def _is_acl_not_ready(reason: str) -> bool:
        r = (reason or "").lower()
        return ("acl system must be bootstrapped" in r) or ("acl not found" in r)

    @staticmethod
    def _is_unknown_check(reason: str) -> bool:
        r = (reason or "").lower()
        return ("unknown check id" in r) or ("404" in r and "check" in r)

    # --- Consul readiness (self-check) ---

    def _is_consul_self(self) -> bool:
        return str(getattr(self._cfg, "service_name", "")) == "consul" and self._ready_marker == "consul_ready"

    def _consul_tls(self) -> tuple[str, str, str] | None:
        try:
            certs_dir = Path(str(self._cfg.get("FS_CERTS_DIR", "/fs/terminal/certs")))
            svc_name = str(getattr(self._cfg, "service_name", "unknown"))
            p = TlsPaths(certs_dir=certs_dir)
            return str(p.ca()), str(p.cert(svc_name)), str(p.key(svc_name))
        except Exception:
            return None

    def _consul_token(self) -> str:
        try:
            token_file = str(self._cfg.get("CONSUL_HTTP_TOKEN_FILE", "") or "").strip()
            if token_file:
                fp = Path(token_file)
                if fp.exists():
                    v = fp.read_text(encoding="utf-8").strip()
                    if v:
                        return v
        except Exception:
            pass
        return ""

    def _consul_readiness(self, *, now_mon: float) -> tuple[bool, dict[str, object]]:
        if not self._net:
            return False, {"step": "net_missing"}

        host = str(self._cfg.get("CONSUL_HOST", "consul") or "consul").strip() or "consul"
        port = int(self._cfg.get("CONSUL_HTTPS_PORT", 8501) or 8501)
        timeout_ms = self._cfg_int("NET_DEFAULT_TIMEOUT_MS", 3000)

        tls = self._consul_tls()
        if not tls:
            return False, {"step": "tls_paths_missing"}
        ca_file, cert_file, key_file = tls

        ok_tcp = self._net.tcp_wait(host, port, timeout_ms=timeout_ms)
        if not ok_tcp:
            return False, {"step": "tcp_wait", "host": host, "port": port}

        url_leader = f"https://{host}:{port}/v1/status/leader"
        code, body = self._net.https_get(
            url_leader,
            timeout_ms=timeout_ms,
            ca_file=ca_file,
            client_cert_file=cert_file,
            client_key_file=key_file,
        )
        if int(code) != 200:
            return False, {"step": "status_leader", "code": code, "body": body}

        leader = (body or "").strip().strip('"')
        if not leader:
            return False, {"step": "status_leader", "code": code, "leader": ""}

        token = self._consul_token()
        if not token:
            return False, {"step": "token_not_ready"}

        url_self = f"https://{host}:{port}/v1/agent/self"
        code2, body2 = self._net.https_get(
            url_self,
            timeout_ms=timeout_ms,
            headers={"X-Consul-Token": token},
            ca_file=ca_file,
            client_cert_file=cert_file,
            client_key_file=key_file,
        )
        if int(code2) != 200:
            return False, {"step": "agent_self", "code": code2, "body": body2}

        return True, {"leader": leader}

    def _log_consul_readiness(self, *, level: str, message: str, fields: dict[str, object]) -> None:
        if not self._log:
            return
        lv = (level or "INFO").upper()
        if lv == "DEBUG":
            self._log.debug(message, fields=fields)
        elif lv in ("WARN", "WARNING"):
            self._log.warn(message, fields=fields)
        elif lv == "ERROR":
            self._log.error(message, fields=fields)
        else:
            self._log.info(message, fields=fields)

    def _ensure_consul_ready(self, *, now_mon: float) -> tuple[bool, dict[str, object]]:
        if not self._is_consul_self():
            return True, {"skip": True}

        if self._markers is not None and self._ready_marker is not None:
            try:
                if self._markers.has(self._ready_marker):
                    return True, {"already": True}
            except Exception:
                pass

        if not self._consul_readiness_started:
            self._consul_readiness_started = True
            self._log_consul_readiness(
                level="WARN",
                message="consul readiness: start",
                fields={"svc": self._spec.service, "host": str(self._cfg.get("CONSUL_HOST", "consul")), "port": int(self._cfg.get("CONSUL_HTTPS_PORT", 8501))},
            )

        ok, details = self._consul_readiness(now_mon=now_mon)
        if ok:
            if self._markers is not None and self._ready_marker is not None:
                try:
                    self._markers.set(self._ready_marker)
                except Exception:
                    pass
            if not self._consul_readiness_ok:
                self._consul_readiness_ok = True
                self._log_consul_readiness(level="WARN", message="consul readiness: ok", fields={"svc": self._spec.service, "details": details})
            return True, details

        if now_mon - self._consul_last_debug_mon >= 5.0:
            self._consul_last_debug_mon = now_mon
            self._log_consul_readiness(level="DEBUG", message="consul readiness: wait", fields={"svc": self._spec.service, "details": details})

        return False, details

    # --- registrar operations ---

    def _register_once(self, *, ttl_sec: int) -> None:
        self._registrar.register(
            service=self._spec.service,
            address=self._spec.address,
            port=int(self._spec.port),
            tags=self._spec.tags,
            check_id=self._check_id,
            ttl_seconds=int(ttl_sec) if ttl_sec else None,
        )

    def _heartbeat_once(self) -> None:
        self._registrar.heartbeat(check_id=self._check_id)

    def _run_impl(self, *, state: StateEnum):
        now = time.monotonic()

        ttl_sec = self._spec.ttl_seconds
        if ttl_sec is None:
            ttl_sec = self._cfg_int("REGISTRAR_TTL_SEC", 15)

        heartbeat_period = self._cfg_int("REGISTRAR_HEARTBEAT_PERIOD_SEC", 20)
        cooldown = self._cfg_int("REGISTRAR_REREGISTRATION_COOLDOWN_SEC", 30)
        window_sec = max(1, self._cfg_int("REGISTRAR_DEREGISTER_CRITICAL_SERVICE_AFTER_SEC", 240))
        max_attempts = max(1, self._cfg_int("REGISTRAR_MAX_REREG_ATTEMPTS_PER_WINDOW", 5))

        reg_backoff_base = float(self._cfg_int("REGISTRAR_BACKOFF_BASE_SEC", 5))
        reg_backoff_cap = float(self._cfg_int("REGISTRAR_BACKOFF_CAP_SEC", 120))
        hb_backoff_base = float(self._cfg_int("REGISTRAR_HEARTBEAT_BACKOFF_BASE_SEC", 5))
        hb_backoff_cap = float(self._cfg_int("REGISTRAR_HEARTBEAT_BACKOFF_CAP_SEC", 120))

        if state == StateEnum.REGISTERING:
            if (now - self._window_start_mon) >= float(window_sec):
                self._window_start_mon = now
                self._window_attempts = 0

            if self._last_register_mon and (now - self._last_register_mon) < float(cooldown):
                return self.retry(reason="cooldown", details={"check_id": self._check_id})

            if self._next_register_mon and now < self._next_register_mon:
                return self.retry(reason="register_backoff", details={"check_id": self._check_id, "wait_s": round(self._next_register_mon - now, 3)})

            if self._is_consul_self():
                ok_ready, details_ready = self._ensure_consul_ready(now_mon=now)
                if not ok_ready:
                    return self.retry(reason="consul_readiness_not_ready", details={"check_id": self._check_id, **details_ready})

            if self._window_attempts >= max_attempts:
                self._next_register_mon = now + 1.0
                return self.retry(reason="reregistration_rate_limited", details={"check_id": self._check_id, "attempts": self._window_attempts})
            self._window_attempts += 1

            try:
                self._register_once(ttl_sec=int(ttl_sec))
                self._registered = True
                self._last_register_mon = now
                self._last_heartbeat_mon = now
                self._next_heartbeat_mon = now + float(heartbeat_period)
                self._register_fail_streak = 0
                if self._markers is not None and self._ready_marker is not None:
                    try:
                        self._markers.set(self._ready_marker)
                    except Exception:
                        pass
                return self.ok(details={"registered": True, "check_id": self._check_id, "ttl_sec": ttl_sec, "ready_marker": self._ready_marker})
            except RuntimeError as e:
                reason = str(e)
                extra = 2.0 if self._is_acl_not_ready(reason) else 0.0
                self._register_fail_streak += 1
                backoff = self._backoff_sec(self._register_fail_streak, base=reg_backoff_base, cap=reg_backoff_cap) + extra
                self._next_register_mon = now + backoff
                return self.retry(reason=reason, details={"check_id": self._check_id, "backoff_s": round(backoff, 3)})
            except Exception as e:
                self._register_fail_streak += 1
                backoff = self._backoff_sec(self._register_fail_streak, base=reg_backoff_base, cap=reg_backoff_cap)
                self._next_register_mon = now + backoff
                return self.retry(reason=f"registrar_error:{type(e).__name__}", details={"check_id": self._check_id, "backoff_s": round(backoff, 3), "exc": str(e)[:256]})

        if state == StateEnum.RUNNING:
            if not self._registered:
                if self._next_register_mon and now < self._next_register_mon:
                    return self.ok(details={"registered": False, "reason": "register_backoff", "check_id": self._check_id, "wait_s": round(self._next_register_mon - now, 3)})

                if self._last_register_mon and (now - self._last_register_mon) < float(cooldown):
                    return self.ok(details={"registered": False, "reason": "cooldown", "check_id": self._check_id})

                if self._is_consul_self():
                    ok_ready, details_ready = self._ensure_consul_ready(now_mon=now)
                    if not ok_ready:
                        self._next_register_mon = now + 1.0
                        return self.ok(details={"registered": False, "reason": "consul_readiness_not_ready", "check_id": self._check_id, **details_ready})

                try:
                    self._register_once(ttl_sec=int(ttl_sec))
                    self._registered = True
                    self._last_register_mon = now
                    self._last_heartbeat_mon = now
                    self._next_heartbeat_mon = now + float(heartbeat_period)
                    self._register_fail_streak = 0
                    if self._markers is not None and self._ready_marker is not None:
                        try:
                            self._markers.set(self._ready_marker)
                        except Exception:
                            pass
                    return self.ok(details={"registered": True, "check_id": self._check_id, "ttl_sec": ttl_sec, "ready_marker": self._ready_marker})
                except RuntimeError as e:
                    reason = str(e)
                    extra = 2.0 if self._is_acl_not_ready(reason) else 0.0
                    self._register_fail_streak += 1
                    backoff = self._backoff_sec(self._register_fail_streak, base=reg_backoff_base, cap=reg_backoff_cap) + extra
                    self._next_register_mon = now + backoff
                    return self.ok(details={"registered": False, "reason": reason, "check_id": self._check_id, "backoff_s": round(backoff, 3)})
                except Exception as e:
                    self._register_fail_streak += 1
                    backoff = self._backoff_sec(self._register_fail_streak, base=reg_backoff_base, cap=reg_backoff_cap)
                    self._next_register_mon = now + backoff
                    return self.ok(details={"registered": False, "reason": f"registrar_error:{type(e).__name__}", "check_id": self._check_id, "backoff_s": round(backoff, 3), "exc": str(e)[:256]})

            if self._next_heartbeat_mon and now < self._next_heartbeat_mon:
                return self.ok(details={"registered": True, "reason": "heartbeat_wait", "check_id": self._check_id, "wait_s": round(self._next_heartbeat_mon - now, 3)})

            try:
                self._heartbeat_once()
                self._last_heartbeat_mon = now
                self._next_heartbeat_mon = now + float(heartbeat_period)
                self._heartbeat_fail_streak = 0
                return self.ok(details={"registered": True, "heartbeat": "ok", "check_id": self._check_id})
            except RuntimeError as e:
                reason = str(e)
                if self._is_unknown_check(reason):
                    self._registered = False
                    self._next_register_mon = now + 0.2
                    return self.ok(details={"registered": False, "reason": reason, "check_id": self._check_id, "action": "reregister"})
                extra = 2.0 if self._is_acl_not_ready(reason) else 0.0
                self._heartbeat_fail_streak += 1
                backoff = self._backoff_sec(self._heartbeat_fail_streak, base=hb_backoff_base, cap=hb_backoff_cap) + extra
                self._next_heartbeat_mon = now + backoff
                return self.ok(details={"registered": True, "heartbeat": "fail", "reason": reason, "check_id": self._check_id, "backoff_s": round(backoff, 3)})
            except Exception as e:
                self._heartbeat_fail_streak += 1
                backoff = self._backoff_sec(self._heartbeat_fail_streak, base=hb_backoff_base, cap=hb_backoff_cap)
                self._next_heartbeat_mon = now + backoff
                return self.ok(details={"registered": True, "heartbeat": "fail", "reason": f"registrar_error:{type(e).__name__}", "check_id": self._check_id, "backoff_s": round(backoff, 3), "exc": str(e)[:256]})

        return self.ok(details={"skip": True})
