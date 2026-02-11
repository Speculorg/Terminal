from __future__ import annotations

import time
from typing import Mapping, Sequence

from core._base import BaseFSM
from core._entities import (
    ErrorCodeEnum,
    EventCodeEnum,
    PolicyStatusEnum,
    StateEnum,
)
from core._interfaces import IConfigs, ILogger, IMarkers, IPolicy


class FSM(BaseFSM):
    """
    Реализация IFSM (TERM-1).

    Цели:
    - фиксированный порядок состояний
    - фиксированная матрица state -> policies
    - минимальная наблюдаемость (HealthSnapshot in-memory)
    - минимальные команды управления: pause/resume/restart/stop

    Важно:
    - stage_gates проверяются MarkerPolicy, но не FSM.
    - FSM не пересобирает Deps и не знает про конкретные сервисы.
    """

    ORDER: tuple[StateEnum, ...] = (
        StateEnum.STARTING,
        StateEnum.INITIALIZING,
        StateEnum.BOOTSTRAPPING,
        StateEnum.SECURING,
        StateEnum.REGISTERING,
        StateEnum.RUNNING,
        StateEnum.STOPPING,
        StateEnum.STOPPED,
    )

    def __init__(
        self,
        *,
        cfg: IConfigs,
        log: ILogger,
        markers: IMarkers,
        service_name: str,
        policy_matrix: Mapping[StateEnum, Sequence[IPolicy]] | None = None,
    ) -> None:
        super().__init__(
            cfg=cfg,
            log=log,
            markers=markers,
            service_name=service_name,
            policy_matrix=dict(policy_matrix or {}),
        )

        self._log.event(EventCodeEnum.FSM_RUN_START, fields={"svc": service_name})

    # --- main loop ---

    def run(self) -> None:
        """
        Главный цикл FSM.

        Семантика:
        - В bootstrap-части: retry-forever (если политика даёт RETRY)
        - На FAIL: ERROR и останов (fail-fast)
        - RUNNING: циклический тик, политики должны быть быстрыми
        - restart(): сбрасывает флаг и повторяет проход с INITIALIZING
        """
        try:
            while True:
                if self._stop:
                    self.transition(StateEnum.STOPPING)
                    self._tick_state(StateEnum.STOPPING)
                    self.transition(StateEnum.STOPPED)
                    return

                if self._restart:
                    self._restart = False
                    # минимальный “сброс”: возвращаемся к INITIALIZING (deps остаются теми же)
                    self.transition(StateEnum.INITIALIZING)

                st = self.get_state()
                if st == StateEnum.PAUSED:
                    time.sleep(self._retry_sleep_s(StateEnum.PAUSED))
                    continue

                # если state не из ORDER (например ERROR/DEGRADED), удерживаем
                if st not in self.ORDER:
                    time.sleep(self._retry_sleep_s(st))
                    continue

                if st == StateEnum.STOPPED:
                    return

                ok = self._tick_state(st)
                if not ok:
                    self.transition(StateEnum.ERROR)
                    self.publish_state(details={"error_code": ErrorCodeEnum.ERR_UNEXPECTED})
                    return

                # RUNNING — остаёмся в RUNNING и тикаем, а не продвигаемся дальше
                if st == StateEnum.RUNNING:
                    time.sleep(self._running_tick_s())
                    continue

                # продвигаемся к следующему состоянию
                nxt = self._next_state(st)
                self.transition(nxt)

        except Exception as e:
            try:
                self._log.event(
                    EventCodeEnum.FSM_RUN_FAIL,
                    level="ERROR",
                    message=str(e),
                    fields={"svc": getattr(self._cfg, "service_name", "unknown")},
                )
            except Exception:
                pass
            self.transition(StateEnum.ERROR)
            return

    # --- internals ---

    def _next_state(self, st: StateEnum) -> StateEnum:
        try:
            idx = list(self.ORDER).index(st)
            if idx >= len(self.ORDER) - 1:
                return StateEnum.STOPPED
            return self.ORDER[idx + 1]
        except ValueError:
            return StateEnum.ERROR

    def _state_deadline_ms(self, st: StateEnum) -> int:
        """
        Дедлайны берём через cfg.get для совместимости с текущими env-ключами.
        0 означает “без дедлайна”.
        """
        key_map = {
            StateEnum.INITIALIZING: "FSM_STATE_INITIALIZING_TIMEOUT_MS",
            StateEnum.BOOTSTRAPPING: "FSM_STATE_BOOTSTRAPPING_TIMEOUT_MS",
            StateEnum.SECURING: "FSM_STATE_SECURING_TIMEOUT_MS",
            StateEnum.REGISTERING: "FSM_STATE_REGISTERING_TIMEOUT_MS",
            StateEnum.STOPPING: "FSM_STATE_STOPPING_TIMEOUT_MS",
        }
        key = key_map.get(st)
        if not key:
            return 0
        try:
            return int(self._cfg.get(key, 0) or 0)
        except Exception:
            return 0

    def _running_tick_s(self) -> float:
        try:
            ms = int(self._cfg.get("FSM_STATE_RUNNING_TICK_TIMEOUT_MS", 1000) or 1000)
            return max(0.05, ms / 1000.0)
        except Exception:
            return 1.0

    def _retry_sleep_s(self, st: StateEnum) -> float:
        """
        Backoff для RETRY/ожиданий, чтобы не засорять логи.

        Ключи конфигурации:
        - FSM_RETRY_SLEEP_MS (дефолт 1000)
        - FSM_RETRY_SLEEP_<STATE>_MS (например FSM_RETRY_SLEEP_REGISTERING_MS)
        """
        # per-state override
        key = f"FSM_RETRY_SLEEP_{st.value}_MS"
        try:
            v = self._cfg.get(key, None)
            if v is not None and str(v).strip() != "":
                ms = int(v)
                return max(0.05, ms / 1000.0)
        except Exception:
            pass

        # global default
        try:
            ms = int(self._cfg.get("FSM_RETRY_SLEEP_MS", 1000) or 1000)
            return max(0.05, ms / 1000.0)
        except Exception:
            return 1

    def _tick_state(self, st: StateEnum) -> bool:
        """
        Выполнение одного состояния.

        Порядок:
        1) policies: OK/RETRY/FAIL
        2) deadline: если вышли за deadline -> FAIL
        """
        enter_ms = self._now_ms()
        deadline_ms = self._state_deadline_ms(st)

        while True:
            if self._stop:
                return True

            if self._restart and st != StateEnum.RUNNING:
                # даём быстрый выход из текущего состояния для рестарта
                return True

            if self.get_state() == StateEnum.PAUSED:
                time.sleep(self._retry_sleep_s(StateEnum.PAUSED))
                continue

            status = self.run_policies(st)
            if status == PolicyStatusEnum.OK:
                return True
            if status == PolicyStatusEnum.FAIL:
                return False

            # RETRY
            if deadline_ms > 0 and (self._now_ms() - enter_ms) > deadline_ms:
                self.publish_state(details={"deadline_ms": deadline_ms, "state": st.value})
                return False

            time.sleep(self._retry_sleep_s(st))
