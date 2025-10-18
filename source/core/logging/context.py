from __future__ import annotations
import os
import re
import uuid
from dataclasses import dataclass
from typing import Optional
from interfaces import IConfigs

_UUID_RE = re.compile(r"^[a-fA-F0-9-]{8,36}$")

@dataclass(frozen=True)
class LogContext:
    svc: str
    state: Optional[str]
    correlation_id: str
    trace_id: Optional[str]

    @staticmethod
    def build(cfg: IConfigs, *, state: Optional[str] = None,
              correlation_id: Optional[str] = None,
              trace_id: Optional[str] = None) -> "LogContext":
        hdr = getattr(cfg.logging, "correlation_id_header", "X-Request-ID")
        cid = correlation_id or os.environ.get(hdr, "") or ""
        if not cid or not _UUID_RE.match(cid):
            cid = str(uuid.uuid4())
        max_len = int(getattr(cfg.logging, "correlation_id_len_max", 64))
        if len(cid) > max_len:
            cid = cid[:max_len]
        return LogContext(
            svc=cfg.context.name,
            state=state,
            correlation_id=cid,
            trace_id=trace_id,
        )
