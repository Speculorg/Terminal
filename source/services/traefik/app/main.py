# source/services/traefik/app/main.py

import sys
import os
import asyncio
import subprocess

sys.path.append("/")
from core.base.service import BaseService

os.environ["SERVICE_NAME"] = "traefik-service"
os.environ["SERVICE_PORT"] = "443"
os.environ["SERVICE_TAGS"] = "core,infra,proxy,edge,routing"

class Service(BaseService):
    async def run(self):
        self.logger.info("Starting Traefik process...")
        process = subprocess.Popen(["traefik", "--configFile=/etc/traefik/traefik.yml"])
        self.set_subprocess(process)

        await self.register_in_consul()

        if process.poll() is not None:
            self.logger.error("Traefik startup error.")
            await self.stop()
            return

        self.healthy = True
        self.logger.info("Traefik service is running.")
        try:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            self.logger.info("Service cancelled.")
        finally:
            await self.stop()

if __name__ == "__main__":
    svc = Service()
    asyncio.run(svc.start())
