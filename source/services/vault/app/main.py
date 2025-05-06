# source\services\vault\app\main.py

"""
Speculorg.Terminal - Service Launcher

Template main.py for all services using BaseService.
"""

import sys
import os
import time
import subprocess
import requests

sys.path.append("/")

from core.base.service import BaseService


# ===========================================================
# 🛠 SERVICE INITIALIZATION PARAMETERS
# Set required service identity via environment variables
# These are read by BaseSettings and must be defined early.
# ===========================================================
os.environ["SERVICE_NAME"] = "vault.service"
os.environ["SERVICE_PORT"] = "8200"
os.environ["SERVICE_TAGS"] = "core,infra,security,secrets,provider"


# ===========================================================
# 🧠 SERVICE IMPLEMENTATION
# Derive from BaseService and override run() as needed.
# ===========================================================
class Service(BaseService):
    def run(self):
        try:
            self.logger.info("Starting Vault server subprocess...")
            vault_process = subprocess.Popen([
                "vault", "server", "-config=/vault/config/vault.hcl"
            ])

            time.sleep(5)

            self.logger.info("Running Vault initializer...")
            result = subprocess.run(["python3", "/vault/config/init-vault.py"], capture_output=True)

            if result.stdout:
                self.logger.info(result.stdout.decode())
            if result.stderr:
                self.logger.error(result.stderr.decode())

            # Проверка здоровья
            for i in range(30):
                try:
                    r = requests.get("http://localhost:8200/v1/sys/health")
                    if r.status_code in (200, 429, 501, 503):
                        self.logger.info(f"Vault health: {r.status_code}")
                        break
                    else:
                        self.logger.warning(f"Vault unexpected health: {r.status_code}")
                except Exception as e:
                    self.logger.warning(f"Healthcheck failed: {e}")
                time.sleep(1)

            # Контроль падения vault
            if vault_process.poll() is not None:
                self.logger.error("Vault exited unexpectedly.")
                self.stop()
                return

            self.logger.info("Vault service is running.")
            while True:
                time.sleep(60)

        except Exception as e:
            self.logger.error(f"Failed to start Vault: {e}")
            self.stop()


# ===========================================================
# 🚀 ENTRYPOINT
# ===========================================================
if __name__ == "__main__":
    svc = Service()
    svc.start()
