from __future__ import annotations
import json
import sys
import threading
import traceback
from datetime import datetime
from typing import Any, Dict, TextIO

from .base import Logger


def _timestamp() -> str:
    """Return current local time with timezone in ISO-8601 format."""
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class JsonLogger(Logger):
    """JSON logger writing structured records to stdout or stderr."""

    def __init__(self, service: str | None = None, **default_fields: Any) -> None:
        if service is not None:
            default_fields.setdefault("svc", service)
        self._fields: Dict[str, Any] = dict(default_fields)
        self._lock = threading.Lock()

    def bind(self, **fields: Any) -> "JsonLogger":
        new_fields = dict(self._fields)
        new_fields.update(fields)
        # propagate service field if present
        return JsonLogger(**new_fields)

    def debug(self, msg: str, *args: Any, **fields: Any) -> None:
        self._log("DEBUG", msg, sys.stdout, *args, **fields)

    def info(self, msg: str, *args: Any, **fields: Any) -> None:
        self._log("INFO", msg, sys.stdout, *args, **fields)

    def warning(self, msg: str, *args: Any, **fields: Any) -> None:
        self._log("WARN", msg, sys.stdout, *args, **fields)

    def error(self, msg: str, *args: Any, **fields: Any) -> None:
        self._log("ERROR", msg, sys.stderr, *args, **fields)

    def exception(self, msg: str, *args: Any, **fields: Any) -> None:
        exc_type, exc, _ = sys.exc_info()
        if exc_type and exc:
            fields = {**fields, "exc": f"{exc_type.__name__}: {exc}", "trace": traceback.format_exc()}
        else:
            # If called outside except, still capture current stack trace
            fields = {**fields, "trace": traceback.format_exc()}
        self._log("ERROR", msg, sys.stderr, *args, **fields)

    # Internal helper
    def _log(self, level: str, msg: str, stream: TextIO, *args: Any, **fields: Any) -> None:
        # printf-style formatting when positional args are provided
        if args:
            try:
                msg = msg % args
            except Exception as fmt_err:  # pragma: no cover
                # Fallback: include formatting error details without raising
                msg = f"{msg} | format_error={fmt_err!s} | args={args!r}"

        record: Dict[str, Any] = dict(self._fields)
        # fields from call override defaults
        record.update(fields)
        record["ts"] = _timestamp()
        record["lvl"] = level
        record["msg"] = msg

        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)
        with self._lock:
            stream.write(line + "\n")
            stream.flush()
