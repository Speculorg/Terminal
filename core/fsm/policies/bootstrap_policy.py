from __future__ import annotations

from typing import Callable, Iterable, Optional

from core._base import BasePolicy
from core._entities import ErrorCodeEnum, StateEnum
from core._interfaces import ILogger, IMarkers


class BootstrapPolicy(BasePolicy):
    """
    BootstrapPolicy выполняет bootstrap-логику (ACL/init/unseal/PKI) идемпотентно.

    Правило:
    - bootstrap_fn должна быть идемпотентной
    - успешное выполнение -> выставляем done-markers

    Наблюдаемость:
    - при ошибке логируем причину (иначе система превращается в "немой RETRY-цикл")
    """

    def __init__(
        self,
        *,
        name: str = "BootstrapPolicy",
        markers: IMarkers,
        done_markers: Iterable[str],
        bootstrap_fn: Optional[Callable[[], None]] = None,
        log: Optional[ILogger] = None,
    ) -> None:
        super().__init__(name)
        self._markers = markers
        self._done = list(done_markers)
        self._fn = bootstrap_fn
        self._log = log

    def _run_impl(self, *, state: StateEnum):
        missing = [m for m in self._done if not self._markers.has(m)]
        if not missing:
            return self.ok(details={"bootstrap": "already_done", "markers": self._done})

        if self._fn is None:
            return self.retry(reason="bootstrap_fn_not_set", missing=missing)

        try:
            self._fn()
        except Exception as e:
            if self._log is not None:
                self._log.error(
                    "bootstrap_fn_failed",
                    fields={
                        "policy": self.name,
                        "exc_type": type(e).__name__,
                        "exc": str(e),
                        "missing": missing,
                        "state": state.value,
                    },
                )
            return self.retry(reason=f"bootstrap_error:{type(e).__name__}", missing=missing)

        for m in self._done:
            self._markers.set(m)

        return self.ok(details={"bootstrap": "done", "markers": self._done})
