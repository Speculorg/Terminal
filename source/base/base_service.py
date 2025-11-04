from __future__ import annotations
from typing import Optional

from .base_deps import BaseDepsFactory
from interfaces import IService, IRunProfile

class BaseService(IService):
    """Тонкий каркас сервиса.
    - Конструктор НИЧЕГО не запускает, только собирает зависимости и профиль.
    - run() инициализирует FSM (svc, stage_gates) и делегирует выполнение FSM.
    - Никакой предметной логики TLS/портов/режимов внутри.
    """
    def __init__(self, run_profile: IRunProfile) -> None:
        self.run_profile = run_profile
        deps = BaseDepsFactory.build()
        # разматываем зависимости в поля (минимально необходимое)
        self._cfg = deps.cfg
        self._logger = deps.logger
        self._fs = deps.fs
        self._markers = deps.markers
        self._net = deps.net
        self._kv = getattr(deps, "kv", None)
        self._metrics = getattr(deps, "metrics", None)
        self._registrar = getattr(deps, "registrar", None)
        self._fsm = deps.fsm

        # Подготовка FSM: имя сервиса и stage_gates с профиля
        self._fsm.svc = self._cfg.context.name  # type: ignore[attr-defined]
        if hasattr(self.run_profile, "stage_gates"):
            self._fsm.stage_gates = getattr(self.run_profile, "stage_gates")  # type: ignore[attr-defined]

    # --- IService протокол ---
    def initialize(self) -> None:
        pass

    def start(self) -> None:
        pass

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass

    def restart(self) -> None:
        # Делегируем FSM, если реализовано
        if hasattr(self._fsm, "restart"):
            self._fsm.restart()  # type: ignore[attr-defined]

    def stop(self) -> None:
        if hasattr(self._fsm, "stop"):
            self._fsm.stop()  # type: ignore[attr-defined]

    # --- главный вход ---
    def run(self) -> None:
        """Инициализация FSM и запуск стандартного сценария FSM."""
        # FSM уже сконфигурирован в __init__. Делегируем выполнение.
        if hasattr(self._fsm, "run"):
            self._fsm.run()  # type: ignore[attr-defined]
