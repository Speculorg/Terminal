# source\services\consul\app\main.py

import sys
import os
import asyncio
import subprocess

sys.path.append("/")
from core.base.service import BaseService

os.environ["SERVICE_NAME"] = "consul-service"
os.environ["SERVICE_PORT"] = "8500"
os.environ["SERVICE_TAGS"] = "core,infra,discovery,dns"

class Service(BaseService):
    async def run(self):
        self.logger.info("Starting Consul agent subprocess...")
        process = subprocess.Popen(["consul", "agent", "-config-file=/consul/config/consul.hcl"])

        await self.register_in_consul()

        try:
            while True:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            process.terminate()
            self.stop()

if __name__ == "__main__":
    svc = Service()
    asyncio.run(svc.start())
