# source\services\vault\app\main.py


from __future__ import annotations

import asyncio
import sys
import subprocess
from pathlib import Path

sys.path.append("/")
from core.base.settings import settings
from core.base.service import BaseService

VAULT_CMD   = ["vault", "server", "-config=/vault/config/vault.hcl"]
INIT_SCRIPT = Path("/vault/config/init-vault.py")


class VaultService(BaseService):

    async def before_run(self) -> None: ...


    async def run(self) -> None:                         # noqa: D401
        self._logger.info("Starting service: %s", " ".join(VAULT_CMD))

        await asyncio.sleep(20)

        proc = subprocess.Popen(VAULT_CMD)              # noqa: S603,S607
        self.set_subprocess(proc)

        await asyncio.sleep(10)
        await self._run_init_script()

        await asyncio.sleep(10) 
        await self.register_in_consul()

        while not self._shutdown_event.is_set():
            await asyncio.sleep(60)


    async def _run_init_script(self) -> None:
        self._logger.info("Running %s", INIT_SCRIPT.name)

        result = subprocess.run(["python3", str(INIT_SCRIPT)], capture_output=True)
        
        for ln in result.stdout.splitlines():
            self._logger.info("[init] %s", ln)
        for ln in result.stderr.splitlines():
            self._logger.error("[init] %s", ln)


    async def after_stop(self) -> None: 
        await self._terminate_subprocess()


if __name__ == "__main__":
    asyncio.run(VaultService().start())
