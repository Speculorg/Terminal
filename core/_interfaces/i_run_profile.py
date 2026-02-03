from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


@runtime_checkable
class IRunProfile(Protocol):
    """
    Спецификация тонкого сервиса для ядра.

    TERM-1 инварианты:
    - service/app/main.py остаётся тонким: RunProfile + BaseService + run()
    - ядро само собирает FSM и Deps
    - RunProfile содержит только:
        - stage_gates: декларативные условия (маркеры) для входа в состояния FSM
        - start_cmd: команды запуска демона

    Примечание по start_cmd:
    - ключ "https" обязателен всегда (рабочий режим после bootstrap)
    - ключ "http" опционален (только bootstrap-окно, если сервису требуется HTTP режим)
    """

    @property
    def stage_gates(self) -> Mapping[str, Sequence[str]]:
        """
        Ключ: имя состояния (StateEnum.value), значение: список marker-имен (gates).

        Семантика:
        - Для StateEnum.INITIALIZING: stage_gates используется только для вычисления RunMode (FIRST/NORMAL),
          не блокирует выполнение.
        - Для остальных состояний: отсутствие хотя бы одного маркера => RETRY (ожидание).
        """
        ...

    @property
    def start_cmd(self) -> Mapping[str, Sequence[str] | str | Any]:
        """
        Команды запуска демона.

        TERM-1:
        - "https": обязательна (argv list preferred).
        - "http": опциональна (argv list preferred).
        """
        ...
