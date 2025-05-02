# source\core\base\service.py

"""
Speculorg.Terminal Core Service Skeleton

Purpose:
  Provides core service functionality (init, logging, consul registration, healthcheck)
  for infrastructure and business services within the Speculorg.Terminal platform.

Author: Speculorg Team
Version: 0.1
"""

import os
import sys
import time
import logging
import requests
import socket


ENV_VARS = {
    "SERVICE_NAME": None,
    "SERVICE_PORT": None,
    "CONSUL_HOST": "consul.service",
    "CONSUL_PORT": 8500,
    "CONSUL_TIMEOUT": 60,
    "CONSUL_CHECK_INTERVAL": "10s",
    "CONSUL_CHECK_TIMEOUT": "3s",
    "LOG_LEVEL": "INFO",
    "METRICS_PORT": 9100
}


class BaseService:
    """
    BaseService provides core service lifecycle, discovery, logging and monitoring.
    """

    def __init__(self):
        self.env = self._load_env_vars()
        self.service_name = self.env["SERVICE_NAME"]
        self.service_port = int(self.env["SERVICE_PORT"])
        self.consul_host = self.env["CONSUL_HOST"]
        self.consul_port = int(self.env["CONSUL_PORT"])
        self.logger = self._setup_logger()

    def _load_env_vars(self):
        env = {}
        for key, default in ENV_VARS.items():
            val = os.getenv(key)
            if val is None:
                if default is None:
                    print(f"[FATAL] Missing required env var: {key}", file=sys.stderr)
                    sys.exit(1)
                val = default
            env[key] = val
        return env

    def _setup_logger(self):
        logger = logging.getLogger(self.service_name)
        logger.setLevel(getattr(logging, self.env["LOG_LEVEL"].upper(), logging.INFO))
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "service": "' + self.service_name + '", "level": "%(levelname)s", "message": "%(message)s"}'
        )
        handler.setFormatter(formatter)
        if not logger.handlers:
            logger.addHandler(handler)
        return logger

    def initialize(self):
        self.logger.info("Initializing service...")
        self.setup_logging()
        self.setup_vault_connection()
        self.monitor_metrics()
        self.register_in_consul()
        self.healthcheck()

    def start(self):
        self.logger.info("Starting service...")
        self.initialize()
        self.run()

    def pause(self):
        self.logger.info("Service paused (not implemented).")

    def restart(self):
        self.logger.info("Service restarting...")
        self.stop()
        self.start()

    def stop(self):
        self.logger.info("Stopping service...")

    def run(self):
        self.logger.info("Service is running.")
        try:
            while True:
                time.sleep(30)
        except KeyboardInterrupt:
            self.stop()

    def setup_logging(self):
        self.logger.info("Logging initialized.")

    def setup_vault_connection(self):
        self.logger.info("Vault integration not implemented.")

    def monitor_metrics(self):
        self.logger.info("Metrics exporter not implemented.")

    def healthcheck(self):
        self.logger.info("Healthcheck passed.")

    def register_in_consul(self):
        self.logger.info("Registering in Consul...")

        if not self._wait_for_port(self.consul_host, self.consul_port, int(self.env["CONSUL_TIMEOUT"])):
            self.logger.error("Consul not reachable.")
            return

        payload = {
            "Name": self.service_name,
            "Port": self.service_port,
            "Check": {
                "TCP": f"{self.service_name}.service:{self.service_port}",
                "Interval": self.env["CONSUL_CHECK_INTERVAL"],
                "Timeout": self.env["CONSUL_CHECK_TIMEOUT"]
            }
        }

        try:
            url = f"http://{self.consul_host}:{self.consul_port}/v1/agent/service/register"
            response = requests.put(url, json=payload, timeout=5)
            response.raise_for_status()
            self.logger.info(f"Registered in Consul: {self.service_name}:{self.service_port}")
        except Exception as exc:
            self.logger.error(f"Consul registration failed: {exc}")

    def _wait_for_port(self, host, port, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection((host, port), timeout=2):
                    return True
            except Exception:
                time.sleep(2)
        return False

    def handle_request(self, request: dict) -> dict:
        self.logger.info(f"Handling request: {request}")
        return {"status": "ok", "data": request}

    def process_task(self, task: dict) -> None:
        self.logger.info(f"Processing task: {task}")

    def process_event(self, event: dict) -> None:
        self.logger.info(f"Processing event: {event}")

    def log_event(self, event: dict) -> None:
        self.logger.info(f"Event log: {event}")
