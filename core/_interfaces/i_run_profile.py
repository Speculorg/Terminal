from __future__ import annotations
from typing import Protocol, runtime_checkable, Mapping, Sequence, Any


@runtime_checkable
class IRunProfile(Protocol):
    """
    Спецификация тонкого сервиса для ядра.

    - stage_gates: условия завершения состояния (маркеры/пререквизиты)
    - start_cmd: команды запуска демона по режимам (http/https) или иным профилям
    """

    @property
    def stage_gates(self) -> Mapping[str, Sequence[str]]:
        """
        Ключ: имя состояния (или иного этапа), значение: список marker-имен (gates).
        Примечание: тип оставлен строковым для простоты на раннем этапе,
        в BaseFSM будет нормализация к StateEnum.
        """
        ...

    @property
    def start_cmd(self) -> Mapping[str, Sequence[str] | str | Any]:
        """
        Команды запуска демона. Минимум для TERM-1: ключи 'http' и 'https'.
        Значение: либо list[str] (argv), либо строка (shell form) — реализация нормализует.
        """
        ...
