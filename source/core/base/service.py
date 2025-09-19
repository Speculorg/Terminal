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
from typing import Optional, Set

from core.settings.settings import SETTINGS, CONFIG_HASH
from core.runtime.status import ServiceStatus, HealthSnapshot
from core.runtime.health_io import write_health
from core.runtime.lifecycle import install_signal_shutdown_flag, Periodic
from core.runtime.tls.tls_reload import TLSReloader
from core.logging import get_logger
from core.metrics.registry import registry as metrics_registry
from core.metrics.registry import Counter, Gauge, Registry
from core.infra.registrars.base import Registrar
from core.infra.registrars.consul import ConsulRegistrar
from core.net import build_url, fqdn

# KV фасад (агрегат)
try:
    from core.kv import KV  # type: ignore
    from core.kv import paths as kv_paths  # для чтения версий/маркеров
except Exception:  # pragma: no cover
    KV = None  # type: ignore[misc]
    kv_paths = None  # type: ignore[misc]


# ----------------------------- Dependencies (DIP) -----------------------------

@dataclass(slots=True)
class ContextMicroserviceDeps:
    registrar: Optional[Registrar] = None
    health_file: Path = Path(SETTINGS.context.health_file)
    metrics: Registry = metrics_registry()
    kv: Optional[KV] = None  # type: ignore
    tls_reloader: Optional[TLSReloader] = None


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
    tls_watch_every_sec: float = 10.0  # период опроса версии TLS-бандла

    # Минимальный gate «TLS должен быть активен, прежде чем перейти в RUNNING»
    # Сервисы могут выставить True, если для них это критично.
    require_tls_for_running: bool = False

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

        # ----------------------------- Метрики (минимальный стандарт) -----------------------------
        self._mx: Registry = self.deps.metrics
        # Служебные/общие:
        self._m_status_changes: Counter = self._mx.counter("svc_status_changes_total", "Service status transitions")
        self._m_errors_total:   Counter = self._mx.counter("svc_errors_total", "Unhandled errors")
        self._m_restarts_total: Counter = self._mx.counter("svc_restart_requests_total", "Requested restarts")
        self._g_uptime_seconds: Gauge   = self._mx.gauge("svc_uptime_seconds", "Service uptime in seconds")
        self._g_tls_active:     Gauge   = self._mx.gauge("svc_tls_active", "TLS active flag (0/1)")
        # KV / Registrar / TLS-watch:
        self._m_kv_status_update_fail: Counter = self._mx.counter("kv_status_update_fail_total", "KV status update failures")
        self._m_kv_heartbeat_fail:     Counter = self._mx.counter("kv_heartbeat_fail_total", "KV heartbeat write failures")
        self._m_reg_deregister_fail:    Counter = self._mx.counter("registrar_deregister_fail_total", "Registrar deregister failures")
        self._m_tls_version_changes:    Counter = self._mx.counter("tls_version_changes_total", "TLS bundle version changes detected")
        self._m_tls_reload_requests:    Counter = self._mx.counter("tls_reload_requests_total", "TLS hot-reload requests issued")
        self._m_tls_reload_fail:        Counter = self._mx.counter("tls_reload_fail_total", "TLS hot-reload failures")

        # Периодические фоновые задачи
        self._tick_health = Periodic(self.write_health_every_sec, self._write_health_tick)
        self._tick_metrics = Periodic(self.update_metrics_every_sec, self._update_metrics_tick)
        self._tick_tls_watch = Periodic(self.tls_watch_every_sec, self._tls_watch_tick)

        # Версия TLS-бандла, известная сервису (для детекта смены)
        self._last_cert_version: Optional[str] = None

        # Причины деградации (агрегируются, снимаются по recover())
        self._degraded_reasons: Set[str] = set()

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

    def _kv_required(self) -> bool:
        # consul/vault/traefik могут стартовать без внешнего KV (ленивое подключение в initialize())
        return self._svc_name not in {"consul", "vault", "traefik"}

    async def serve(self) -> None:
        install_signal_shutdown_flag(self._shutdown, on_signal=self._on_signal)

        try:
            # BOOTSTRAP
            self._set_status(ServiceStatus.BOOTSTRAPPING, "entry")
            self._tick_health.start()
            self._tick_metrics.start()
            self._tick_tls_watch.start()

            # Публикация CONFIG_HASH/DOMAIN_ROOT в KV (идемпотентно, если KV есть уже сейчас)
            self._publish_config_hash_once()

            # INIT (ленивое подключение зависимостей делается внутри initialize())
            self._set_status(ServiceStatus.INITIALIZING, "initialize()")
            await self.initialize()
            # Если для сервиса KV обязателен, но после initialize() его всё ещё нет — это ошибка конфигурации
            if self._kv_required() and getattr(self.deps, "kv", None) is None:
                self.log.error("evt=deps.kv.missing.post_init", svc=self._svc_name)
                raise RuntimeError(
                    "KV dependency is required after initialize() for this service "
                    "(inject via ContextMicroserviceDeps.kv or attach during initialize())"
                )

            # Маркер инициализации сервиса
            self._ensure_marker("initialized")

            # REGISTER
            self._set_status(ServiceStatus.REGISTERING, "registrar.register()")
            if self.deps.registrar:
                await self.deps.registrar.register()
            # Маркер регистрации сервиса
            self._ensure_marker("registered")

            # READY-GATE (опционально ждём TLS)
            await self._ready_gate()

            # RUN
            # Если есть активные причины деградации — остаёмся в DEGRADED.
            if self._degraded_reasons:
                self._set_status(ServiceStatus.DEGRADED, "degraded:on_enter_run")
            else:
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
                self._m_reg_deregister_fail.inc(labels={"svc": self._svc_name})
                self.log.warning("evt=registrar.deregister.failed", svc=self._svc_name, err=exc)
            await self._before_stop()
            await self._write_health_tick()
            await self._tick_health.stop()
            await self._tick_metrics.stop()
            await self._tick_tls_watch.stop()
            self.log.info("evt=stopped", svc=self._svc_name)

    async def _ready_gate(self) -> None:
        """
        Минимальный gate перед RUNNING.
        По умолчанию: если require_tls_for_running=True, ждём активный TLS ограниченное время.
        Сервисы могут переопределить метод и добавить свои проверки.
        """
        timeout = float(SETTINGS.timeouts.init_timeout_s)
        if self.require_tls_for_running and not self._tls_active:
            self._set_status(ServiceStatus.SECURING, "ready_gate.wait_tls")
            deadline = time.time() + max(1.0, timeout)
            while time.time() < deadline and not self._tls_active and not self._shutdown.is_set():
                await asyncio.sleep(0.5)
            # не блокируем переход — просто зафиксируем состояние, если TLS так и не активировался
            if not self._tls_active:
                self.log.warning("evt=ready_gate.tls.not_active", svc=self._svc_name)

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
            svc=self._svc_name,
            phase=st.value,
            st=st.value,
            prev=getattr(prev, "value", str(prev)),
            tls=1 if self._tls_active else 0,
            reason=";".join(reasons) if reasons else "-",
        )

        # ЕДИНАЯ точка записи статуса/фазы в KV
        kv = getattr(self.deps, "kv", None)
        if kv is not None:
            try:
                kv.status.update(self._svc_name, st, meta={
                    "reasons": list(reasons) if reasons else [],
                    "degraded": sorted(self._degraded_reasons),
                })
            except Exception as exc:  # noqa: BLE001
                self._m_kv_status_update_fail.inc(labels={"svc": self._svc_name})
                self.log.warning("evt=kv.status.update.fail", svc=self._svc_name, phase=st.value, err=exc)

    def svc_health_snapshot(self) -> dict:
        snap = self._health.to_dict()
        snap.update({
            "service": self._svc_name,
            "domain": SETTINGS.domain.root,
            "tls_active": self._tls_active,
            "degraded_reasons": sorted(self._degraded_reasons),
        })
        return snap

    async def _write_health_tick(self) -> None:
        try:
            write_health(self.svc_health_snapshot(), self.deps.health_file)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=health.write.fail", svc=self._svc_name, err=exc)

        # Параллельно - heartbeat в KV
        kv = getattr(self.deps, "kv", None)
        if kv is not None:
            try:
                kv.status.heartbeat(self._svc_name, tls_active=self._tls_active, meta={
                    "degraded": sorted(self._degraded_reasons)
                })
            except Exception as exc:  # noqa: BLE001
                self._m_kv_heartbeat_fail.inc(labels={"svc": self._svc_name})
                self.log.warning("evt=kv.heartbeat.fail", svc=self._svc_name, err=exc)

    # ----------------------------- TLS / URL helpers -----------------------------

    def svc_set_tls_active(self, active: bool) -> None:
        self._tls_active = bool(active)
        self._g_tls_active.set(1.0 if self._tls_active else 0.0, labels={"svc": self._svc_name})
        self.log.info("evt=tls.state", svc=self._svc_name, active=1 if active else 0, phase=self._status.value)

        # Быстрый heartbeat + маркер mTLS
        kv = getattr(self.deps, "kv", None)
        if kv is not None:
            try:
                kv.status.heartbeat(self._svc_name, tls_active=self._tls_active, meta={"evt": "tls_active_changed"})
            except Exception as exc:  # noqa: BLE001
                self._m_kv_heartbeat_fail.inc(labels={"svc": self._svc_name})
                self.log.warning("evt=kv.heartbeat.fail", svc=self._svc_name, err=exc)
            if self._tls_active:
                self._ensure_marker("mtls_ready")

    def svc_url(self, host: str, port_http: int, port_https: int, path: str = "") -> str:
        return build_url(host, port_http, port_https, path, tls=self._tls_active)

    def svc_fqdn(self, name: str) -> str:
        return fqdn(name, SETTINGS.domain.root)

    # ----------------------------- Metrics helpers -----------------------------

    async def _update_metrics_tick(self) -> None:
        self._g_uptime_seconds.set(self._uptime_seconds(), labels={"svc": self._svc_name})

    def metrics_text(self) -> str:
        return self._mx.render_prometheus()

    # ----------------------------- TLS Version Watcher -----------------------------

    async def _tls_watch_tick(self) -> None:
        """
        Периодически читает версию TLS-бандла из KV и, если версия изменилась,
        инициирует hot-reload через deps.tls_reloader.
        """
        if not getattr(self.deps, "kv", None) or kv_paths is None:
            return

        ver = None
        try:
            # 1) Простая версия (text)
            ver, _ = self.deps.kv.get_text(kv_paths.CERTS_VERSION)
            if not ver:
                # 2) Маркерный JSON
                js, _ = self.deps.kv.get_json(kv_paths.CERTS_STATUS)
                if isinstance(js, dict) and "version" in js:
                    ver = str(js.get("version") or "").strip()
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=tls.version.read.fail", svc=self._svc_name, err=exc)
            return

        if not ver:
            return

        if ver != self._last_cert_version:
            prev = self._last_cert_version or "-"
            self._last_cert_version = ver
            self._m_tls_version_changes.inc(labels={"svc": self._svc_name})
            self.log.info("evt=tls.cert.version.change", svc=self._svc_name, prev=prev, next=ver, phase=self._status.value)
            reloader = getattr(self.deps, "tls_reloader", None)
            if reloader:
                try:
                    reloader.notify_version(ver)
                    self._m_tls_reload_requests.inc(labels={"svc": self._svc_name})
                    self.log.info("evt=tls.reload.requested", svc=self._svc_name, version=ver, phase=self._status.value)
                except Exception as exc:  # noqa: BLE001
                    self._m_tls_reload_fail.inc(labels={"svc": self._svc_name})
                    self.log.warning("evt=tls.reload.fail", svc=self._svc_name, version=ver, err=exc)

    # ----------------------------- Degrade helpers -----------------------------

    def degrade(self, reason: str) -> None:
        """
        Зафиксировать деградацию по причине `reason`. Статус переводится в DEGRADED,
        если не был в нём. Причина добавляется к агрегату причин.
        """
        reason = (reason or "").strip()
        if not reason:
            return
        if reason not in self._degraded_reasons:
            self._degraded_reasons.add(reason)
            self.log.warning("evt=degraded.add", svc=self._svc_name, reason=reason, reasons=sorted(self._degraded_reasons))
        if self._status is ServiceStatus.RUNNING:
            self._set_status(ServiceStatus.DEGRADED, f"degraded:{reason}")

    def recover(self, reason: str) -> None:
        """
        Снять конкретную причину деградации. Если причин больше не осталось и
        сервис был в DEGRADED — вернуть статус RUNNING.
        """
        reason = (reason or "").strip()
        if not reason:
            return
        if reason in self._degraded_reasons:
            self._degraded_reasons.remove(reason)
            self.log.info("evt=degraded.remove", svc=self._svc_name, reason=reason, reasons=sorted(self._degraded_reasons))
        if self._status is ServiceStatus.DEGRADED and not self._degraded_reasons:
            self._set_status(ServiceStatus.RUNNING, "recovered")

    # ----------------------------- Shutdown / Signals -----------------------------

    def _on_signal(self, sig: signal.Signals) -> None:
        self.log.info("evt=signal", svc=self._svc_name, sig=sig.name, phase=self._status.value)

    async def _before_stop(self) -> None:
        self._set_status(ServiceStatus.STOPPING, "shutdown")
        if self._child and self._child.poll() is None:
            self.log.info("evt=child.terminate", svc=self._svc_name)
            try:
                self._child.terminate()
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._child.wait, 10)
            except Exception:
                self.log.warning("evt=child.kill", svc=self._svc_name)
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
                self.log.warning("evt=kv.config_hash.write.false", svc=self._svc_name)
            # config/global/domain_root (подтверждение домена)
            if not kv.config.set_domain_root(SETTINGS.domain.root):
                self.log.warning("evt=kv.domain_root.write.false", svc=self._svc_name)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=kv.publish_config.fail", svc=self._svc_name, err=exc)

    # ----------------------------- Markers helpers -----------------------------

    def _ensure_marker(self, flag: str) -> None:
        """
        Универсальная постановка маркера marker/<svc>/<flag> (идемпотентно, best-effort).
        """
        kv = getattr(self.deps, "kv", None)
        if kv is None:
            return
        try:
            kv.marker.svc(self._svc_name).flag(flag).ensure()
            self.log.info("evt=marker.ensure", svc=self._svc_name, flag=flag)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=marker.ensure.fail", svc=self._svc_name, flag=flag, err=exc)
