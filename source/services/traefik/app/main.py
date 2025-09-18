# source/services/traefik/app/main.py

from __future__ import annotations
import asyncio
import os
import signal
import socket
import ssl
import subprocess
from pathlib import Path
from typing import Optional

from core.base.service import ContextMicroservice
from core.runtime.status import ServiceStatus
from core.settings.settings import SETTINGS
from core.net.port import wait_port
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
        "probe_timeout": 2.0,
    },
}

# Consul tokens issued by Consul service (must be mounted here)
CONSUL_TOKENS_DIR = Path("/consul/secrets")
TRAEFIK_CONSUL_TOKEN_FILE = CONSUL_TOKENS_DIR / "traefik_consul_token"

# TLS certs
CERTS_DIR = Path(SETTINGS.paths.tls_certs_dir)
CA_CERT   = CERTS_DIR / "ca.crt"
TR_CRT    = CERTS_DIR / "traefik.crt"
TR_KEY    = CERTS_DIR / "traefik.key"

# Тайминги
INIT_TIMEOUT = float(SETTINGS.timeouts.init_timeout_s)
SMOKE_MAX_ATTEMPTS = 15
SMOKE_RETRY_SEC = 2.0


def _probe_tls_server(host: str, port: int, ca_file: Optional[Path] = None, timeout: float = 2.0) -> bool:
    """
    Простой TLS-handshake к серверу (без клиентского сертификата).
    """
    try:
        ctx = ssl.create_default_context()
        if ca_file and ca_file.exists():
            ctx.load_verify_locations(cafile=str(ca_file))
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                ssock.do_handshake()
        return True
    except Exception:
        return False


def _probe_mtls(host: str, port: int, ca_file: Path, cert_file: Path, key_file: Path, timeout: float = 2.0) -> bool:
    """
    mTLS-handshake (клиентский сертификат + проверка сервера).
    """
    try:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if ca_file.exists():
            ctx.load_verify_locations(cafile=str(ca_file))
        ctx.load_cert_chain(certfile=str(cert_file), keyfile=str(key_file))
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                ssock.do_handshake()
        return True
    except Exception:
        return False


class TraefikService(ContextMicroservice):
    # Для Traefik не делаем жёсткий gate «требовать TLS для RUNNING»,
    # так как TLS может включиться после первого reload. Оставляем дефолт False.

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._kv: Optional[KV] = None
        self._last_certs_version: Optional[str] = None
        self._watch_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        cmd = os.getenv("TRAEFIK_CMD", "traefik --configFile=/etc/traefik/traefik.yml").split()
        self.log.info("evt=proc.start app=traefik cmd=%s", " ".join(cmd))
        proc = subprocess.Popen(cmd)  # noqa: S603
        self.proc_attach(proc)

        if not await wait_port(SETTINGS.traefik.host, TRAEFIK_SCHEME["ports"]["http"], timeout=INIT_TIMEOUT):
            self.log.error("evt=wait.traefik.timeout host=%s port=%s",
                           SETTINGS.traefik.host, TRAEFIK_SCHEME["ports"]["http"])
            return

        # Быстрая проверка HTTPS на периметре (серверный TLS)
        tls_ok = _probe_tls_server(
            TRAEFIK_SCHEME["tls_probe"]["host"],
            TRAEFIK_SCHEME["ports"]["https"],
            ca_file=CA_CERT if CA_CERT.exists() else None,
            timeout=float(TRAEFIK_SCHEME["tls_probe"]["probe_timeout"]),
        )
        self.svc_set_tls_active(tls_ok)

        # Маркер инициализации (best-effort)
        await self._publish_initialized_marker()

        # Подключение к KV и запуск вотчера версии сертификатов
        await self._attach_kv()
        if self._kv is not None and self._watch_task is None:
            self._watch_task = asyncio.create_task(self._watch_certs_version_loop())

        # Лёгкий smoke: mTLS до Consul (best-effort, не блокирующий)
        asyncio.create_task(self._smoke_mtls_to_consul_once())

    async def start(self) -> None:
        # Если к моменту входа в RUNNING уже есть активные причины деградации —
        # базовый класс сам зафиксирует DEGRADED. Здесь обычный рабочий цикл.
        self._set_status(ServiceStatus.RUNNING, "start()")
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
            if getattr(self, "deps", None) is not None:
                self.deps.kv = self._kv
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=traefik.kv.attach.fail err=%s", exc)
            self._kv = None

    async def _publish_initialized_marker(self) -> None:
        try:
            token = None
            if TRAEFIK_CONSUL_TOKEN_FILE.exists():
                token = TRAEFIK_CONSUL_TOKEN_FILE.read_text(encoding="utf-8").strip() or None
            if token:
                kv = KV(build_consul_kv_from_settings(SETTINGS, token=token))
                kv.marker.ensure_true(kvpaths.M_TRAEFIK_INITIALIZED)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("evt=traefik.marker.init.fail err=%s", exc)

    # ---------------- Version watch & Hot reload ----------------

    async def _watch_certs_version_loop(self) -> None:
        """
        Пуллинг certs/version из KV; при изменении — посылаем Traefik SIGHUP (hot reload),
        после чего проверяем, что HTTPS снова поднялся; затем делаем одноразовый mTLS-smoke до Consul.
        При длительной неуспешности фиксируем DEGRADED и снимаем её при восстановлении.
        """
        self.log.info("evt=traefik.watch.start key=%s interval_s=%.3f", kvpaths.CERTS_VERSION, SMOKE_RETRY_SEC)
        delay = SMOKE_RETRY_SEC
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

                    if getattr(self, "_child", None):
                        try:
                            self._child.send_signal(signal.SIGHUP)
                            self.log.info("evt=traefik.sighup.sent")
                            # Подтвердим, что HTTPS поднялся после reload
                            https_ok = await self._verify_https_after_reload()
                            if not https_ok:
                                self.degrade("https_reload_failed")
                            else:
                                self.recover("https_reload_failed")

                            # Одноразовый mTLS-smoke до Consul
                            mtls_ok = await self._smoke_mtls_to_consul_once()
                            if not mtls_ok:
                                self.degrade("mtls_to_consul_failed")
                            else:
                                self.recover("mtls_to_consul_failed")

                        except Exception as exc:  # noqa: BLE001
                            self.log.warning("evt=traefik.sighup.fail err=%s", exc)
                            self.degrade("sighup_exception")
            except Exception as exc:  # noqa: BLE001
                self.log.warning("evt=watch.loop.err err=%s", exc)

            await asyncio.sleep(delay)

    async def _verify_https_after_reload(self) -> bool:
        host = TRAEFIK_SCHEME["tls_probe"]["host"]
        port = TRAEFIK_SCHEME["ports"]["https"]
        for attempt in range(1, SMOKE_MAX_ATTEMPTS + 1):
            ok = _probe_tls_server(host, port, ca_file=CA_CERT if CA_CERT.exists() else None, timeout=2.0)
            if ok:
                self.log.info("evt=traefik.reload.https.ok attempt=%d", attempt)
                self.svc_set_tls_active(True)
                return True
            await asyncio.sleep(SMOKE_RETRY_SEC)
        self.log.warning("evt=traefik.reload.https.fail attempts=%d", SMOKE_MAX_ATTEMPTS)
        return False

    async def _smoke_mtls_to_consul_once(self) -> bool:
        """
        Неблокирующая проверка mTLS до Consul: клиент — traefik.crt/key, сервер — consul:8501.
        Возвращает успех/провал; не меняет фаз напрямую (только через degrade/recover в вызывающем коде).
        """
        if not (CA_CERT.exists() and TR_CRT.exists() and TR_KEY.exists()):
            return False
        host, port = SETTINGS.consul.host, SETTINGS.consul.https_port
        for attempt in range(1, SMOKE_MAX_ATTEMPTS + 1):
            ok = _probe_mtls(host, port, CA_CERT, TR_CRT, TR_KEY, timeout=2.0)
            if ok:
                self.log.info("evt=smoke.mtls.consul.ok attempt=%d", attempt)
                return True
            await asyncio.sleep(SMOKE_RETRY_SEC)
        self.log.warning("evt=smoke.mtls.consul.fail attempts=%d host=%s port=%s", SMOKE_MAX_ATTEMPTS, host, port)
        return False

    async def stop(self) -> None:
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
            try:
                await self._watch_task
            except Exception:
                pass
        await super().stop()


async def main() -> None:
    await TraefikService().serve()


if __name__ == "__main__":
    asyncio.run(main())
