from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from core._entities import HealthSnapshotType, StateEnum
from core._interfaces import IDeps, IDepsFactory, IFSM, IRunProfile, IService


class BaseService(IService):
    """
    Тонкий каркас сервиса.

    Цель:
    - Тонкий сервис предоставляет только RunProfile (stage_gates + start_cmd + bootstrap hooks).
    - Вся сборка Deps и FSM по умолчанию происходит в ядре.

    Инварианты:
    - __init__ ничего не запускает
    - run() можно вызвать только один раз (entrypoint)
    - IDeps.close() вызывается гарантированно в finally
    - FSM создаётся отдельно и НЕ входит в Deps
    """

    def __init__(self, *, run_profile: IRunProfile, deps_factory: Optional[IDepsFactory] = None) -> None:
        self._run_profile = run_profile

        if deps_factory is None:
            # lazy import: избегаем циклов
            from core.deps import DepsFactory  # noqa: WPS433

            deps_factory = DepsFactory()

        self._deps_factory = deps_factory

        self._deps: Optional[IDeps] = None
        self._fsm: Optional[IFSM] = None

        self._started = False
        self._snapshot: HealthSnapshotType = {}

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    # --- hooks for concrete services (override only if really needed) ---

    def build_fsm(self, *, deps: IDeps) -> IFSM:
        """
        Default FSM builder (TERM-1).

        Источники:
        - self._run_profile.stage_gates: Mapping[str, Sequence[str]]
        - self._run_profile.start_cmd: Mapping[str, Sequence[str] | str | Any]
        - optional (duck-typing):
            - bootstrap_fn(cfg, fs, markers, log)
            - bootstrap_done_markers: Sequence[str]
            - enable_tls: bool (default True)

        Конкретные сервисы могут переопределить build_fsm(), но это должно быть исключением.
        """
        from core.fsm import FSM
        from core.fsm.daemon import DaemonRunner
        from core.fsm.policies import BootstrapPolicy, DaemonPolicy, TlsPolicy

        stage_gates_raw = getattr(self._run_profile, "stage_gates", {}) or {}
        start_cmd_raw = getattr(self._run_profile, "start_cmd", {}) or {}

        stage_gates: dict[StateEnum, tuple[str, ...]] = {}
        for k, v in dict(stage_gates_raw).items():
            try:
                st = StateEnum[str(k)]
            except Exception:
                continue
            stage_gates[st] = tuple(v or ())

        def _norm_cmd(x: Any) -> list[str]:
            if x is None:
                return []
            if isinstance(x, (list, tuple)):
                return [str(i) for i in x]
            if isinstance(x, str):
                # shell-form не поддерживаем на TERM-1 (детерминизм). Можно добавить позже.
                return [x]
            return [str(x)]

        http_cmd = _norm_cmd(start_cmd_raw.get("http"))
        https_cmd = _norm_cmd(start_cmd_raw.get("https"))
        if not http_cmd or not https_cmd:
            raise RuntimeError("run_profile.start_cmd must contain 'http' and 'https' commands")

        svc_name = str(getattr(deps.cfg, "service_name", "unknown"))

        runner = DaemonRunner()

        daemon_policy = DaemonPolicy(
            runner=runner,
            markers=deps.markers,
            start_cmd={"http": http_cmd, "https": https_cmd},
        )

        bootstrap_fn = getattr(self._run_profile, "bootstrap_fn", None)
        bootstrap_done = tuple(getattr(self._run_profile, "bootstrap_done_markers", ()) or ())

        boot_policies = [daemon_policy]
        if bootstrap_fn is not None and bootstrap_done:
            boot_policies.append(
                BootstrapPolicy(
                    markers=deps.markers,
                    done_markers=bootstrap_done,
                    bootstrap_fn=lambda: bootstrap_fn(cfg=deps.cfg, fs=deps.fs, markers=deps.markers, log=deps.log),
                )
            )

        enable_tls = bool(getattr(self._run_profile, "enable_tls", True))

        policy_matrix: dict[StateEnum, Sequence[Any]] = {
            StateEnum.INITIALIZING: (daemon_policy,),
            StateEnum.BOOTSTRAPPING: tuple(boot_policies),
            StateEnum.RUNNING: (daemon_policy,),
            StateEnum.STOPPING: (daemon_policy,),
        }

        if enable_tls:
            certs_dir = Path(str(getattr(deps.cfg, "fs_certs_dir", deps.cfg.get("FS_CERTS_DIR", "/fs/terminal/certs"))))
            ca_file = certs_dir / "ca.crt"
            cert_file = certs_dir / f"{svc_name}.crt"
            key_file = certs_dir / f"{svc_name}.key"

            tls_policy = TlsPolicy(
                tls=deps.tls,
                ca_file=ca_file,
                cert_file=cert_file,
                key_file=key_file,
                bundle=None,
            )
            policy_matrix[StateEnum.SECURING] = (tls_policy, daemon_policy)
        else:
            policy_matrix[StateEnum.SECURING] = (daemon_policy,)

        return FSM(
            cfg=deps.cfg,
            log=deps.log,
            markers=deps.markers,
            service_name=svc_name,
            stage_gates=stage_gates,
            policy_matrix=policy_matrix,  # type: ignore[arg-type]
        )

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
