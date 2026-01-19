from __future__ import annotations

from typing import Callable, Iterable, Optional

from _base import BasePolicy
from _entities import ErrorCodeEnum, StateEnum
from _interfaces import IMarkers


class BootstrapPolicy(BasePolicy):
    """
    BootstrapPolicy выполняет bootstrap-логику (ACL/init/unseal/PKI) идемпотентно.

    На этом этапе policy является "обёрткой" для bootstrap-функции сервиса:
    - bootstrap_fn должна сама быть идемпотентной
    - успешное выполнение выставляет маркер(ы)
    
    """

    def __init__(
        self,
        *,
        name: str = "BootstrapPolicy",
        markers: IMarkers,
        done_markers: Iterable[str],
        bootstrap_fn: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(name)
        self._markers = markers
        self._done = list(done_markers)
        self._fn = bootstrap_fn

    def _run_impl(self, *, state: StateEnum):
        # если все done-markers выставлены — ничего не делаем
        missing = [m for m in self._done if not self._markers.has(m)]
        if not missing:
            return self.ok(details={"bootstrap": "already_done", "markers": self._done})

        if self._fn is None:
            return self.retry(reason="bootstrap_fn_not_set", missing=missing)

        try:
            self._fn()
        except Exception as e:
            return self.retry(reason=f"bootstrap_error:{type(e).__name__}", missing=missing)

        # повторно проверяем и ставим маркеры (политика не должна предполагать, что fn их поставила)
        for m in self._done:
            self._markers.set(m)

        return self.ok(details={"bootstrap": "done", "markers": self._done})
