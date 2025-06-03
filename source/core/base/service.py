# source\core\base\service.py


import asyncio
import logging
import os
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Optional

import requests

sys.path.append("/")
from core.base.settings import settings   # pylint: disable=wrong-import-position


class BaseService:
    """
    Basic asynchronous wrapper for Speculorg services.
    """

    # ──────────────────────────── INIT / START ────────────────────────────
    def __init__(self) -> None:
        self.env = settings
        self.service_name = self.env.SERVICE_NAME
        self.service_port = int(self.env.SERVICE_PORT)
        self.consul_host = self.env.CONSUL_HOST
        self.consul_port = int(self.env.CONSUL_PORT)
        self.logger = self._setup_logger()
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self._main_task: Optional[asyncio.Task] = None
        self._subprocess = None  # type: ignore

        # ───── Consul tokens ──────
        # path = os.environ.get("CONSUL_TOKEN_FILE", "")
        # self.consul_token = Path(path).read_text().strip() if path else ""
        # self.logger.info("self.consul_token = %s", self.consul_token)

    # ──────────────────────────── LIFECYCLE ────────────────────────────
    async def start(self) -> None:
        self.logger.info("Starting service %s", self.service_name)
        self._setup_signal_handlers()

        await asyncio.sleep(0.1)
        self._main_task = asyncio.create_task(self.run())  # noqa
        await self._shutdown_event.wait()

        self.logger.info("Shutdown flag set → waiting main task …")
        if self._main_task:
            await self._main_task
        self.logger.info("Service fully stopped.")

    async def run(self) -> None:  # noqa: D401
        """Main service loop."""
        self.logger.info("Service loop started.")
        try:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            self.logger.info("Main task cancelled.")
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the service."""
        self.logger.info("Stopping service …")
        if self._subprocess and self._subprocess.poll() is None:
            self.logger.info("Terminating subprocess …")
            self._subprocess.terminate()
            try:
                self._subprocess.wait(timeout=10)
                self.logger.info("Subprocess terminated gracefully.")
            except Exception:  # pylint: disable=broad-except
                self.logger.warning("Subprocess didn`t stop in time → killing.")
                self._subprocess.kill()

    # ──────────────────────────── SIGNALS ────────────────────────────
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers."""
        loop = asyncio.get_event_loop()
        try:
            loop.add_signal_handler(signal.SIGTERM,
                                    lambda: asyncio.create_task(self._shutdown("SIGTERM")))
            loop.add_signal_handler(signal.SIGINT,
                                    lambda: asyncio.create_task(self._shutdown("SIGINT")))
            self.logger.info("SIGTERM / SIGINT handlers registered.")
        except NotImplementedError:
            self.logger.warning("Signal handlers not supported on this platform.")

    async def _shutdown(self, signame: str) -> None:
        """Set shutdown flag."""
        self.logger.info(f"Received {signame} → set shutdown flag.")
        self._shutdown_event.set()

    # ──────────────────────────── CONSUL REGISTRATION ────────────────────────────
    async def register_in_consul(self) -> None:
        """Register service in Consul."""
        if self.service_name == "consul":
            self.logger.info("Skip Consul self-registration.")
            return
        
        path = os.environ.get("REGISTERING_CONSUL_TOKEN_FILE", "")
        self.registering_consul_token = Path(path).read_text().strip() if path else ""
        # self.logger.info("self.registering_consul_token = %s", self.registering_consul_token)        
        
        self.logger.info("Registering service in Consul …")
        if not await self._wait_for_port(self.consul_host, self.consul_port, 20):
            self.logger.error("Consul not reachable → registration skipped.")
            return

        payload = {
            "Name": self.service_name,
            "Port": self.service_port,
            "Tags": [t.strip() for t in self.env.SERVICE_TAGS.split(",") if t],
        }

        headers = {"X-Consul-Token": self.registering_consul_token} if self.registering_consul_token else {}
        url = f"http://{self.consul_host}:{self.consul_port}/v1/agent/service/register"

        try:
            resp = requests.put(url, json=payload, headers=headers, timeout=5)
            resp.raise_for_status()
            self.logger.info("Service registered in Consul.")
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.error(f"Consul registration failed: {exc}")

    # ──────────────────────────── HELPERS ────────────────────────────
    def set_subprocess(self, process) -> None:
        """Save Popen-object of child process for proper shutdown."""
        self._subprocess = process


    @staticmethod
    async def _wait_for_port(host: str, port: int, timeout: int) -> bool:
        """Wait for port to be open."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection((host, port), timeout=2):
                    return True
            except Exception:
                await asyncio.sleep(1)
        return False

    @staticmethod
    def _read_token_file(path: str) -> str:
        """Read token from specified path"""
        try:
            p = Path(path)
            if p.is_file():
                return p.read_text().strip()
        except Exception:  # pylint: disable=broad-except
            pass
        return ""


    def _setup_logger(self) -> logging.Logger:
        """Setup logger"""
        logger = logging.getLogger(self.service_name)
        logger.setLevel(getattr(logging, self.env.LOG_LEVEL.upper(), logging.INFO))
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(
                '{"ts":"%(asctime)s","svc":"' + self.service_name +
                '","lvl":"%(levelname)s","msg":"%(message)s"}'
            ))
            logger.addHandler(handler)
        return logger
