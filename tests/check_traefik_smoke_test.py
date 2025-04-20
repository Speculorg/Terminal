#!/usr/bin/env python3
"""
smoke_test_traefik.py

Smoke tests for Traefik in Speculorg.Terminal setup.
Checks:
 1. Container 'traefik.service' is running.
 2. HTTP GET http://localhost:9000/dashboard/ returns 200.
 3. HTTP GET http://localhost:9000/api/rawdata returns valid JSON.
"""

import sys
import time

try:
    import docker
except ImportError:
    print("Please install docker SDK: pip install docker", file=sys.stderr)
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Please install requests: pip install requests", file=sys.stderr)
    sys.exit(1)


def check_container_running(name: str, timeout: int = 30) -> bool:
    client = docker.from_env()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            c = client.containers.get(name)
            if c.status == "running":
                print(f"[OK] Container '{name}' is running.")
                return True
            else:
                print(f"[WAIT] Container '{name}' status: {c.status}")
        except docker.errors.NotFound:
            print(f"[WAIT] Container '{name}' not found yet.")
        time.sleep(2)
    print(f"[FAIL] Container '{name}' did not reach 'running' status within {timeout}s.")
    return False


def check_http_status(url: str, expected: int = 200, timeout: int = 10) -> bool:
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == expected:
            print(f"[OK] {url} returned status {r.status_code}.")
            return True
        else:
            print(f"[FAIL] {url} returned status {r.status_code}, expected {expected}.")
            return False
    except Exception as e:
        print(f"[FAIL] Error requesting {url}: {e}")
        return False


def check_json_endpoint(url: str, timeout: int = 10) -> bool:
    try:
        r = requests.get(url, timeout=timeout)
        data = r.json()  # may raise
        print(f"[OK] {url} returned valid JSON ({type(data).__name__}).")
        return True
    except Exception as e:
        print(f"[FAIL] Invalid JSON from {url}: {e}")
        return False


def main():
    all_ok = True

    # 1. Traefik container
    if not check_container_running("traefik.service"):
        all_ok = False

    # 2. Dashboard UI
    if not check_http_status("http://localhost:9000/dashboard/"):
        all_ok = False

    # 3. Rawdata API
    if not check_json_endpoint("http://localhost:9000/api/rawdata"):
        all_ok = False

    if all_ok:
        print("\nSMOKE TESTS PASSED ✓")
        sys.exit(0)
    else:
        print("\nSMOKE TESTS FAILED ✗", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
