# source\services\consul\app\main.py


from __future__ import annotations
import asyncio
import json
import signal
import subprocess
import sys
import time
import requests
from pathlib import Path
sys.path.append("/")
from core.base.settings import settings
from core.base.service import BaseService

# --------------------------------------------------------------------------- #
#                                   Constants                                 #
# --------------------------------------------------------------------------- #
CERTS_DIR              = Path("/certs")
CONSUL_CERT            = CERTS_DIR / "consul.crt"
CONSUL_KEY             = CERTS_DIR / "consul.key"
CA_CERT                = CERTS_DIR / "ca.crt"

CFG_HTTP               = "/consul/config/consul_http.hcl"
CFG_HTTPS              = "/consul/config/consul_https.hcl"
INIT_SCRIPT            = Path("/consul/config/init-consul.py")

SECRETS_DIR            = Path("/consul/secrets")
AGENT_TOKEN_FILE       = SECRETS_DIR / "agent_consul_token"
ROOT_TOKEN_JSON        = SECRETS_DIR / "root_consul_token.json"

CONSUL_HOST            = settings.CONSUL_HOST
CONSUL_PORT            = settings.CONSUL_PORT

HEALTH_TIMEOUT_SEC     = 15
RESTART_DELAY_SEC      = 60

# --------------------------------------------------------------------------- #
#                               Helpers                                       #
# --------------------------------------------------------------------------- #
def consul_url(tls: bool) -> str:
    scheme = "https" if tls else "http"
    port   = 8501 if tls else 8500
    return f"{scheme}://{CONSUL_HOST}:{port}/v1/status/leader"


def wait_for_ready(tls: bool, timeout: int = HEALTH_TIMEOUT_SEC) -> bool:
    url     = consul_url(tls)
    verify  = str(CA_CERT) if tls else False
    cert    = (str(CONSUL_CERT), str(CONSUL_KEY)) if tls else None
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=3, verify=verify, cert=cert)
            if r.ok and r.text and r.text != '""':
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False


def tls_ready() -> bool:
    return CONSUL_CERT.exists() and CONSUL_KEY.exists() and CA_CERT.exists()


# --------------------------------------------------------------------------- #
#                                 Main service                                #
# --------------------------------------------------------------------------- #
class ConsulService(BaseService):

    async def run(self) -> None:                     # noqa: D401
        first_launch = not AGENT_TOKEN_FILE.exists()

        # ---------- initial HTTP run --------------------------------------
        if first_launch:            
            self._logger.info("This is first launch of Consul")
            if not await self._run_once(use_tls=False):
                return
            
            await self._run_init_script()

            time.sleep(RESTART_DELAY_SEC)
            await self._terminate_subprocess()
        else:
            self._logger.info("This is not first launch of Consul") 

        # ---------- normal run (TLS если есть) ----------------------------
        use_tls_now = tls_ready()
        if not await self._run_once(use_tls=use_tls_now):
            return

        await self._apply_agent_token()

        # idle loop
        while not self._shutdown_event.is_set():
            await asyncio.sleep(60)


    async def _run_once(self, *, use_tls: bool) -> bool:
        cfg_file = CFG_HTTPS if use_tls else CFG_HTTP
        cmd      = ["consul", "agent", f"-config-file={cfg_file}"]

        mode = "TLS" if use_tls else "HTTP"
        self._logger.info("Starting Consul (%s)", mode)
        proc = subprocess.Popen(cmd) # noqa: S603,S607
        self.set_subprocess(proc)

        loop  = asyncio.get_running_loop()
        ready = await loop.run_in_executor(None, wait_for_ready, use_tls)
        if not ready or proc.poll() is not None:
            self._logger.error("Consul failed to start (%s)", mode)
            return False

        self._logger.info("Leader ready (%s)", mode)
        return True


    async def _run_init_script(self) -> None:
        self._logger.info("Executing %s", INIT_SCRIPT.name)
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run( # noqa: S603,S607
                ["python3", str(INIT_SCRIPT)],
                capture_output=True,
                text=True,
            ),
        )
        for line in res.stdout.splitlines():
            self._logger.info("[init] %s", line)
        for line in res.stderr.splitlines():
            self._logger.error("[init] %s", line)
        if res.returncode != 0:
            self._logger.error("Init script returned non-zero code %s", res.returncode)


    async def _apply_agent_token(self) -> None:
        if not (AGENT_TOKEN_FILE.exists() and ROOT_TOKEN_JSON.exists()):
            self._logger.warning("Token files missing — skip set-agent-token")
            return

        agent_token = AGENT_TOKEN_FILE.read_text().strip()
        mgmt_token  = json.loads(ROOT_TOKEN_JSON.read_text())["SecretID"]

        cmd = [
            "consul", "acl", "set-agent-token",
            "-token", mgmt_token,
            "agent",  agent_token,
        ]
        self._logger.info("Applying agent token")
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(cmd, capture_output=True, text=True),
        )
        if res.returncode == 0:
            self._logger.info("Agent token applied successfully")
        else:
            self._logger.error("set-agent-token error: %s", res.stderr.strip() or "<no-stderr>")


    async def after_stop(self) -> None:
        await self._terminate_subprocess()


if __name__ == "__main__":
    asyncio.run(ConsulService().start())
