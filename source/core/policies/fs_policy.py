
from __future__ import annotations
import os, tempfile

class FSPolicy:
    """
    Безопасные операции записи на диск.
    """

    @staticmethod
    def atomic_write(path: str, data: bytes, mode: int = 0o640) -> None:
        d = os.path.dirname(path)
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=d)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.chmod(tmp, mode)
            os.replace(tmp, path)
        finally:
            try:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            except Exception:
                pass
