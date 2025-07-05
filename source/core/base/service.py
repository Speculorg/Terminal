# source\core\base\service.py


from __future__ import annotations

import asyncio
import json
import logging
import signal
import socket
import requests
import sys
import time
from pathlib import Path
from typing import Optional


sys.path.append("/")
from core.base.settings import settings


# ────────────────────────── constants ──────────────────────────
LOG_FORMAT = ('{"ts":"%(asctime)s","svc":"' + settings.SERVICE_NAME + '","lvl":"%(levelname)s","msg":"%(message)s"}')


class BaseService:
    # ───────────────────── lifecycle ─────────────────────
    def __init__(self) -> None:
        self._logger = self._setup_logger()
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self._main_task: Optional[asyncio.Task] = None
        self._subprocess = None  # type: ignore


    async def start(self) -> None:
        self._logger.info("Entering BaseService ...")
        self._setup_signal_handlers()

        await self.before_run()

        self._main_task = asyncio.create_task(self.run())
        await self._shutdown_event.wait()

        if self._main_task:
            await self._main_task
        await self.after_stop()
        self._logger.info("Service fully stopped")


    # subclasses override ----------------------------------------------------------------
    async def before_run(self) -> None: ...


    async def run(self) -> None:                                         # noqa: D401
        """Long-living loop - must be overridden."""
        while not self._shutdown_event.is_set():
            await asyncio.sleep(60)


    async def after_stop(self) -> None: ...
    # ------------------------------------------------------------------------------------


    # ─────────────────── graceful shutdown ───────────────────
    def _setup_signal_handlers(self) -> None:
        loop = asyncio.get_event_loop()
        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda s=sig: self._on_signal(s))
            self._logger.info("SIGTERM/SIGINT handlers registered")
        except NotImplementedError:
            self._logger.warning("Signal handlers unsupported on this platform")


    def _on_signal(self, signum: signal.Signals) -> None:
        self._logger.info("Received %s -> shutdown flag set", signum.name)
        self._shutdown_event.set()


    # ────────────────── subprocess helper ───────────────────
    def set_subprocess(self, popen) -> None:                            # subprocess.Popen
        self._subprocess = popen


    async def _terminate_subprocess(self) -> None:
        if self._subprocess and self._subprocess.poll() is None:
            self._logger.info("Terminating child process …")
            self._subprocess.terminate()
            try:
                await asyncio.get_event_loop().run_in_executor(None, self._subprocess.wait, 10)
            except Exception:                                           # pylint: disable=broad-except
                self._logger.warning("Child not stopped -> kill")
                self._subprocess.kill()


    # ─────────────── consul registration ────────────────
    async def register_in_consul(self) -> None:
        if settings.SERVICE_NAME == "consul":
            self._logger.info("Skip Consul self-registration")
            return

        token_path = settings.CONSUL_HTTP_TOKEN_FILE
        token = Path(token_path).read_text().strip() if token_path else ""

        if not await self._wait_port(settings.CONSUL_HOST, settings.CONSUL_PORT, 20):
            self._logger.error("Consul not reachable - registration skipped")
            return

        payload = {
            "Name":  settings.SERVICE_NAME,
            "Port":  settings.SERVICE_PORT,
            "Tags":  [t.strip() for t in settings.SERVICE_TAGS.split(",") if t],
            "Meta":  {"env": settings.ENV_MODE},
            "EnableTagOverride": False,
        }

        hdrs = {"X-Consul-Token": token} if token else {}
        url = f"http://{settings.CONSUL_HOST}:{settings.CONSUL_PORT}/v1/agent/service/register"

        try:
            resp = requests.put(url, headers=hdrs, data=json.dumps(payload), timeout=5)
            resp.raise_for_status()
            self._logger.info("OK - Registered in consul")
        except Exception as exc:                                        # pylint: disable=broad-except
            self._logger.error("Failed registered in consul: %s", exc)


    # ────────────────────── helpers ──────────────────────
    @staticmethod
    async def _wait_port(host: str, port: int, timeout: int) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection((host, port), timeout=2):
                    return True
            except Exception:
                await asyncio.sleep(1)
        return False


    @staticmethod
    def _setup_logger() -> logging.Logger:
        logger = logging.getLogger(settings.SERVICE_NAME)
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(LOG_FORMAT))
            logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        return logger
