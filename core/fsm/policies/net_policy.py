from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core._base import BasePolicy
from core._entities import ErrorCodeEnum, StateEnum
from core._interfaces import INet


@dataclass(frozen=True, slots=True)
class NetCheck:
    """
    Описание сетевой проверки.
    kind:
      - "tcp": tcp_check(host, port)
      - "http": http_get(url)
    """
    kind: str
    target: str
    timeout_ms: int = 3000
    verify_tls: bool = True
    ca_file: str | None = None
    client_cert_file: str | None = None
    client_key_file: str | None = None


class NetPolicy(BasePolicy):
    """
    NetPolicy выполняет набор сетевых проверок (tcp/http) и блокирует переход,
    пока они не станут успешными.
    
    """

    def __init__(self, *, net: INet, checks: Sequence[NetCheck]) -> None:
        super().__init__("NetPolicy")
        self._net = net
        self._checks = list(checks)

    def _run_impl(self, *, state: StateEnum):
        missing: list[str] = []
        details: dict[str, object] = {"checks": []}

        for c in self._checks:
            if c.kind == "tcp":
                host, port_s = c.target.split(":", 1)
                ok = self._net.tcp_check(host.strip(), int(port_s.strip()), timeout_ms=c.timeout_ms)
                details["checks"].append({"kind": "tcp", "target": c.target, "ok": ok})
                if not ok:
                    missing.append(f"tcp:{c.target}")
                    continue

            elif c.kind == "http":
                code, body = self._net.http_get(
                    c.target,
                    timeout_ms=c.timeout_ms,
                    verify_tls=c.verify_tls,
                    ca_file=c.ca_file,
                    client_cert_file=c.client_cert_file,
                    client_key_file=c.client_key_file,
                )
                ok = (code >= 200 and code < 400)
                details["checks"].append({"kind": "http", "target": c.target, "code": code, "ok": ok, "body": body})
                if not ok:
                    missing.append(f"http:{c.target}")
                    continue
            else:
                return self.fail(error_code=ErrorCodeEnum.ERR_PRECONDITION, reason=f"unknown_check_kind:{c.kind}")

        if missing:
            return self.retry(reason="net_checks_failed", missing=missing, details=details)

        return self.ok(details=details)
