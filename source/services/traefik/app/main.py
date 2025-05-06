# source\services\traefik\app\main.py

"""
Speculorg.Terminal - Service Launcher

Template main.py for all services using BaseService.
"""

import sys
import os
import time

sys.path.append("/")

from core.base.service import BaseService


# ===========================================================
# 🛠 SERVICE INITIALIZATION PARAMETERS
# Set required service identity via environment variables
# These are read by BaseSettings and must be defined early.
# ===========================================================
os.environ["SERVICE_NAME"] = "traefik.service"
os.environ["SERVICE_PORT"] = "9000"
os.environ["SERVICE_TAGS"] = "core,infra,proxy,edge,routing"


# ===========================================================
# 🧠 SERVICE IMPLEMENTATION
# Derive from BaseService and override run() as needed.
# ===========================================================
class Service(BaseService):
    def run(self):
        self.logger.info("Starting Traefik process...")

        import subprocess
        try:
            process = subprocess.Popen([
                "traefik", "--configFile=/etc/traefik/traefik.yml"
            ])
            process.wait()
        except Exception as e:
            self.logger.error(f"Failed to start Traefik: {e}")
            self.stop()


# ===========================================================
# 🚀 ENTRYPOINT
# ===========================================================
if __name__ == "__main__":
    svc = Service()
    svc.start()
