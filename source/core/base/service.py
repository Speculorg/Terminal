# source\core\base\service.py

import asyncio
import logging
import socket
import sys
import time
import requests
from datetime import datetime, timezone
from aiohttp import web

sys.path.append("/")
from core.base.settings import settings

class BaseService:
    def __init__(self):
        self.env = settings
        self.service_name = self.env.SERVICE_NAME
        self.service_port = int(self.env.SERVICE_PORT)
        self.health_port = int(self.env.HEALTHCHECK_PORT)
        self.consul_host = self.env.CONSUL_HOST
        self.consul_port = self.env.CONSUL_PORT
        self.logger = self._setup_logger()

        self.healthy = False
        self.last_heartbeat = datetime.now(timezone.utc)
        self._health_runner = None

    def _setup_logger(self):
        logger = logging.getLogger(self.service_name)
        logger.setLevel(getattr(logging, self.env.LOG_LEVEL.upper(), logging.INFO))
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "service": "' + self.service_name +
            '", "level": "%(levelname)s", "message": "%(message)s"}'
        )
        handler.setFormatter(formatter)
        if not logger.handlers:
            logger.addHandler(handler)
        return logger

    async def start(self):
        self.logger.info("Starting service...")
        await self.initialize()
        await self.run()

    async def initialize(self):
        self.logger.info("Initializing service...")
        self._setup_metrics()
        await self._setup_health()
        self._setup_vault()
        await asyncio.sleep(0.1)

    async def run(self):
        self.logger.info("Service is running.")
        try:
            while True:
                self.last_heartbeat = datetime.now(timezone.utc)
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            self.logger.info("Service cancelled.")
        finally:
            self.stop()

    def stop(self):
        self.logger.info("Stopping service...")

    def _setup_metrics(self):
        self.logger.info("Metrics exporter not implemented.")

    def _setup_vault(self):
        self.logger.info("Vault integration not implemented.")

    async def _setup_health(self):
        async def handle_health(request):
            now = datetime.utcnow().isoformat()
            status = {
                "status": "ok" if self.healthy else "unhealthy",
                "service": self.service_name,
                "port": self.health_port,
                "last_heartbeat": self.last_heartbeat.isoformat(),
                "timestamp": now
            }
            return web.json_response(status, status=200 if self.healthy else 503)

        app = web.Application()
        app.router.add_get("/health", handle_health)

        self._health_runner = web.AppRunner(app)
        await self._health_runner.setup()
        site = web.TCPSite(self._health_runner, "0.0.0.0", self.health_port)
        await site.start()

        self.logger.info(f"Healthcheck server started at http://0.0.0.0:{self.health_port}/health")

    async def register_in_consul(self):
        if self.service_name == "consul-service":
            self.logger.info("Skipping Consul self-registration.")
            return

        self.logger.info("Waiting for Consul...")
        if not await self._wait_for_port(self.consul_host, self.consul_port, self.env.CONSUL_TIMEOUT):
            self.logger.error("Consul not reachable.")
            return

        payload = {
            "Name": self.service_name,
            "Port": self.service_port,
            "Tags": [t.strip() for t in self.env.SERVICE_TAGS.split(",") if t],
            "Check": {
                "HTTP": f"http://{self.service_name}:{self.health_port}/health",
                "Interval": self.env.CONSUL_CHECK_INTERVAL,
                "Timeout": self.env.CONSUL_CHECK_TIMEOUT
            }
        }

        try:
            url = f"http://{self.consul_host}:{self.consul_port}/v1/agent/service/register"
            resp = requests.put(url, json=payload, timeout=5)
            resp.raise_for_status()
            self.logger.info(f"Registered in Consul: {self.service_name}:{self.service_port}")
        except Exception as e:
            self.logger.error(f"Consul registration failed: {e}")

    async def _wait_for_port(self, host, port, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection((host, port), timeout=2):
                    return True
            except Exception:
                await asyncio.sleep(1)
        return False
