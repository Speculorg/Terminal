# source\services\vault\app\main.py

"""
Vault service launcher.

Algorithm:
1. Detect first launch by absence of server certificates.
2. Run Vault once (HTTP), execute init-script, terminate.
3. Run Vault again (HTTPS). Apply Consul registration if certificates exist.
4. Stay alive until SIGTERM/SIGINT.
The code is idempotent and parameters are grouped in CONSTANTS.
"""

from __future__ import annotations

import asyncio
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests  # lightweight probe only

sys.path.append("/")
from core.base.settings import settings          # project-wide configuration
from core.base.service import BaseService        # common async wrapper

# --------------------------------------------------------------------------- #
#                                   CONSTANTS                                 #
# --------------------------------------------------------------------------- #
CERTS_DIR             = Path("/certs")
VAULT_CERT            = CERTS_DIR / "vault.crt"
VAULT_KEY             = CERTS_DIR / "vault.key"
CA_CERT               = CERTS_DIR / "ca.crt"

CFG_HTTP              = "/vault/config/vault_http.hcl"
CFG_HTTPS             = "/vault/config/vault_https.hcl"
INIT_SCRIPT           = Path("/vault/config/init-vault.py")

# Health-check
VAULT_HOST            = settings.VAULT_HOST
VAULT_PORT            = settings.VAULT_PORT

HEALTH_TIMEOUT_SEC    = 15
RESTART_DELAY_SEC     = 60


# --------------------------------------------------------------------------- #
#                               Helper functions                              #
# --------------------------------------------------------------------------- #
def vault_url(path: str, tls: bool) -> str:
    scheme = "https" if tls else "http"
    return f"{scheme}://{VAULT_HOST}:{VAULT_PORT}{path}"


def wait_for_ready(tls: bool, timeout: int = HEALTH_TIMEOUT_SEC) -> bool:
    url = vault_url("/v1/sys/health", tls)
    verify = str(CA_CERT) if tls else False
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=3, verify=verify)
            if r.status_code in (200, 429, 501, 503):
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False


# --------------------------------------------------------------------------- #
#                                 Main service                                #
# --------------------------------------------------------------------------- #
class VaultService(BaseService):

    async def run(self) -> None:                  # noqa: D401
        first_launch = not (VAULT_CERT.exists() and CA_CERT.exists())

        # ---------- first (HTTP) run ---------------------------------------
        if first_launch:
            self._logger.info("This is first launch of Vault")
            if not await self._run_once(use_tls=False):
                return
            
            await self._run_init_script()
            
            time.sleep(RESTART_DELAY_SEC)
            await self._terminate_subprocess()
        else:
            self._logger.info("This is not first launch of Vault") 

        # ---------- normal (TLS) run ---------------------------------------
        if not await self._run_once(use_tls=True):
            return

        # idle loop
        while not self._shutdown_event.is_set():
            await asyncio.sleep(60)

    
    async def _run_once(self, *, use_tls: bool) -> bool:
        cfg_file = CFG_HTTPS if use_tls else CFG_HTTP
        cmd = ["vault", "server", f"-config={cfg_file}"]
        time.sleep(15)
        self._logger.info("Starting Vault (%s)", "TLS" if use_tls else "HTTP")
        proc = subprocess.Popen(cmd)                                    # noqa: S603,S607
        self.set_subprocess(proc)

        loop = asyncio.get_running_loop()
        ready = await loop.run_in_executor(None, wait_for_ready, use_tls)
        if not ready or proc.poll() is not None:
            self._logger.error("Vault failed to start (TLS=%s)", use_tls)
            return False

        self._logger.info("Vault is ready (TLS=%s)", use_tls)
        return True

    
    async def _run_init_script(self) -> None:
        self._logger.info("Executing %s", INIT_SCRIPT.name)
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(                                   # noqa: S603,S607
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

    
    async def after_stop(self) -> None:
        await self._terminate_subprocess()


if __name__ == "__main__":
    asyncio.run(VaultService().start())
