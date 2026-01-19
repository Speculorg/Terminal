from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True, slots=True)
class DaemonSpec:
    """
    Спецификация запуска демона.

    cmd:
      - argv-форма (preferred): ["consul", "agent", "-config-file=/..."]
    env:
      - дополнения к текущему окружению процесса
    cwd:
      - рабочий каталог (обычно не нужен)
    """
    cmd: Sequence[str]
    env: Optional[dict[str, str]] = None
    cwd: Optional[str] = None


class DaemonRunner:
    """
    Управление процессом демона внутри контейнера.

    Инварианты:
    - один runner управляет максимум одним активным процессом
    - start/stop/restart идемпотентны по смыслу (не валят процесс на повторном вызове)
    - runner НЕ решает "готов ли демон": это ответственность политик/Net checks
    """

    def __init__(self) -> None:
        self._p: Optional[subprocess.Popen] = None

    def is_alive(self) -> bool:
        return self._p is not None and self._p.poll() is None

    def pid(self) -> Optional[int]:
        if self._p is None:
            return None
        return self._p.pid

    def start(self, *, spec: DaemonSpec) -> None:
        if self.is_alive():
            return

        env = os.environ.copy()
        if spec.env:
            env.update({str(k): str(v) for k, v in spec.env.items()})

        # stdout/stderr по умолчанию наследуем (контейнерный лог), не буферизуем
        self._p = subprocess.Popen(
            list(spec.cmd),
            env=env,
            cwd=spec.cwd,
            stdout=None,
            stderr=None,
        )

    def signal(self, sig: int) -> None:
        if not self.is_alive():
            return
        try:
            os.kill(int(self._p.pid), sig)
        except Exception:
            pass

    def stop(self, *, timeout_ms: int = 5000, sig: int = signal.SIGTERM) -> None:
        if not self.is_alive():
            self._p = None
            return

        self.signal(sig)

        deadline = time.monotonic() + max(0, int(timeout_ms)) / 1000.0
        while time.monotonic() <= deadline:
            if not self.is_alive():
                self._p = None
                return
            time.sleep(0.05)

        # жёсткое добивание
        self.signal(signal.SIGKILL)
        time.sleep(0.05)
        self._p = None

    def restart(self, *, spec: DaemonSpec, stop_timeout_ms: int = 5000) -> None:
        self.stop(timeout_ms=stop_timeout_ms)
        self.start(spec=spec)
