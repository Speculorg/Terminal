# source\core\infra\registrars\base.py


from __future__ import annotations
from abc import ABC, abstractmethod

class Registrar(ABC):
    @abstractmethod
    async def register(self) -> None: ...
    @abstractmethod
    async def deregister(self) -> None: ...
