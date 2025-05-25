# source/core/base/service.py

import asyncio
import logging
import sys
import signal
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
        self.logger = self._setup_logger()

        self.healthy = False
        self.last_heartbeat = datetime.now(timezone.utc)
        self._health_runner = None

        self._shutdown_event = asyncio.Event()
        self._main_task = None
        self._subprocess = None


    async def start(self):
        self.logger.info("Starting service...")
        # Setup signal handlers
        self._setup_signal_handlers()
        await self.initialize()
        # main run loop is scheduled as a task, to allow graceful shutdown
        self._main_task = asyncio.create_task(self.run())
        await self._shutdown_event.wait()
        self.logger.info("Shutdown event triggered. Waiting for main task to finish...")
        if self._main_task:
            await self._main_task
        self.logger.info("Service stopped.")


    async def initialize(self):
        self.logger.info("Initializing service...")
        self._setup_metrics()
        await self._setup_health()
        self._setup_vault()
        await asyncio.sleep(0.1)


    async def run(self):
        self.logger.info("Service is running.")
        try:
            while not self._shutdown_event.is_set():
                self.last_heartbeat = datetime.now(timezone.utc)
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            self.logger.info("Service cancelled.")
        finally:
            await self.stop()


    async def stop(self):
        self.logger.info("Stopping service...")
        # Stop healthcheck server
        if self._health_runner:
            await self._health_runner.cleanup()
            self.logger.info("Healthcheck server stopped.")
        # Stop any subprocess if exists
        if self._subprocess and self._subprocess.poll() is None:
            self.logger.info("Terminating subprocess...")
            self._subprocess.terminate()
            try:
                self._subprocess.wait(timeout=10)
                self.logger.info("Subprocess terminated gracefully.")
            except Exception:
                self.logger.warning("Subprocess did not terminate in time, killing...")
                self._subprocess.kill()
        self.healthy = False


    async def shutdown(self, signame):
        self.logger.info(f"Received {signame}. Initiating shutdown...")
        self._shutdown_event.set()


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


    def _setup_signal_handlers(self):
        # Register handlers for SIGTERM, SIGINT for graceful shutdown
        try:
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(self.shutdown("SIGTERM")))
            loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(self.shutdown("SIGINT")))
            self.logger.info("Signal handlers set for SIGTERM/SIGINT.")
        except NotImplementedError:
            # Windows compatibility: signals not supported in ProactorEventLoop
            self.logger.warning("Signal handlers not supported on this platform.")


    # New: For main.py, so subprocess can be tracked and terminated
    def set_subprocess(self, process):
        self._subprocess = process


    def _setup_metrics(self):
        self.logger.info("Metrics exporter not implemented.")


    def _setup_vault(self):
        self.logger.info("Vault integration not implemented.")