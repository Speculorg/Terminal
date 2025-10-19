from __future__ import annotations
from dataclasses import dataclass
from entities.run_mode_enum import RunModeEnum
from entities.state_enum import StateEnum

@dataclass
class FSMPolicy:
    cfg: object

    # STARTING -> BOOTSTRAPPING gate
    def check_prereq(self) -> bool:
        # Простая проверка окружения без сетевых проб
        return True

    # BOOTSTRAPPING transitions by run_mode
    def first_run(self) -> StateEnum:
        return StateEnum.INITIALIZING

    def recovery_run(self) -> StateEnum:
        return StateEnum.INITIALIZING

    def normal_run(self) -> StateEnum:
        return StateEnum.SECURING

    # INITIALIZING -> SECURING gate when one-shot ops done
    def bootstrap_gate(self) -> StateEnum:
        return StateEnum.SECURING

    # TLS_TRANSITION handler
    def switch_https(self) -> StateEnum:
        return StateEnum.REGISTERING

    # REGISTERING -> RUNNING gate
    def on_register_ok(self) -> StateEnum:
        return StateEnum.RUNNING

    # Error handling
    def on_error(self, current: StateEnum) -> StateEnum:
        return StateEnum.DEGRADED

    def on_fail(self, current: StateEnum) -> StateEnum:
        return StateEnum.ERROR

    # RUNNING tick
    def on_tick(self) -> StateEnum:
        return StateEnum.RUNNING

    # Pause/Resume/Stop
    def pause(self) -> StateEnum:
        return StateEnum.PAUSED

    def resume(self) -> StateEnum:
        return StateEnum.RUNNING

    def stop(self) -> StateEnum:
        return StateEnum.STOPPING

    # Restart gate
    def restart_gate(self) -> StateEnum:
        return StateEnum.STARTING
