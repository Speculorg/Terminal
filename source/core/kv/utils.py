# source\core\kv\utils.py

"""
core.kv.utils
Утилиты CAS-обновлений с backoff/retry.
"""

from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Tuple
from core.logging import get_logger

log = get_logger("kv.utils")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sleep_backoff(attempt: int) -> None:
    # 0,1,2,... -> 0.1, 0.2, 0.4, ... capped
    delay = min(1.6 * (2 ** max(attempt - 2, 0)) * 0.1, 3.0)
    time.sleep(delay)


def cas_update_json(
    get_fn: Callable[[], Tuple[Optional[Any], Optional[int]]],
    put_fn: Callable[[Any, Optional[int]], bool],
    update_fn: Callable[[Optional[Any]], Any],
    *,
    tries: int = 10,
) -> bool:
    """
    Универсальный CAS-апдейтер: get->modify_index->put(cas=modify_index) с retry/backoff.
    """
    last_err = None
    for i in range(max(1, tries)):
        try:
            current, idx = get_fn()
            next_obj = update_fn(current)
            if put_fn(next_obj, idx):
                return True
        except Exception as exc:
            last_err = exc
            log.warning("evt=cas.update.error attempt=%d err=%s", i + 1, exc)
        _sleep_backoff(i)
    if last_err:
        log.error("evt=cas.update.fail err=%s", last_err)
    return False


def ensure_bool_marker(
    get_fn: Callable[[], Tuple[Optional[Any], Optional[int]]],
    put_fn: Callable[[Any, Optional[int]], bool],
    *,
    tries: int = 10,
) -> bool:
    """Идемпотентно установить marker=True (если None/False)."""
    def _upd(old: Optional[Any]) -> Any:
        return True if (old is None or old is False) else True
    return cas_update_json(get_fn, put_fn, _upd, tries=tries)
