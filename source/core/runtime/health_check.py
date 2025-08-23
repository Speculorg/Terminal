# source\core\runtime\health_check.py


from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path
from typing import Iterable, List


def _parse_paths(env_value: str) -> List[str]:
    """
    Поддерживаем:
      - одиночный путь: "/run/terminal/health/consul.json"
      - список через запятую/точку с запятой/пробел: "a.json,b.json"
      - JSON-массив: '["a.json","b.json"]'
    """
    s = (env_value or "").strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
    # split по распространённым разделителям
    for sep in (",", ";", " "):
        if sep in s:
            return [p.strip() for p in s.split(sep) if p.strip()]
    return [s]


def _fresh_enough(p: Path, max_age_sec: float = 180.0) -> bool:
    """
    Доп. защита: файл здоровья не должен быть слишком старым
    (на случай, если процесс умер, а файл остался).
    """
    try:
        return (time.time() - p.stat().st_mtime) <= max_age_sec
    except Exception:
        return False


def _healthy_doc(doc: dict) -> bool:
    # Базовый контракт: либо status == RUNNING, либо state == "up"
    status = str(doc.get("status", "")).upper()
    state  = str(doc.get("state", "")).lower()
    return status == "RUNNING" or state == "up"


def _check_one(path: str) -> bool:
    try:
        p = Path(path)
        if not p.is_file():
            return False
        if not _fresh_enough(p):
            return False
        doc = json.loads(p.read_text(encoding="utf-8") or "{}")
        return _healthy_doc(doc)
    except Exception:
        return False


def main() -> int:
    paths = _parse_paths(os.getenv("SERVICE_HEALTH_FILE", ""))
    # Если путей нет — считаем unhealthy (конфигурационная ошибка)
    if not paths:
        return 1
    return 0 if any(_check_one(p) for p in paths) else 1


if __name__ == "__main__":
    sys.exit(main())
