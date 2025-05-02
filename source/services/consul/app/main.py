# source\services\consul\app\main.py

import sys
sys.path.append("/")
from core.base.service import BaseService
import subprocess


class ConsulService(BaseService):
    def run(self):
        self.logger.info("Starting Consul agent process...")

        try:
            process = subprocess.Popen([
                "consul", "agent", "-config-file=/consul/config/consul.hcl"
            ])
            process.wait()
        except Exception as e:
            self.logger.error(f"Failed to start consul agent: {e}")
            self.stop()


if __name__ == "__main__":
    svc = ConsulService()
    svc.start()
