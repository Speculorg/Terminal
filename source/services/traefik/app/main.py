# source/services/traefik/app/main.py

from __future__ import annotations
import asyncio
import os
import subprocess
from pathlib import Path
from typing import Optional

from core.base.service import ContextMicroservice, ContextMicroserviceDeps
from core.runtime.status import ServiceStatus
from core.settings.settings import SETTINGS
from core.net.port import wait_port
from core.infra.tls import probe_tls
from core.logging import get_logger

# KV / SoT
from core.kv import KV, build_consul_kv_from_settings

# TLS hot-reload для внешнего процесса
from core.runtime.tls.signal_reloader import SignalTLSReloader

log = get_logger("traefik.app")


TRAEFIK_SCHEME: dict = {
    "ports": {
        "http": int(SETTINGS.traefik.http_port),
        "https": int(SETTINGS.traefik.https_port),
    },
    "tls_probe": {
        "host": SETTINGS.traefik.host,
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

    async def initialize(self) -> None:
        cmd = os.getenv("TRAEFIK_CMD", "traefik --configFile=/etc/traefik/traefik.yml").split()
        self.log.info("evt=proc.start app=traefik cmd=%s", " ".join(cmd))
        proc = subprocess.Popen(cmd)  # noqa: S603
        self.proc_attach(proc)

        # Подключаем SignalTLSReloader к каркасу (hot-reload по SIGHUP)
        try:
            if getattr(self, "deps", None) is not None:
                # pid уже есть у дочернего процесса
                self.deps.tls_reloader = SignalTLSReloader(pid=self._child.pid if self._child else None)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=tls.reloader.attach.fail err=%s", exc)

        # Ждём HTTP-порт (готовность API/entrypoint)
        if not await wait_port(SETTINGS.traefik.host, TRAEFIK_SCHEME["ports"]["http"], timeout=INIT_TIMEOUT):
            self.log.error("evt=wait.traefik.timeout host=%s port=%s",
                           SETTINGS.traefik.host, TRAEFIK_SCHEME["ports"]["http"])
            return

        # Определяем активность TLS (наружный 443)
        tls_ok = probe_tls(SETTINGS.traefik.host, TRAEFIK_SCHEME["ports"]["https"],
                           timeout=TRAEFIK_SCHEME["tls_probe"]["probe_timeout"])
        self.svc_set_tls_active(tls_ok)

        # Подключаемся к KV и ставим универсальные маркеры (initialized)
        await self._attach_kv()
        if self._kv is not None:
            try:
                self._kv.marker.svc("traefik").initialized.ensure()
            except Exception as exc:  # noqa: BLE001
                self.log.warning("evt=traefik.marker.init.fail err=%s", exc)

    async def start(self) -> None:
        self._set_status(ServiceStatus.RUNNING, "traefik.up")
        while not getattr(self, "_shutdown").is_set():
            await asyncio.sleep(5)

    # ---------------- KV helpers ----------------

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
            # присоединим в deps — базовый класс будет слать heartbeat/markers
            if getattr(self, "deps", None) is not None:
                self.deps.kv = self._kv
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=traefik.kv.attach.fail err=%s", exc)
            self._kv = None


async def main() -> None:
    # Возможность переопределить deps здесь при необходимости
    await TraefikService().serve()


if __name__ == "__main__":
    asyncio.run(main())
