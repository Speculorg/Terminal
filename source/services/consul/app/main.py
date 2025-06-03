# source\services\consul\app\main.py


"""
Consul service starter.
"""


from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests

sys.path.append("/")
from core.base.service import BaseService


# ─────────────────────────── paths & const ──────────────────────────
os.environ.setdefault("SERVICE_NAME", "consul")
os.environ.setdefault("SERVICE_PORT", "8500")
os.environ.setdefault("SERVICE_TAGS", "core,infra,dns,discovery")
SECRETS_DIR = Path("/consul/secrets")
SECRETS_DIR.mkdir(parents=True, exist_ok=True)
AGENT_TOKEN_FILE = SECRETS_DIR / "agent_consul_token"
ROOT_TOKEN_JSON = SECRETS_DIR / "root_consul_token.json"


# ─────────────────────────── helpers ────────────────────────────────
def _wait_for_leader(host: str = "localhost", port: int = 8500, timeout: int = 30) -> bool:
    """Waits for the Consul leader to be ready."""
    deadline = time.time() + timeout
    url = f"http://{host}:{port}/v1/status/leader"
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.ok and r.text and r.text != '""':
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


class Service(BaseService):

    # ───────────────────────── orchestration ─────────────────────────
    async def run(self) -> None:
        """Main service loop."""
        first_launch = not AGENT_TOKEN_FILE.exists()

        # first agent launch
        if first_launch:
            self.logger.info("First launch detected → bootstrap phase")
            if not await self._run_consul_once():
                return
            if not await self._run_init_consul():
                return
            await self._stop_subprocess()

        # second (working) agent launch
        if not await self._run_consul_once():
            return

        # explicit agent token authorization
        await self._authorize_agent_token()

        self.logger.info("Consul agent is up - idle loop")
        try:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(60)
        finally:
            await self.stop()


    # ───────────────────────── sub-helpers ───────────────────────────
    async def _run_consul_once(self) -> bool:
        """Runs the Consul agent once."""
        cmd = ["consul", "agent", "-config-file=/consul/config/consul.hcl"]
        self.logger.info("Starting Consul: %s", " ".join(cmd))

        proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
        self.set_subprocess(proc)

        ready = await asyncio.get_event_loop().run_in_executor(None, _wait_for_leader)
        if not ready or proc.poll() is not None:
            self.logger.error("Consul failed to start (ready=%s, exit=%s)", ready, proc.poll())
            return False

        self.logger.info("Consul leader ready")
        return True


    async def _run_init_consul(self) -> bool:
        """Runs the bootstrap script."""
        self.logger.info("Running init-consul.py …")
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                ["python3", "/consul/config/init-consul.py"],
                capture_output=True,
                text=True,
            ),
        )
        for line in res.stdout.splitlines():
            self.logger.info("[init-consul] %s", line)
        for line in res.stderr.splitlines():
            self.logger.error("[init-consul] %s", line)

        ok = res.returncode == 0 and AGENT_TOKEN_FILE.exists() and ROOT_TOKEN_JSON.exists()
        if not ok:
            self.logger.error("init-consul failed (code=%s)", res.returncode)
        return ok


    async def _authorize_agent_token(self) -> None:
        """Executes `consul acl set-agent-token agent <SecretID>`."""
        if not (AGENT_TOKEN_FILE.exists() and ROOT_TOKEN_JSON.exists()):
            self.logger.error("Token files not found → skip agent authorization")
            return

        agent_secret = AGENT_TOKEN_FILE.read_text().strip()
        try:
            mgmt_secret = json.loads(ROOT_TOKEN_JSON.read_text())["SecretID"]
        except Exception as exc:
            self.logger.error("Cannot read root token: %s", exc)
            return

        env = os.environ.copy()

        cmd = [
            "consul", "acl", "set-agent-token",
            "-token", mgmt_secret,
            "agent", agent_secret,
        ]

        self.logger.info("Authorizing Consul agent token …")

        res = await asyncio.get_event_loop().run_in_executor(
            None, lambda: subprocess.run(cmd, env=env, capture_output=True, text=True)
        )

        if res.returncode == 0:
            self.logger.info("Agent token applied successfully.")
        else:
            self.logger.error("set-agent-token failed (%s): %s", res.returncode, res.stderr.strip() or "<no stderr>")


    async def _stop_subprocess(self) -> None:
        """Correctly stopping a running consul-agent."""
        if self._subprocess and self._subprocess.poll() is None:
            self.logger.info("Stopping first Consul instance …")
            self._subprocess.send_signal(signal.SIGINT)
            try:
                await asyncio.get_event_loop().run_in_executor(None, self._subprocess.wait, 10)
                self.logger.info("Consul stopped")
            except Exception:
                self.logger.warning("Consul didn`t stop in time → killing")
                self._subprocess.kill()
        self.set_subprocess(None)


if __name__ == "__main__":
    asyncio.run(Service().start())
