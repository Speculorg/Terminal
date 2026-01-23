from __future__ import annotations

from typing import Optional

from core._entities import ErrorCodeEnum, PolicyResultType, PolicyStatusEnum, StateEnum
from core._interfaces import IPolicy


class BasePolicy(IPolicy):
    """
    Базовый каркас политики.

    Принцип: базовый класс не должен бросать NotImplementedError.
    Если _run_impl не переопределён, политика возвращает FAIL с понятной причиной.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def run(self, *, state: StateEnum) -> PolicyResultType:
        return self._run_impl(state=state)

    def _run_impl(self, *, state: StateEnum) -> PolicyResultType:
        return self.fail(error_code=ErrorCodeEnum.ERR_UNEXPECTED, reason="policy_not_implemented", details={"policy": self._name, "state": str(state)})

    # --- helpers (единая семантика) ---

    def ok(self, *, details: Optional[dict[str, object]] = None) -> PolicyResultType:
        return {"status": PolicyStatusEnum.OK, "details": details}

    def retry(
        self,
        *,
        reason: str,
        missing: Optional[list[str]] = None,
        details: Optional[dict[str, object]] = None,
    ) -> PolicyResultType:
        d: dict[str, object] = {"reason": reason}
        if missing:
            d["missing"] = missing
        if details:
            d["meta"] = details
        return {"status": PolicyStatusEnum.RETRY, "details": d}

    def fail(
        self,
        *,
        error_code: ErrorCodeEnum | str = ErrorCodeEnum.ERR_UNEXPECTED,
        reason: str,
        details: Optional[dict[str, object]] = None,
    ) -> PolicyResultType:
        d: dict[str, object] = {"error_code": str(error_code), "reason": reason}
        if details:
            d["meta"] = details
        return {"status": PolicyStatusEnum.FAIL, "details": d}
