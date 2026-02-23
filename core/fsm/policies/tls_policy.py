from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core._base import BasePolicy
from core._entities import EventCodeEnum, StateEnum
from core._interfaces import IConfigs, ILogger, ITLS


@dataclass(frozen=True, slots=True)
class RotateCfg:
    check_interval_sec: int
    rotate_after_sec: int
    ttl: str
    vault_addr: str
    vault_token_file: Path
    pki_path: str
    role: str
    domain_root: str


class TlsPolicy(BasePolicy):
    """
    TlsPolicy:
    - SECURING: проверяет связку CA/cert/key (минимальная)
    - RUNNING: ALWAYS ON, пер-сервисная ротация leaf (name = cfg.service_name)
      через tls.rotate_leaf_if_needed(...)

    Важно:
    - RUNNING не блокируем: всегда OK.
    - Ротация сама по себе меняет файлы -> DaemonPolicy watcher выполнит reload.
    """

    def __init__(
        self,
        *,
        cfg: IConfigs,
        log: ILogger,
        tls: ITLS,
        ca_file: Path,
        cert_file: Path,
        key_file: Path,
    ) -> None:
        super().__init__("TlsPolicy")
        self._cfg = cfg
        self._log = log
        self._tls = tls
        self._ca = ca_file
        self._crt = cert_file
        self._key = key_file

        self._next_check_mon: float = 0.0
        self._fail_streak: int = 0
        self._last_warn_mon: float = 0.0
        self._last_debug_mon: float = 0.0

    def _run_impl(self, *, state: StateEnum):
        if state == StateEnum.SECURING:
            ok = self._tls.validate_chain(ca_file=self._ca, cert_file=self._crt, key_file=self._key)
            if not ok:
                return self.retry(
                    reason="tls_chain_invalid_or_missing",
                    missing=[str(self._ca), str(self._crt), str(self._key)],
                )
            return self.ok(details={"tls_chain_ok": True})

        if state == StateEnum.RUNNING:
            cfg = self._rotate_cfg()
            now = time.monotonic()
            if now < self._next_check_mon:
                return self.ok(details={"skip": True, "next_in_s": round(self._next_check_mon - now, 3)})

            self._next_check_mon = now + float(max(5, cfg.check_interval_sec))

            try:
                res = self._tls.rotate_leaf_if_needed(
                    name=self._cfg.service_name,
                    vault_addr=cfg.vault_addr,
                    vault_token_file=cfg.vault_token_file,
                    pki_path=cfg.pki_path,
                    role=cfg.role,
                    domain_root=cfg.domain_root,
                    ttl=cfg.ttl,
                    rotate_after_sec=int(cfg.rotate_after_sec),
                )

                if bool(res.get("rotated", False)):
                    self._log.event(EventCodeEnum.TLS_ROTATE, level="INFO", fields={"svc": self._cfg.service_name, **res})

                # fail streak reset on success or not_due
                reason = str(res.get("reason", "") or "")
                if reason in ("issued", "not_due"):
                    self._fail_streak = 0

                # warn if persistent hard errors (throttled)
                if reason in ("vault_token_missing", "vault_issue_http", "vault_issue_empty_pem"):
                    self._fail_streak += 1
                    if self._fail_streak >= 3 and (now - self._last_warn_mon) >= 60.0:
                        self._last_warn_mon = now
                        self._log.event(EventCodeEnum.TLS_ROTATE, level="WARN", fields={"svc": self._cfg.service_name, "streak": self._fail_streak, **res})

                return self.ok(details={"rotate": res})

            except Exception as e:  # noqa: BLE001
                self._fail_streak += 1
                backoff = min(60.0, 5.0 * (2 ** max(0, self._fail_streak - 1)))
                self._next_check_mon = time.monotonic() + backoff

                now2 = time.monotonic()
                if (now2 - self._last_debug_mon) >= 10.0:
                    self._last_debug_mon = now2
                    self._log.event(
                        EventCodeEnum.TLS_ROTATE,
                        level="DEBUG",
                        fields={"svc": self._cfg.service_name, "err": f"{type(e).__name__}:{str(e)[:200]}", "backoff_s": round(backoff, 3)},
                    )

                return self.ok(details={"rotate_err": f"{type(e).__name__}:{str(e)[:200]}", "backoff_s": round(backoff, 3)})

        return self.ok(details={"skip": True})

    def _rotate_cfg(self) -> RotateCfg:
        # берём из модели (в ней эти поля теперь есть), но читаем через cfg.get для простоты/совместимости
        check_interval_sec = int(self._cfg.get("TLS_ROTATE_CHECK_INTERVAL_SEC", 30) or 30)
        rotate_after_sec = int(self._cfg.get("TLS_ROTATE_AFTER_SEC", 300) or 300)
        ttl = str(self._cfg.get("TLS_ROTATE_TTL", "10m") or "10m").strip() or "10m"
        vault_addr = str(self._cfg.get("TLS_ROTATE_VAULT_ADDR", "https://vault:8200") or "https://vault:8200").strip()

        token_file = Path(str(self._cfg.get("TLS_ROTATE_VAULT_TOKEN_FILE", "/fs/terminal/secrets/vault_root_token.json") or "/fs/terminal/secrets/vault_root_token.json"))

        pki_path = str(self._cfg.get("VAULT_PKI_ROOT_PATH", "pki-root") or "pki-root").strip().strip("/")
        role = str(self._cfg.get("VAULT_PKI_ROLE", "terminal-leaf") or "terminal-leaf").strip()
        domain_root = str(self._cfg.get("GLOBAL_DOMAIN_ROOT", "terminal.local") or "terminal.local").strip().strip(".")

        return RotateCfg(
            check_interval_sec=max(5, int(check_interval_sec)),
            rotate_after_sec=max(60, int(rotate_after_sec)),
            ttl=ttl,
            vault_addr=vault_addr,
            vault_token_file=token_file,
            pki_path=pki_path,
            role=role,
            domain_root=domain_root,
        )