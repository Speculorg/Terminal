# source\services\traefik\app\main.py

import sys
import os
import asyncio
import subprocess

sys.path.append("/")
from core.base.service import BaseService

os.environ["SERVICE_NAME"] = "traefik-service"
os.environ["SERVICE_PORT"] = "9000"
os.environ["SERVICE_TAGS"] = "core,infra,proxy,edge,routing"

class Service(BaseService):
    async def run(self):
        self.logger.info("Starting Traefik process...")
        process = subprocess.Popen(["traefik", "--configFile=/etc/traefik/traefik.yml"])

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
