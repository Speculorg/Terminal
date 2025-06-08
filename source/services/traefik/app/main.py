# source/services/traefik/app/main.py


from __future__ import annotations

import asyncio
import sys
import subprocess

sys.path.append("/")
from core.base.settings import settings
from core.base.service import BaseService

TRAEFIK_CMD = ["traefik", "--configFile=/etc/traefik/traefik.yml"]


class TraefikService(BaseService):

    async def run(self) -> None:                         # noqa: D401
        self._logger.info("Starting service: %s", " ".join(TRAEFIK_CMD))

        proc = subprocess.Popen(TRAEFIK_CMD)            # noqa: S603,S607
        self.set_subprocess(proc)

        await asyncio.sleep(10)
        await self.register_in_consul()

        while not self._shutdown_event.is_set():
            await asyncio.sleep(60)

    async def after_stop(self) -> None:
        await self._terminate_subprocess()


if __name__ == "__main__":
    asyncio.run(TraefikService().start())
