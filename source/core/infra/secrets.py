# source\core\infra\secrets.py


from __future__ import annotations
import os
from pathlib import Path

def read_token_from_envfile(env_name: str) -> str:
    path = os.getenv(env_name, "")
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception:
        return ""
