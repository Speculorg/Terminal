from __future__ import annotations
from typing import Optional
import time
import subprocess
import signal

from .base_deps import BaseDeps, BaseDepsFactory
from .base_health import BaseHealth

from interfaces import IService, IRunProfile
from entities import HealthStatusEnum, StateEnum

from core.policies import FSMPolicy, TLSPolicy, DaemonPolicy


class BaseService(IService):
    """Каркас сервиса. Принимает профиль запуска из main.py."""
    def __init__(self, run_profile: Optional[IRunProfile] = None) -> None:
        deps = BaseDepsFactory.build()
        self._deps = deps
        self.run_profile: Optional[IRunProfile] = run_profile
        self._cfg = deps.cfg
        self._logger = deps.logger
        self._fs = deps.fs
        self._markers = deps.markers
        self._net = deps.net
        self._registrar = deps.registrar
        self._metrics = deps.metrics
        self._fsm = deps.fsm
        self._health = BaseHealth()
        self.initialize()


    # Жизненный цикл
    def initialize(self) -> None:
        self._logger.info("service.initialize", svc=self._cfg.context.name)
        self.start()

    def _resolve_port(self, mode: str) -> int:
        name = self._cfg.context.name
        try:
            if name == "consul":
                return int(self._cfg.consul.http_port if mode=="http" else self._cfg.consul.https_port)
            if name == "vault":
                return int(self._cfg.vault.http_port if mode=="http" else self._cfg.vault.https_port)
            return int(self._cfg.context.port)
        except Exception:
            return int(self._cfg.context.port)

    def start(self) -> None:
        if not self.run_profile:
            self._logger.error("service.start.no_profile", svc=self._cfg.context.name, details={} )
            return

        # Проверка обязательных маркеров сервиса
        ok, missing = self._markers.require(self.run_profile.required_markers, self._cfg.context.name) if getattr(self.run_profile, "required_markers", None) else (True, set())
        if not ok:
            self._logger.error("service.start.precondition", svc=self._cfg.context.name, details={"missing": sorted(list(missing))} )
            return


        # Подготовка контекста FSM
        try:
            if hasattr(self, "_fsm"):
                self._fsm.svc = self._cfg.context.name
                rm = getattr(self.run_profile, "required_markers", None) or set()
                sg = getattr(self.run_profile, "stage_gates", None) or {}
                sg_pairs = { st: [(self._cfg.context.name, m) for m in sorted(list(names))] for st, names in sg.items() }
                self._fsm.required_markers = set(rm)
                self._fsm.stage_gates = sg_pairs  # type: ignore
        except Exception:
            pass
        # Запуск FSM отложен до реализации демонов. Пока — публикация health.
        self._health.status = HealthStatusEnum.PASSING
        self._health.heartbeat_ts = int(time.time())
        
        # План старта демона по профилю
        self._logger.info("service.start", svc=self._cfg.context.name, details={"port": self._cfg.context.port} )
        def _sigterm_handler(signum, frame):
            try:
                self._logger.info("service.sigterm", svc=self._cfg.context.name, details={} )
                if getattr(self, "_daemon_proc", None):
                    self._daemon_proc.terminate()
                    try:
                        self._daemon_proc.wait(timeout=5)
                    except Exception:
                        pass
            finally:
                raise SystemExit(0)
        signal.signal(signal.SIGTERM, _sigterm_handler)
        try:
            start_cmd_map = getattr(self.run_profile, "start_cmd", None)
            if start_cmd_map:
                # diag: log which SECURING gates are required and missing
                try:
                    gates = getattr(self.run_profile, "stage_gates", {}) or {}
                    required = set(gates.get(StateEnum.SECURING, set()))
                    missing = sorted([m for m in required if not self._markers.exists(m)])
                    self._logger.info("tls.gates", svc=self._cfg.context.name, details={"required": sorted(list(required)), "missing": missing})
                except Exception:
                    pass
                mode = TLSPolicy.decide_initial_mode(self._markers, self.run_profile)
                cmd = DaemonPolicy.build_start_cmd(self.run_profile, mode)
                self._logger.info("daemon.plan.start", svc=self._cfg.context.name, details={"mode": mode, "cmd": cmd})
                self._daemon_proc = subprocess.Popen(cmd)
                self._logger.info("daemon.start", svc=self._cfg.context.name, details={"pid": self._daemon_proc.pid, "mode": mode} )
                try:
                    port = self._resolve_port(mode)
                    self._net.wait_port("127.0.0.1", int(port), timeout_ms=self._cfg.fsm.state_initializing_timeout_ms)
                    self._logger.info("daemon.ready", svc=self._cfg.context.name, details={"port": int(port), "mode": mode})
                except Exception as e:
                    self._logger.warn("daemon.wait_port.failed", svc=self._cfg.context.name, details={"error": str(e)})
                
                # TLS transition: if started in http and SECURING gates become ready -> restart in https
                try:
                    gates = getattr(self.run_profile, "stage_gates", {}) or {}
                    required = set(gates.get(StateEnum.SECURING, set()))
                    if mode == "http" and required:
                        deadline = time.time() + (self._cfg.fsm.state_tls_transition_timeout_ms / 1000.0)
                        poll = max(0.1, self._cfg.tls.watch_poll_ms / 1000.0)
                        while time.time() < deadline:
                            missing = [m for m in required if not self._markers.exists(m)]
                            if not missing:
                                self._logger.info("tls.transition.trigger", svc=self._cfg.context.name, details={"from": "http", "to": "https"})
                                try:
                                    self._daemon_proc.terminate()
                                    try:
                                        self._daemon_proc.wait(timeout=5)
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                                mode = "https"
                                cmd = DaemonPolicy.build_start_cmd(self.run_profile, mode)
                                self._logger.info("daemon.plan.start", svc=self._cfg.context.name, details={"mode": mode, "cmd": cmd})
                                self._daemon_proc = subprocess.Popen(cmd)
                                self._logger.info("daemon.start", svc=self._cfg.context.name, details={"pid": self._daemon_proc.pid, "mode": mode})
                                try:
                                    port = self._resolve_port(mode)
                                    self._net.wait_port("127.0.0.1", int(port), timeout_ms=self._cfg.fsm.state_initializing_timeout_ms)
                                    self._logger.info("daemon.ready", svc=self._cfg.context.name, details={"port": int(port), "mode": mode})
                                except Exception as e:
                                    self._logger.warn("daemon.wait_port.failed", svc=self._cfg.context.name, details={"error": str(e)})
                                break
                            time.sleep(poll)
                        else:
                            self._logger.info("tls.transition.skip_timeout", svc=self._cfg.context.name, details={"required": sorted(list(required))})
                except Exception as e:
                    self._logger.warn("tls.transition.error", svc=self._cfg.context.name, details={"error": str(e)})
                try:
                # делегируем политику TLS для переключения
                    self._fsm.configure_tls(self.run_profile, self._net, self._restart_to_mode, self._resolve_port, mode)
                    self._fsm.on_enter(StateEnum.TLS_TRANSITION)
                # FSM consumed: self._cfg, self._logger, self._markers, self._net, self.run_profile, mode, self._restart_to_mode, self._resolve_port)
                except Exception:
                    pass
                rc = self._daemon_proc.wait()
                self._logger.error("daemon.exit", svc=self._cfg.context.name, details={"returncode": rc})
                return
        except Exception as e:
            self._logger.error("daemon.plan.error", svc=self._cfg.context.name, details={"error": str(e)})

    def _restart_to_mode(self, mode: str) -> None:
        """Аккуратно останавливает текущий процесс и запускает демон в указанном режиме."""
        try:
            # остановка текущего процесса если есть
            if getattr(self, "_daemon_proc", None):
                try:
                    self._daemon_proc.terminate()  # type: ignore
                    self._daemon_proc.wait(timeout=5)  # type: ignore
                except Exception:
                    try:
                        self._daemon_proc.kill()  # type: ignore
                    except Exception:
                        pass
            # запуск в целевом режиме
            cmd = DaemonPolicy.build_start_cmd(self.run_profile, mode)  # type: ignore
            self._logger.info("daemon.plan.start", svc=self._cfg.context.name, details={"mode": mode, "cmd": cmd} )
            self._daemon_proc = __import__("subprocess").Popen(cmd)  # type: ignore
            self._logger.info("daemon.start", svc=self._cfg.context.name, details={"pid": int(self._daemon_proc.pid)} )
        except Exception as e:
            self._logger.error("daemon.plan.error", svc=self._cfg.context.name, details={"error": str(e)})
        
    def stop(self) -> None:
        try:
            # дерегистрация если есть
            if self._registrar:
                self._registrar.deregister(self._cfg.context.name)  # type: ignore
        except Exception as e:
            pass
            self._logger.error("service.start.no_profile", svc=self._cfg.context.name, details={} )
        self._logger.info("service.stop", svc=self._cfg.context.name, details={} )
