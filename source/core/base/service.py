# source/core/base/service.py

"""
Speculorg.Terminal.Core.Base.ContextMicroservice
- Контракт жизненного цикла микросервиса.
- Делегирует инфраструктуру в подсистемы.
"""

from __future__ import annotations
import asyncio
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.settings.settings import SETTINGS, CONFIG_HASH
from core.runtime.status import ServiceStatus, HealthSnapshot
from core.runtime.health_io import write_health
from core.runtime.lifecycle import install_signal_shutdown_flag, Periodic
from core.logging import get_logger
from core.metrics.registry import registry as metrics_registry
from core.metrics.registry import Counter, Gauge, Registry
from core.infra.registrars.base import Registrar
from core.infra.registrars.consul import ConsulRegistrar
from core.net.url import build_url, fqdn

# KV фасад (агрегат)
try:
    from core.kv import KV  # type: ignore
except Exception:  # pragma: no cover
    KV = None  # type: ignore[misc]


# ----------------------------- Dependencies (DIP) -----------------------------

@dataclass(slots=True)
class ContextMicroserviceDeps:
    registrar: Optional[Registrar] = None
    health_file: Path = Path(SETTINGS.context.health_file)
    metrics: Registry = metrics_registry()
    kv: Optional[KV] = None  # type: ignore


# ----------------------------- ContextMicroservice -----------------------------

class ContextMicroservice:
    """
    Контракт базового микросервиса:
      initialize()  -> идемпотентная подготовка среды/зависимостей/конфигураций
      start()       -> запуск основной работы (долгоживущий цикл)
      pause()       -> пауза обработки
      restart()     -> управляемый рестарт
      stop()        -> корректная остановка
    """

    write_health_every_sec: float = 5.0
    update_metrics_every_sec: float = 15.0

    def __init__(self, deps: Optional[ContextMicroserviceDeps] = None) -> None:
        self.deps = deps or ContextMicroserviceDeps()

        # Паспорт сервиса - из SETTINGS.context
        self._svc_name: str = SETTINGS.context.name
        self._svc_port: int = SETTINGS.context.port
        self._svc_tags: list[str] = list(SETTINGS.context.tags)

        # По умолчанию подключаем регистратора
        if self.deps.registrar is None and self._svc_name not in {"consul", "vault"}:
            self.deps.registrar = ConsulRegistrar(
                service_id=self._svc_name or "service",
                name=self._svc_name or "service",
                port=self._svc_port,
                tags=list(self._svc_tags),
            )

        self.log = get_logger(self._svc_name)
        self._shutdown = asyncio.Event()
        self._status: ServiceStatus = ServiceStatus.BOOTSTRAPPING
        self._health = HealthSnapshot()
        self._tls_active: bool = False
        self._child = None  # subprocess.Popen | None

        # Метрики
        self._mx: Registry = self.deps.metrics
        self._m_status_changes: Counter = self._mx.counter("svc_status_changes_total", "Service status transitions")
        self._m_errors_total:   Counter = self._mx.counter("svc_errors_total", "Unhandled errors")
        self._m_restarts_total: Counter = self._mx.counter("svc_restart_requests_total", "Requested restarts")
        self._g_uptime_seconds: Gauge   = self._mx.gauge("svc_uptime_seconds", "Service uptime in seconds")
        self._g_tls_active:     Gauge   = self._mx.gauge("svc_tls_active", "TLS active flag (0/1)")

        # Периодические фоновые задачи
        self._tick_health = Periodic(self.write_health_every_sec, self._write_health_tick)
        self._tick_metrics = Periodic(self.update_metrics_every_sec, self._update_metrics_tick)

    # ----------------------------- Переопределяемые хуки -----------------------------

    async def initialize(self) -> None:
        return

    async def start(self) -> None:
        while not self._shutdown.is_set():
            await asyncio.sleep(1.0)

    async def pause(self) -> None:
        self._set_status(ServiceStatus.PAUSED, "pause")

    async def restart(self) -> None:
        self._m_restarts_total.inc(labels={"svc": self._svc_name})
        self._set_status(ServiceStatus.TLS_TRANSITION, "restart requested")
        # управляемый рестарт контейнера
        import os
        os._exit(95)  # noqa: PLW1510

    async def stop(self) -> None:
        self._set_status(ServiceStatus.STOPPING, "stop requested")
        self._shutdown.set()

    # ----------------------------- Оркестратор -----------------------------

    async def serve(self) -> None:
        install_signal_shutdown_flag(self._shutdown, on_signal=self._on_signal)

        try:
            # BOOTSTRAP
            self._set_status(ServiceStatus.BOOTSTRAPPING, "entry")
            self._tick_health.start()
            self._tick_metrics.start()

            # Публикация CONFIG_HASH/DOMAIN_ROOT в KV (идемпотентно)
            self._publish_config_hash_once()

            # INIT
            self._set_status(ServiceStatus.INITIALIZING, "initialize()")
            await self.initialize()

            # REGISTER
            self._set_status(ServiceStatus.REGISTERING, "registrar.register()")
            if self.deps.registrar:
                await self.deps.registrar.register()

            # RUN
            self._set_status(ServiceStatus.RUNNING, "start()")
            await self.start()

        except Exception as exc:  # noqa: BLE001
            self._m_errors_total.inc(labels={"svc": self._svc_name})
            self._set_status(ServiceStatus.ERROR, f"fatal:{type(exc).__name__}")
            self.log.exception("err=unhandled")
            raise
        finally:
            try:
                if self.deps.registrar:
                    await self.deps.registrar.deregister()
            except Exception as exc:  # noqa: BLE001
                self.log.warning("registrar.deregister.failed", err=exc)
            await self._before_stop()
            await self._write_health_tick()
            await self._tick_health.stop()
            await self._tick_metrics.stop()
            self.log.info("stopped")

    # ----------------------------- Health / Status -----------------------------

    def _set_status(self, st: ServiceStatus, *reasons: str) -> None:
        prev = self._status
        self._status = st
        h = self._health
        h.status = st
        h.phase = st.value
        h.state = (
            "up" if st is ServiceStatus.RUNNING else
            "degraded" if st is ServiceStatus.DEGRADED else
            "init" if st in {
                ServiceStatus.BOOTSTRAPPING, ServiceStatus.INITIALIZING,
                ServiceStatus.SECURING, ServiceStatus.TLS_TRANSITION, ServiceStatus.REGISTERING
            } else "down"
        )
        if reasons:
            h.reasons = tuple(reasons)
        self._m_status_changes.inc(labels={
            "svc": self._svc_name,
            "from": prev.value if hasattr(prev, "value") else str(prev),
            "to": st.value,
        })
        self.log.info(
            "evt=status.change",
            st=st.value,
            prev=getattr(prev, "value", str(prev)),
            tls=1 if self._tls_active else 0,
            reason=";".join(reasons) if reasons else "-",
        )

        # Отразить фазу/статус в KV (идемпотентно через CAS)
        kv = getattr(self.deps, "kv", None)
        if kv is not None:
            try:
                kv.status.set_phase(self._svc_name, st.value, meta={"reasons": list(reasons) if reasons else []})
                kv.status.set_status(self._svc_name, st)
            except Exception as exc:  # noqa: BLE001
                # только лог, не валим сервис при временных KV проблемах
                self.log.warning("evt=kv.status.update.fail", err=exc)

    def svc_health_snapshot(self) -> dict:
        snap = self._health.to_dict()
        snap.update({
            "service": self._svc_name,
            "domain": SETTINGS.domain.root,
            "tls_active": self._tls_active,
        })
        return snap

    async def _write_health_tick(self) -> None:
        try:
            write_health(self.svc_health_snapshot(), self.deps.health_file)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=health.write.fail", err=exc)

        # Параллельно - heartbeat в KV
        kv = getattr(self.deps, "kv", None)
        if kv is not None:
            try:
                kv.status.heartbeat(self._svc_name, tls_active=self._tls_active)
            except Exception as exc:  # noqa: BLE001
                self.log.warning("evt=kv.heartbeat.fail", err=exc)

    # ----------------------------- TLS / URL helpers -----------------------------

    def svc_set_tls_active(self, active: bool) -> None:
        self._tls_active = bool(active)
        self._g_tls_active.set(1.0 if self._tls_active else 0.0, labels={"svc": self._svc_name})
        self.log.info("evt=tls.state", active=1 if active else 0)

        # Ради полноты - быстрый heartbeat в KV при смене TLS
        kv = getattr(self.deps, "kv", None)
        if kv is not None:
            try:
                kv.status.heartbeat(self._svc_name, tls_active=self._tls_active, meta={"evt": "tls_active_changed"})
            except Exception as exc:  # noqa: BLE001
                self.log.warning("evt=kv.heartbeat.fail", err=exc)

    def svc_url(self, host: str, port_http: int, port_https: int, path: str = "") -> str:
        return build_url(host, port_http, port_https, path, tls=self._tls_active)

    def svc_fqdn(self, name: str) -> str:
        return fqdn(name, SETTINGS.domain.root)

    # ----------------------------- Metrics helpers -----------------------------

    async def _update_metrics_tick(self) -> None:
        self._g_uptime_seconds.set(self._uptime_seconds(), labels={"svc": self._svc_name})

    def metrics_text(self) -> str:
        return self._mx.render_prometheus()

    # ----------------------------- Shutdown / Signals -----------------------------

    def _on_signal(self, sig: signal.Signals) -> None:
        self.log.info("evt=signal", sig=sig.name)

    async def _before_stop(self) -> None:
        self._set_status(ServiceStatus.STOPPING, "shutdown")
        if self._child and self._child.poll() is None:
            self.log.info("evt=child.terminate")
            try:
                self._child.terminate()
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._child.wait, 10)
            except Exception:
                self.log.warning("evt=child.kill")
                try:
                    self._child.kill()
                except Exception:
                    pass

    def proc_attach(self, popen) -> None:
        self._child = popen

    # ----------------------------- Internals -----------------------------

    def _uptime_seconds(self) -> float:
        return max(0.0, time.time() - float(self._health.started_at or time.time()))

    def _publish_config_hash_once(self) -> None:
        """
        Идемпотентно публикует текущий CONFIG_HASH и DOMAIN_ROOT в KV.
        Используется на старте, до initialize().
        """
        kv = getattr(self.deps, "kv", None)
        if kv is None:
            return
        try:
            # config/global/config_hash
            if not kv.config.set_config_hash(CONFIG_HASH):
                self.log.warning("evt=kv.config_hash.write.false")
            # config/global/domain_root (подтверждение домена)
            if not kv.config.set_domain_root(SETTINGS.domain.root):
                self.log.warning("evt=kv.domain_root.write.false")
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=kv.publish_config.fail", err=exc)
