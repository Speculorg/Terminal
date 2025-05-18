# source/services/consul/app/main.py

import sys
import os
import asyncio
import subprocess

sys.path.append("/")
from core.base.service import BaseService

os.environ["SERVICE_NAME"] = "consul-service"
os.environ["SERVICE_PORT"] = "8500"
os.environ["SERVICE_TAGS"] = "core,infra,dns,discovery"

class Service(BaseService):
    async def run(self):
        self.logger.info("Starting Consul agent subprocess...")
        process = subprocess.Popen(["consul", "agent", "-config-file=/consul/config/consul.hcl"])
        self.set_subprocess(process)

        await self.register_in_consul()

        if process.poll() is not None:
            self.logger.error("Consul startup error.")
            await self.stop()
            return

        self.healthy = True
        self.logger.info("Consul service is running.")
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
