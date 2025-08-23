# source/services/traefik/app/main.py


from __future__ import annotations
import asyncio
import os
import subprocess
from core.base.service import ContextMicroservice
from core.runtime.status import ServiceStatus
from core.settings.settings import settings
from core.net.port import wait_port
from core.infra.tls import probe_tls


TRAEFIK_SCHEME: dict = {
    "ports": {
        "http": int(settings.TRAEFIK_PORT_HTTP),
        "https": int(settings.TRAEFIK_PORT_HTTPS),
    },
    "tls_probe": {
        "host": settings.TRAEFIK_HOST,
        "require_tls": False,
        "probe_timeout": 2.0,
    },
}


class TraefikService(ContextMicroservice):
    async def initialize(self) -> None:
        cmd = os.getenv("TRAEFIK_CMD", "traefik --configFile=/etc/traefik/traefik.yml").split()
        self.log.info("evt=proc.start app=traefik cmd=%s", " ".join(cmd))
        proc = subprocess.Popen(cmd)  # noqa: S603
        self.proc_attach(proc)

        if not await wait_port(settings.TRAEFIK_HOST, TRAEFIK_SCHEME["ports"]["http"], timeout=60.0):
            self.log.error("evt=wait.traefik.timeout host=%s port=%s", settings.TRAEFIK_HOST, TRAEFIK_SCHEME["ports"]["http"])
            return

        tls_ok = probe_tls(settings.TRAEFIK_HOST, TRAEFIK_SCHEME["ports"]["https"], timeout=TRAEFIK_SCHEME["tls_probe"]["probe_timeout"])
        self.svc_set_tls_active(tls_ok)

        if TRAEFIK_SCHEME["tls_probe"]["require_tls"]:
            attempts = 0
            while not tls_ok and attempts < 30:
                await asyncio.sleep(2.0)
                tls_ok = probe_tls(settings.TRAEFIK_HOST, TRAEFIK_SCHEME["ports"]["https"], timeout=2.0)
                attempts += 1
            self.svc_set_tls_active(tls_ok)

    async def start(self) -> None:
        self._set_status(ServiceStatus.RUNNING, "traefik.up")
        while not getattr(self, "_shutdown").is_set():
            await asyncio.sleep(5)

async def main() -> None:
    await TraefikService().serve()

if __name__ == "__main__":
    asyncio.run(main())
