# source/services/vault/app/main.py

import sys
import os
import asyncio
import subprocess

sys.path.append("/")
from core.base.service import BaseService

os.environ["SERVICE_NAME"] = "vault-service"
os.environ["SERVICE_PORT"] = "8200"
os.environ["SERVICE_TAGS"] = "core,infra,secrets"

class Service(BaseService):
    async def run(self):
        self.logger.info("Starting Vault subprocess...")
        process = subprocess.Popen(["vault", "server", "-config=/vault/config/vault.hcl"])
        self.set_subprocess(process)

        await asyncio.sleep(10)
        self.logger.info("Running Vault initializer...")
        result = subprocess.run(["python3", "/vault/config/init-vault.py"], capture_output=True)
        if result.stdout:
            for line in result.stdout.decode().splitlines():
                self.logger.info(f"[init-vault] {line}")
        if result.stderr:
            for line in result.stderr.decode().splitlines():
                self.logger.error(f"[init-vault] {line}")

        await self.register_in_consul()

        if process.poll() is not None:
            self.logger.error("Vault startup error.")
            await self.stop()
            return

        self.healthy = True
        self.logger.info("Vault service is running.")
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
