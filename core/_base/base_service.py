from __future__ import annotations

import time
from typing import Optional

from _entities import HealthSnapshotType, StateEnum
from _interfaces import IDeps, IDepsFactory, IFSM, IRunProfile, IService


class BaseService(IService):
    """
    Тонкий каркас сервиса.

    Инварианты:
    - __init__ ничего не запускает
    - run() можно вызвать только один раз (entrypoint)
    - IDeps.close() вызывается гарантированно в finally
    - FSM создаётся отдельно и НЕ входит в Deps
    """

    def __init__(self, *, run_profile: IRunProfile, deps_factory: IDepsFactory) -> None:
        self._run_profile = run_profile
        self._deps_factory = deps_factory

        self._deps: Optional[IDeps] = None
        self._fsm: Optional[IFSM] = None

        self._started = False
        self._snapshot: HealthSnapshotType = {}

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    # --- hooks for concrete services ---

    def build_fsm(self, *, deps: IDeps) -> IFSM:
        """
        Создать FSM для сервиса.
        Конкретный сервис/ядро переопределяет и возвращает реализацию core/fsm/FSM.
        """
        raise NotImplementedError

    # --- IService ---

    def run(self) -> None:
        if self._started:
            raise RuntimeError("service.run() must be called only once")
        self._started = True

        deps = self._deps_factory.build()
        self._deps = deps

        svc = getattr(deps.cfg, "service_name", "unknown")
        self._snapshot = {
            "svc": str(svc),
            "state": StateEnum.STARTING,
            "ts_ms": self._now_ms(),
            "since_ts_ms": self._now_ms(),
            "health": {},
            "details": {},
        }

        fsm = self.build_fsm(deps=deps)
        self._fsm = fsm

        try:
            fsm.run()
        finally:
            try:
                deps.close()
            finally:
                self._snapshot["ts_ms"] = self._now_ms()
                # если FSM доступен — отражаем финальное состояние
                try:
                    self._snapshot["state"] = fsm.get_state()
                except Exception:
                    self._snapshot["state"] = StateEnum.ERROR

    def pause(self) -> None:
        if self._fsm is None:
            return
        self._fsm.pause()

    def resume(self) -> None:
        if self._fsm is None:
            return
        self._fsm.resume()

    def restart(self) -> None:
        if self._fsm is None:
            return
        self._fsm.restart()

    def stop(self) -> None:
        if self._fsm is None:
            return
        self._fsm.stop()

    def get_state(self) -> HealthSnapshotType:
        # В TERM-1 HealthSnapshot живёт in-memory.
        if self._fsm is not None:
            try:
                self._snapshot["state"] = self._fsm.get_state()
            except Exception:
                self._snapshot["state"] = StateEnum.ERROR
        self._snapshot["ts_ms"] = self._now_ms()
        return dict(self._snapshot)
