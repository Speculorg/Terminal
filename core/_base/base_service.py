from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional, Sequence

from core._entities import HealthSnapshotType, StateEnum
from core._interfaces import IDeps, IDepsFactory, IFSM, IRunProfile, IService


class BaseService(IService):
    def __init__(self, *, run_profile: IRunProfile, deps_factory: Optional[IDepsFactory] = None) -> None:
        self._run_profile = run_profile

        if deps_factory is None:
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

    def build_fsm(self, *, deps: IDeps) -> IFSM:
        from core.fsm import FSM
        from core.fsm.daemon import DaemonRunner
        from core.fsm.policies import (
            BootstrapPolicy,
            DaemonPolicy,
            MarkerPolicy,
            RegistrarPolicy,
            RegistrarSpec,
            TlsPolicy,
        )

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
                return [x]
            return [str(x)]

        https_cmd = _norm_cmd(start_cmd_raw.get("https"))
        http_cmd = _norm_cmd(start_cmd_raw.get("http"))  # optional

        if not https_cmd:
            raise RuntimeError("run_profile.start_cmd must contain non-empty 'https' command")

        svc_name = str(getattr(deps.cfg, "service_name", "unknown"))

        run_mode_ref: dict[str, object] = {}
        marker_policy = MarkerPolicy(markers=deps.markers, stage_gates=stage_gates, run_mode_ref=run_mode_ref)

        enable_tls = bool(getattr(self._run_profile, "enable_tls", True))
        tls_bundle: list[Path] = []
        tls_policy: Optional[TlsPolicy] = None

        if enable_tls:
            certs_dir = Path(str(deps.cfg.get("FS_CERTS_DIR", "/fs/terminal/certs")))
            ca_file = certs_dir / "ca.crt"
            cert_file = certs_dir / f"{svc_name}.crt"
            key_file = certs_dir / f"{svc_name}.key"

            tls_bundle = [ca_file, cert_file, key_file]
            tls_policy = TlsPolicy(
                cfg=deps.cfg,
                log=deps.log,
                tls=deps.tls,
                ca_file=ca_file,
                cert_file=cert_file,
                key_file=key_file,
            )

        runner = DaemonRunner()
        daemon_policy = DaemonPolicy(
            cfg=deps.cfg,
            log=deps.log,
            runner=runner,
            start_cmd={"http": http_cmd, "https": https_cmd},
            run_mode_ref=run_mode_ref,
            tls=deps.tls if enable_tls else None,
            tls_bundle=tls_bundle if enable_tls else None,
        )

        bootstrap_fn = getattr(self._run_profile, "bootstrap_fn", None)
        bootstrap_done = tuple(getattr(self._run_profile, "bootstrap_done_markers", ()) or ())

        bootstrap_policy: Optional[BootstrapPolicy] = None
        if bootstrap_fn is not None and bootstrap_done:
            bootstrap_policy = BootstrapPolicy(
                markers=deps.markers,
                done_markers=bootstrap_done,
                bootstrap_fn=lambda: bootstrap_fn(cfg=deps.cfg, fs=deps.fs, markers=deps.markers, log=deps.log),
            )

        boot_policies: list[Any] = [marker_policy, daemon_policy]
        if bootstrap_policy is not None:
            boot_policies.append(bootstrap_policy)

        securing_policies: list[Any] = [marker_policy]
        if tls_policy is not None:
            securing_policies.append(tls_policy)
        securing_policies.append(daemon_policy)

        # RUNNING: добавляем tls_policy (если TLS включён), чтобы ротация была всегда активна.
        running_policies: list[Any] = []
        if tls_policy is not None:
            running_policies.append(tls_policy)
        running_policies.append(daemon_policy)

        policy_matrix: dict[StateEnum, Sequence[Any]] = {
            StateEnum.INITIALIZING: (marker_policy,),
            StateEnum.BOOTSTRAPPING: tuple(boot_policies),
            StateEnum.SECURING: tuple(securing_policies),
            StateEnum.REGISTERING: (marker_policy,),
            StateEnum.RUNNING: tuple(running_policies),
            StateEnum.STOPPING: (daemon_policy,),
        }

        if getattr(deps, "registrar", None) is not None:
            tags: tuple[str, ...] = ()
            try:
                model = getattr(deps.cfg, "_model", None)
                ctx = getattr(model, "context", None)
                tags = tuple(getattr(ctx, "tags", ()) or ())
            except Exception:
                tags = ()

            address = str(deps.cfg.get("SERVICE_ADVERTISE_HOST", svc_name))
            try:
                port = int(deps.cfg.get("SERVICE_ADVERTISE_PORT", deps.cfg.get("SERVICE_PORT", 0)) or 0)
            except Exception:
                port = 0

            ttl_sec = int(deps.cfg.get("REGISTRAR_TTL_SEC", 15) or 15)

            registrar_policy = RegistrarPolicy(
                cfg=deps.cfg,
                registrar=deps.registrar,
                markers=deps.markers,
                net=deps.net,
                log=deps.log,
                spec=RegistrarSpec(
                    service=svc_name,
                    address=address,
                    port=int(port),
                    tags=tags,
                    ttl_seconds=ttl_sec,
                ),
            )

            policy_matrix[StateEnum.REGISTERING] = (marker_policy, registrar_policy)

            running2: list[Any] = []
            if tls_policy is not None:
                running2.append(tls_policy)
            running2.append(registrar_policy)
            running2.append(daemon_policy)
            policy_matrix[StateEnum.RUNNING] = tuple(running2)

        return FSM(
            cfg=deps.cfg,
            log=deps.log,
            markers=deps.markers,
            service_name=svc_name,
            policy_matrix=policy_matrix,  # type: ignore[arg-type]
        )

    def run(self) -> None:
        if self._started:
            raise RuntimeError("service.run() must be called only once")
        self._started = True

        deps = self._deps_factory.build()
        self._deps = deps

        try:
            svc_name = str(getattr(deps.cfg, "service_name", "unknown"))
            deps.markers.delete(f"{svc_name}_ready")
        except Exception:
            pass

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