# source\services\consul\app\main.py


from __future__ import annotations

import asyncio
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests

sys.path.append("/")
from core.base.settings import settings
from core.base.service import BaseService


# ───────────────────────── constants ─────────────────────────
SECRETS_DIR             = Path("/consul/secrets")
AGENT_TOKEN_FILE        = SECRETS_DIR / "agent_consul_token"
ROOT_TOKEN_JSON         = SECRETS_DIR / "root_consul_token.json"
INIT_SCRIPT             = Path("/consul/config/init-consul.py")
CONSUL_CMD              = ["consul", "agent", "-config-file=/consul/config/consul.hcl"]
LOCAL_LEADER_URL        = f"http://{settings.CONSUL_HOST}:{settings.CONSUL_PORT}/v1/status/leader"


# ───────────────────────── helpers ───────────────────────────
def wait_for_leader(timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(LOCAL_LEADER_URL, timeout=2)
            if r.ok and r.text and r.text != '""':
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


# ───────────────────────── service ───────────────────────────
class ConsulService(BaseService):

    async def before_run(self) -> None:
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)


    async def run(self) -> None:                         # noqa: D401
        first_launch = not AGENT_TOKEN_FILE.exists()

        # ── initial agent run ───────────────────────────
        if first_launch:
            if not await self._run_consul_once():
                return
            if not await self._run_init_script():
                return
            await self._terminate_subprocess()

        # ── normal agent run ────────────────────────────
        if not await self._run_consul_once():
            return

        await self._apply_agent_token()

        # idle loop
        while not self._shutdown_event.is_set():
            await asyncio.sleep(60)


    # ───────────────────── sub-routines ─────────────────────
    async def _run_consul_once(self) -> bool:
        self._logger.info("Starting service: %s", " ".join(CONSUL_CMD))
        proc = subprocess.Popen(CONSUL_CMD)             # noqa: S603,S607
        self.set_subprocess(proc)

        ready = await asyncio.get_event_loop().run_in_executor(None, wait_for_leader)
        if not ready or proc.poll() is not None:
            self._logger.error("Consul failed to start.")
            return False

        self._logger.info("Leader ready.")
        return True


    async def _run_init_script(self) -> bool:
        self._logger.info("Running %s", INIT_SCRIPT.name)

        result = subprocess.run(["python3", str(INIT_SCRIPT)], capture_output=True)
        
        for ln in result.stdout.splitlines():
            self._logger.info("[init] %s", ln)
        for ln in result.stderr.splitlines():
            self._logger.error("[init] %s", ln)

        ok = result.returncode == 0 and AGENT_TOKEN_FILE.exists() and ROOT_TOKEN_JSON.exists()
        if ok:
            self._logger.info("Bootstrap OK")
        else:
            self._logger.error("Failed bootstrap")
        return ok


    async def _apply_agent_token(self) -> None:
        if not (AGENT_TOKEN_FILE.exists() and ROOT_TOKEN_JSON.exists()):
            self._logger.warning("Token files missing - skip agent-authorization")
            return

        agent_token = AGENT_TOKEN_FILE.read_text().strip()
        mgmt_token  = json.loads(ROOT_TOKEN_JSON.read_text())["SecretID"]

        cmd = [
            "consul", "acl", "set-agent-token",
            "-token", mgmt_token,
            "agent",  agent_token,
        ]
        self._logger.info("Applying agent-token …")
        res = await asyncio.get_event_loop().run_in_executor(
            None, lambda: subprocess.run(cmd, capture_output=True, text=True)
        )
        if res.returncode == 0:
            self._logger.info("OK - agent-token applied")
        else:
            self._logger.error("Failed authorization - agent-token error: %s", res.stderr.strip() or "<no-stderr>")


    async def after_stop(self) -> None:
        await self._terminate_subprocess()


if __name__ == "__main__":
    asyncio.run(ConsulService().start())
