# source\services\traefik\app\main.py

from __future__ import annotations
import asyncio
import os
import subprocess
from pathlib import Path
from typing import Optional

from core.base.service import ContextMicroservice
from core.settings.settings import SETTINGS
from core.net.port import wait_port
from core.infra.tls import probe_tls
from core.logging import get_logger
from core.kv import KV, build_consul_kv_from_settings
from core.kv import paths as kvpaths
from core.runtime.status import ServiceStatus
from core.runtime.tls.signal_reloader import SignalTLSReloader
from core.runtime.tls.client_reloader import ClientTLSReloader
from core.runtime.tls.combined_reloader import CombinedTLSReloader
from core.runtime.tls.version_watch import CertsVersionWatcher


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

CONSUL_TOKENS_DIR = Path("/consul/secrets")
TRAEFIK_CONSUL_TOKEN_FILE = CONSUL_TOKENS_DIR / "traefik_consul_token"

CERTS_DIR = Path(SETTINGS.paths.tls_certs_dir)
CA_PEM = CERTS_DIR / "ca.crt"
CRT = CERTS_DIR / "traefik.crt"
KEY = CERTS_DIR / "traefik.key"

INIT_TIMEOUT = float(SETTINGS.timeouts.init_timeout_s)


class TraefikService(ContextMicroservice):
    def __init__(self) -> None:
        super().__init__()
        self._kv: Optional[KV] = None
        self._tls_watch_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        cmd = os.getenv("TRAEFIK_CMD", "traefik --configFile=/etc/traefik/traefik.yml").split()
        self.log.info("evt=proc.start app=traefik cmd=%s", " ".join(cmd))
        proc = subprocess.Popen(cmd)  # noqa: S603
        self.proc_attach(proc)

        # Комбинированный TLS-релоадер: SIGHUP Traefik + клиентский контекст (на будущее)
        try:
            srv = SignalTLSReloader(pid=self._child.pid if self._child else None)
            cli = ClientTLSReloader(ca_file=CA_PEM, cert_file=CRT, key_file=KEY)
            self.deps.tls_reloader = CombinedTLSReloader([srv, cli])
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=tls.reloader.attach.fail err=%s", exc)

        # Wait for HTTP
        if not await wait_port(SETTINGS.traefik.host, TRAEFIK_SCHEME["ports"]["http"], timeout=INIT_TIMEOUT):
            self.log.error("evt=wait.traefik.timeout host=%s port=%s",
                           SETTINGS.traefik.host, TRAEFIK_SCHEME["ports"]["http"])
            return

        # TLS active?
        tls_ok = probe_tls(SETTINGS.traefik.host, TRAEFIK_SCHEME["ports"]["https"],
                           timeout=TRAEFIK_SCHEME["tls_probe"]["probe_timeout"])
        self.svc_set_tls_active(tls_ok)

        # KV attach + marker initialized
        await self._attach_kv()
        if self._kv is not None:
            try:
                self._kv.marker.svc("traefik").initialized.ensure()
            except Exception as exc:  # noqa: BLE001
                self.log.warning("evt=traefik.marker.init.fail err=%s", exc)

        # Единый watcher certs/version → hot reload
        if getattr(self.deps, "kv", None) and getattr(self.deps, "tls_reloader", None):
            watcher = CertsVersionWatcher(self.deps.kv, self.deps.tls_reloader, kvpaths.CERTS_VERSION, 2.0, self.log)
            self._tls_watch_task = asyncio.create_task(watcher.run(self._shutdown))

    async def start(self) -> None:
        self._set_status(ServiceStatus.RUNNING, "traefik.up")
        while not getattr(self, "_shutdown").is_set():
            await asyncio.sleep(5)

    async def stop(self) -> None:
        if self._tls_watch_task and not self._tls_watch_task.done():
            self._tls_watch_task.cancel()
            try:
                await self._tls_watch_task
            except Exception:
                pass
        await super().stop()

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
            if getattr(self, "deps", None) is not None:
                self.deps.kv = self._kv
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=traefik.kv.attach.fail err=%s", exc)
            self._kv = None


async def main() -> None:
    await TraefikService().serve()


if __name__ == "__main__":
    asyncio.run(main())
