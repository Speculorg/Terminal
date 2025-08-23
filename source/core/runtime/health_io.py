# source\core\runtime\health_io.py


from __future__ import annotations
import json
from pathlib import Path
from typing import Mapping

def write_health(snapshot: Mapping[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
