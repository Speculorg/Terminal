# source/services/traefik/app/main.py

from __future__ import annotations
import asyncio
import os
import signal
import subprocess
from pathlib import Path
from typing import Optional

from core.base.service import ContextMicroservice
from core.runtime.status import ServiceStatus
from core.settings.settings import SETTINGS
from core.net.port import wait_port
from core.infra.tls import probe_tls
from core.logging import get_logger

# KV / SoT
from core.kv import KV, build_consul_kv_from_settings
from core.kv import paths as kvpaths

log = get_logger("traefik.app")


TRAEFIK_SCHEME: dict = {
    "ports": {
        "http": int(SETTINGS.traefik.http_port),
        "https": int(SETTINGS.traefik.https_port),
    },
    "tls_probe": {
        "host": SETTINGS.traefik.host,
        "require_tls": False,      # на TERM-1 не навязываем строгую проверку, только детектим
        "probe_timeout": 2.0,
    },
}

# Consul tokens issued by Consul service (must be mounted here)
CONSUL_TOKENS_DIR = Path("/consul/secrets")
TRAEFIK_CONSUL_TOKEN_FILE = CONSUL_TOKENS_DIR / "traefik_consul_token"

# Тайминги из SETTINGS
INIT_TIMEOUT = float(SETTINGS.timeouts.init_timeout_s)


class TraefikService(ContextMicroservice):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._kv: Optional[KV] = None
        self._last_certs_version: Optional[str] = None
        self._watch_task: Optional[asyncio.Task] = None
        self._kv_attach_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        cmd = os.getenv("TRAEFIK_CMD", "traefik --configFile=/etc/traefik/traefik.yml").split()
        self.log.info("evt=proc.start app=traefik cmd=%s", " ".join(cmd))
        proc = subprocess.Popen(cmd)  # noqa: S603
        self.proc_attach(proc)

        if not await wait_port(SETTINGS.traefik.host, TRAEFIK_SCHEME["ports"]["http"], timeout=INIT_TIMEOUT):
            self.log.error("evt=wait.traefik.timeout host=%s port=%s",
                           SETTINGS.traefik.host, TRAEFIK_SCHEME["ports"]["http"])
            return

        tls_ok = probe_tls(SETTINGS.traefik.host, TRAEFIK_SCHEME["ports"]["https"],
                           timeout=TRAEFIK_SCHEME["tls_probe"]["probe_timeout"])
        self.svc_set_tls_active(tls_ok)

        # Маркер инициализации (best-effort, может сработать даже без deps.kv)
        await self._publish_initialized_marker()

        # Подключаемся к KV (если есть токен) и запускаем watcher на certs/version
        await self._attach_kv()
        if self._kv is None:
            # Токена может ещё не быть — запускаем лёгкий ретрай для позднего присоединения
            self._kv_attach_task = asyncio.create_task(self._kv_attach_loop())

        if self._kv is not None and self._watch_task is None:
            self._watch_task = asyncio.create_task(self._watch_certs_version_loop())

        if TRAEFIK_SCHEME["tls_probe"]["require_tls"]:
            attempts = 0
            while not tls_ok and attempts < 30:
                await asyncio.sleep(2.0)
                tls_ok = probe_tls(SETTINGS.traefik.host, TRAEFIK_SCHEME["ports"]["https"], timeout=2.0)
                attempts += 1
            self.svc_set_tls_active(tls_ok)

    async def start(self) -> None:
        self._set_status(ServiceStatus.RUNNING, "traefik.up")
        while not getattr(self, "_shutdown").is_set():
            await asyncio.sleep(5)

    # ---------------- KV helpers ----------------

    async def _kv_attach_loop(self) -> None:
        """
        Пытается присоединить KV каждую пару секунд, пока не получится или пока сервис не остановлен.
        """
        delay = 3.0
        while not getattr(self, "_shutdown").is_set() and self._kv is None:
            await asyncio.sleep(delay)
            try:
                await self._attach_kv()
                if self._kv is not None and self._watch_task is None:
                    self._watch_task = asyncio.create_task(self._watch_certs_version_loop())
                    self.log.info("evt=traefik.kv.attached.late")
            except Exception as exc:  # noqa: BLE001
                self.log.warning("evt=traefik.kv.attach.retry.fail err=%s", exc)

    async def _attach_kv(self) -> None:
        token = None
        try:
            if TRAEFIK_CONSUL_TOKEN_FILE.exists():
                token = TRAEFIK_CONSUL_TOKEN_FILE.read_text(encoding="utf-8").strip() or None
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=traefik.kv.token.read.fail err=%s", exc)

        if not token:
            self.log.warning("evt=traefik.kv.attach.skip reason=no.consul.token")
            return

        try:
            client = build_consul_kv_from_settings(SETTINGS, token=token)
            self._kv = KV(client)
            # присоединим в deps - базовый класс будет слать heartbeat и статусы
            if getattr(self, "deps", None) is not None:
                self.deps.kv = self._kv
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=traefik.kv.attach.fail err=%s", exc)
            self._kv = None

    async def _publish_initialized_marker(self) -> None:
        try:
            # Публикуем marker/traefik/initialized (best-effort)
            token = None
            if TRAEFIK_CONSUL_TOKEN_FILE.exists():
                token = TRAEFIK_CONSUL_TOKEN_FILE.read_text(encoding="utf-8").strip() or None
            if token:
                kv = KV(build_consul_kv_from_settings(SETTINGS, token=token))
                kv.marker.ensure_true(kvpaths.M_TRAEFIK_INITIALIZED)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=traefik.marker.init.fail err=%s", exc)

    async def _watch_certs_version_loop(self) -> None:
        """
        Пуллинг certs/version из KV; при изменении - посылаем Traefik процессу SIGHUP (hot reload).
        """
        self.log.info("evt=traefik.watch.start key=%s", kvpaths.CERTS_VERSION)
        delay = 2.0
        while not getattr(self, "_shutdown").is_set():
            try:
                if self._kv is None:
                    await asyncio.sleep(delay)
                    continue
                version, _ = self._kv.get_text(kvpaths.CERTS_VERSION)
                if version and version != self._last_certs_version:
                    prev = self._last_certs_version
                    self._last_certs_version = version
                    self.log.info("evt=certs.version.changed prev=%s next=%s", prev or "-", version)
                    # Hot reload Traefik
                    if getattr(self, "_child", None):
                        try:
                            self._child.send_signal(signal.SIGHUP)
                            self.log.info("evt=traefik.sighup.sent")
                        except Exception as exc:  # noqa: BLE001
                            self.log.warning("evt=traefik.sighup.fail err=%s", exc)
            except Exception as exc:  # noqa: BLE001
                self.log.warning("evt=watch.loop.err err=%s", exc)

            await asyncio.sleep(delay)

    async def stop(self) -> None:
        # Остановим фоновые задачи перед стандартной остановкой
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
            try:
                await self._watch_task
            except Exception:
                pass
        if self._kv_attach_task and not self._kv_attach_task.done():
            self._kv_attach_task.cancel()
            try:
                await self._kv_attach_task
            except Exception:
                pass
        await super().stop()


async def main() -> None:
    await TraefikService().serve()


if __name__ == "__main__":
    asyncio.run(main())
