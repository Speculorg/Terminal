from __future__ import annotations
import json, base64
import urllib.request, urllib.error
from typing import Optional, Dict, Tuple

from interfaces.i_kv import IKV

class ConsulKV(IKV):
    """IKV через HTTP API Consul KV.
    - базовый URL: http(s)://{host}:{port}/v1/kv
    - токен: X-Consul-Token, считывается из cfg.context.consul_token (если путь задан)
    - timeout: cfg.kv.request_timeout_ms (мс)
    """
    def __init__(self, cfg, *, scheme: str | None = None) -> None:
        self._host = cfg.consul.host
        self._port = cfg.consul.http_port
        self._timeout = int(getattr(cfg.kv, "request_timeout_ms", 5000)) / 1000.0
        self._scheme = scheme or "http"
        token_path = getattr(cfg.context, "consul_token", "") or ""
        token_value = ""
        if token_path:
            try:
                with open(token_path, "r", encoding="utf-8") as f:
                    token_value = f.read().strip()
            except FileNotFoundError:
                token_value = ""
        self._token = token_value

    # --- helpers ---
    def _base(self) -> str:
        return f"{self._scheme}://{self._host}:{self._port}/v1/kv"

    def _headers(self) -> dict:
        h = {"User-Agent": "Speculorg.Terminal/kv"}
        if self._token:
            h["X-Consul-Token"] = self._token
        return h

    def _req(self, url: str, method: str = "GET", data: bytes | None = None):
        req = urllib.request.Request(url, data=data, method=method, headers=self._headers())
        return urllib.request.urlopen(req, timeout=self._timeout)

    # --- low-level read (json envelope) ---
    def _read_envelope(self, key: str) -> tuple[int, Optional[bytes]]:
        url = f"{self._base()}/{key}"
        try:
            with self._req(url) as resp:
                body = resp.read()
                arr = json.loads(body.decode("utf-8"))
                if not arr:
                    return 0, None
                obj = arr[0]
                idx = int(obj.get("ModifyIndex", 0) or 0)
                val_b64 = obj.get("Value")
                if val_b64 is None:
                    return idx, None
                raw = base64.b64decode(val_b64) if val_b64 else b""
                return idx, raw
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 0, None
            raise

    # --- IKV: text ---
    def read_text(self, key: str) -> tuple[int, Optional[str]]:
        idx, raw = self._read_envelope(key)
        if raw is None:
            return idx, None
        return idx, raw.decode("utf-8")

    def put_text(self, key: str, value: str) -> None:
        data = value.encode("utf-8")
        url = f"{self._base()}/{key}"
        with self._req(url, method="PUT", data=data) as resp:
            resp.read()

    def cas_text(self, key: str, value: str, modify_index: int) -> bool:
        url = f"{self._base()}/{key}?cas={modify_index}"
        data = value.encode("utf-8")
        with self._req(url, method="PUT", data=data) as resp:
            body = resp.read()
            try:
                return bool(json.loads(body.decode("utf-8")))
            except json.JSONDecodeError:
                return body.strip().lower() == b"true"

    # --- IKV: json ---
    def read_json(self, key: str):
        idx, text = self.read_text(key)
        if text is None or text == "":
            return idx, None
        try:
            return idx, json.loads(text)
        except json.JSONDecodeError:
            return idx, None

    def put_json(self, key: str, obj: Dict) -> None:
        self.put_text(key, json.dumps(obj, separators=(",", ":"), ensure_ascii=False))

    def cas_json(self, key: str, obj: Dict, modify_index: int) -> bool:
        return self.cas_text(key, json.dumps(obj, separators=(",", ":"), ensure_ascii=False), modify_index)
