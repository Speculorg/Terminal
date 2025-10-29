from __future__ import annotations
from entities.state_enum import StateEnum

import json, urllib.request, urllib.error
def _http_json(url: str, method: str = "GET", headers: dict | None = None, body: dict | None = None, timeout: int = 5) -> dict:
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    for k,v in (headers or {}).items():
        req.add_header(k, v)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

# === data from schema.py ===
from __future__ import annotations
CONSUL_TOKEN_FILENAME: str = "consul_token_for_traefik"

def on_initializing(cfg, logger, fs, markers, net):
    logger.info('init.traefik.nop', svc=cfg.context.name, details={})
    return StateEnum.SECURING