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
CONSUL_ENDPOINT = f"{settings.CONSUL_HOST}:{settings.CONSUL_PORT}"
LEADER_PATH = "/v1/status/leader"


# ───────────────────────── helpers ───────────────────────────

def wait_for_leader(url: str, ca: str, client_cert: str, client_key: str, timeout: int = 60) -> bool:
    deadline = time.time() + timeout
    last_exc = None
    while time.time() < deadline:
        try:
            r = requests.get(
                url,
                verify=ca,
                cert=(client_cert, client_key),
                timeout=2,
            )
            if r.ok and r.text and r.text != '""':
                return True
        except Exception as e:
            last_exc = e
        time.sleep(1)
    print(f"wait_for_leader: timeout, last_status=EXC, last_text={last_exc}")
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
            self._logger.info("Run the restart command ...")
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
        CFG_HTTP  = "/consul/config/consul_http.hcl"
        CFG_HTTPS = "/consul/config/consul_https.hcl"

        CERTS_OK = (
            Path("/certs/consul.crt").exists() and
            Path("/certs/consul.key").exists() and
            Path("/certs/ca.crt").exists()
        )

        if CERTS_OK:
            scheme = "https"
            port = 8501
            verify = "/certs/ca.crt"
            cert = "/certs/consul.crt"
            key  = "/certs/consul.key"
            cfg_file   = CFG_HTTPS
            self._logger.info("Certs OK - using HTTPS")
        else:
            scheme = "http"
            port = 8500
            verify = False
            cert = None
            key = None
            cfg_file   = CFG_HTTP
            self._logger.info("Certs missing - using HTTP")

        consul_cmd = ["consul", "agent", f"-config-file={cfg_file}"]
        self._logger.info("Starting service: %s", " ".join(consul_cmd))

        proc = subprocess.Popen(consul_cmd)     # noqa: S603,S607
        self.set_subprocess(proc)

        await asyncio.sleep(30) 

        loop = asyncio.get_running_loop()

        leader_url = f"{scheme}://consul:{port}/v1/status/leader"
        ready = await loop.run_in_executor(None, wait_for_leader, leader_url, verify, cert, key)
        if not ready or proc.poll() is not None:
            self._logger.error(
                f"Consul failed to start. Leader not detected by {leader_url}"
            )
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
