from __future__ import annotations
import json, base64
import urllib.request, urllib.error
from typing import Optional, Dict, Tuple
from interfaces import IKV, IConfigs

class ConsulKV(IKV):
    """Минимальная HTTP-реализация IKV для Consul KV API."""
    def __init__(self, cfg: IConfigs) -> None:
        self._host = cfg.consul.host
        self._scheme = "http"  # HTTPS добавим отдельно при необходимости
        self._port = cfg.consul.http_port
        self._token = cfg.context.consul_token
        self._timeout = max(1, int(cfg.kv.request_timeout_ms) // 1000)

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

    # --- low-level read (envelope) ---
    def _read_envelope(self, key: str) -> tuple[int, Optional[bytes]]:
        url = f"{self._base()}/{key}"
        try:
            with self._req(url) as resp:
                body = resp.read()
                arr = json.loads(body.decode("utf-8"))
                if not arr:
                    return 0, None
                obj = arr[0]
                idx = int(obj.get("ModifyIndex", 0))
                val_b64 = obj.get("Value")
                if val_b64 is None:
                    return idx, None
                return idx, base64.b64decode(val_b64)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 0, None
            raise
        except urllib.error.URLError:
            return 0, None

    # --- IKV text ---
    def read_text(self, key: str) -> tuple[int, Optional[str]]:
        idx, raw = self._read_envelope(key)
        if raw is None:
            return idx, None
        try:
            return idx, raw.decode("utf-8")
        except Exception:
            return idx, None

    def put_text(self, key: str, value: str) -> None:
        url = f"{self._base()}/{key}"
        data = value.encode("utf-8")
        with self._req(url, method="PUT", data=data) as resp:
            resp.read()

    def cas_text(self, key: str, value: str, modify_index: int) -> bool:
        url = f"{self._base()}/{key}?cas={modify_index}"
        data = value.encode("utf-8")
        with self._req(url, method="PUT", data=data) as resp:
            body = resp.read().decode("utf-8")
            return body.strip().lower() == "true"

    # --- IKV json ---
    def read_json(self, key: str) -> tuple[int, Optional[Dict]]:
        idx, text = self.read_text(key)
        if text is None:
            return idx, None
        try:
            return idx, json.loads(text)
        except Exception:
            return idx, None

    def put_json(self, key: str, obj: Dict) -> None:
        self.put_text(key, json.dumps(obj, ensure_ascii=False, separators=(',',':')))

    def cas_json(self, key: str, obj: Dict, modify_index: int) -> bool:
        return self.cas_text(key, json.dumps(obj, ensure_ascii=False, separators=(',',':')), modify_index)
