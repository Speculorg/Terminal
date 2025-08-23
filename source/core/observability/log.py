# source\core\observability\log.py


from __future__ import annotations
import logging, os, sys
from core.settings.settings import settings

def make_logger(name: str | None = None, level: str | None = None) -> logging.Logger:
    svc = name or os.getenv("SERVICE_NAME") or "service"
    fmt = '{"ts":"%(asctime)s","svc":"' + svc + '","lvl":"%(levelname)s","msg":"%(message)s"}'
    lg = logging.getLogger(svc)
    if not lg.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter(fmt))
        lg.addHandler(h)
    lg.setLevel(getattr(logging, (level or settings.LOG_LEVEL).upper(), logging.INFO))
    return lg
