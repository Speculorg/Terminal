#!/usr/bin/env python3
"""
register_in_consul.py
~~~~~~~~~~~~~~~~~~~~~
Registers the current container as a service in Consul using the
environment variables:

  SERVICE_NAME   – logical name of the service
  SERVICE_PORT   – container port to expose
  CONSUL_HOST    – consul agent host  (default: 'consul.service')
  CONSUL_PORT    – consul agent port  (default: 8500)

The script tries indefinitely until Consul becomes reachable.
Designed to be launched from Docker ENTRYPOINT or as a side-car.
"""

import json
import os
import socket
import sys
import time
from typing import Dict

import requests

# ----------------------------------------------------------------------
CONSUL_HOST = os.getenv("CONSUL_HOST", "consul.service")
CONSUL_PORT = int(os.getenv("CONSUL_PORT", 8500))
CONSUL_URL = f"http://{CONSUL_HOST}:{CONSUL_PORT}/v1/agent/service/register"

SERVICE_NAME = os.getenv("SERVICE_NAME")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "0"))
SERVICE_TAGS = [tag.strip() for tag in os.getenv("SERVICE_TAGS", "").split(",") if tag]

if not SERVICE_NAME or SERVICE_PORT == 0:
    print("SERVICE_NAME and SERVICE_PORT must be set", file=sys.stderr)
    sys.exit(1)


def wait_for_consul(host: str, port: int, timeout: int = 60) -> None:
    """Wait until Consul agent port is open."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(2)
    print("Consul agent is not reachable", file=sys.stderr)
    sys.exit(2)


def register(payload: Dict) -> None:
    """POST /v1/agent/service/register"""
    try:
        response = requests.put(CONSUL_URL, data=json.dumps(payload), timeout=5)
        response.raise_for_status()
        print(f"[CONSUL] Service registered: {SERVICE_NAME}:{SERVICE_PORT}")
    except Exception as exc:
        print(f"[CONSUL] Registration failed: {exc}", file=sys.stderr)
        sys.exit(3)


def main() -> None:
    wait_for_consul(CONSUL_HOST, CONSUL_PORT)

    payload = {
        "Name": SERVICE_NAME,
        "Port": SERVICE_PORT,
        "Tags": SERVICE_TAGS,
        "Check": {
            "TCP": f"{SERVICE_NAME}.service:{SERVICE_PORT}",
            "Interval": "10s",
            "Timeout": "3s"
        }
    }
    register(payload)


if __name__ == "__main__":
    main()
