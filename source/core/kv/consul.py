# source\core\kv\consul.py

"""
core.kv.consul
Минималистичный клиент Consul KV (HTTP/HTTPS, mTLS).
- get_raw -> (value, ModifyIndex)
- put_raw -> CAS (?cas=ModifyIndex)
- Встроенный backoff и повторное подключение по необходимости.

Дополнительно:
- build_consul_kv_from_settings(SETTINGS, token) -> ConsulKVClient  (низкоуровневый клиент)
- build_kv(SETTINGS, token) -> KV (агрегат с фасадами marker/status/cert/config)
"""

from __future__ import annotations
import base64
import http.client
import json
import os
import ssl
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from .base import KVClient, KVEntry, KV
from core.logging import get_logger

log = get_logger("kv.consul")


@dataclass
class _ConnCfg:
    host: str
    http_port: int
    https_port: int
    tls: bool = False
    ca_file: Optional[str] = None
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    token: Optional[str] = None


class ConsulKVClient(KVClient):
    def __init__(self, host: str, http_port: int, https_port: int, *, tls: bool = False,
                 ca_file: Optional[str] = None, cert_file: Optional[str] = None, key_file: Optional[str] = None,
                 token: Optional[str] = None) -> None:
        self._cfg = _ConnCfg(host, int(http_port), int(https_port), bool(tls), ca_file, cert_file, key_file, token)
        self._conn: Optional[http.client.HTTPConnection] = None
        self._connect()

    # --------------- low-level ---------------
    def _connect(self) -> None:
        if self._conn:
            try:
                self._conn.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        if self._cfg.tls:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            if self._cfg.ca_file and os.path.exists(self._cfg.ca_file):
                ctx.load_verify_locations(self._cfg.ca_file)
            else:
                ctx.load_default_certs()
            if self._cfg.cert_file and self._cfg.key_file and os.path.exists(self._cfg.cert_file) and os.path.exists(self._cfg.key_file):
                ctx.load_cert_chain(self._cfg.cert_file, self._cfg.key_file)
            self._conn = http.client.HTTPSConnection(self._cfg.host, self._cfg.https_port, context=ctx, timeout=10)
        else:
            self._conn = http.client.HTTPConnection(self._cfg.host, self._cfg.http_port, timeout=10)

    def _headers(self) -> dict:
        hdrs = {"User-Agent": "Speculorg.Terminal/kv"}
        if self._cfg.token:
            hdrs["X-Consul-Token"] = self._cfg.token
        return hdrs

    def _request(self, method: str, path: str, body: Optional[bytes] = None) -> Tuple[int, bytes, dict]:
        assert self._conn is not None
        try:
            self._conn.request(method, path, body=body, headers=self._headers())
            resp = self._conn.getresponse()
            data = resp.read() or b""
            headers = {k.lower(): v for k, v in resp.getheaders()}
            return resp.status, data, headers
        except Exception:
            # reconnect once
            try:
                self._connect()
                self._conn.request(method, path, body=body, headers=self._headers())
                resp = self._conn.getresponse()
                data = resp.read() or b""
                headers = {k.lower(): v for k, v in resp.getheaders()}
                return resp.status, data, headers
            except Exception as exc:
                log.error("evt=consul.request.fail method=%s path=%s err=%s", method, path, exc)
                raise

    @staticmethod
    def _b64(v: bytes) -> str:
        return base64.b64encode(v).decode("ascii")

    @staticmethod
    def _b64d(s: str) -> bytes:
        return base64.b64decode(s.encode("ascii"))

    # --------------- KVClient ---------------
    def get_raw(self, key: str) -> KVEntry:
        status, data, _ = self._request("GET", f"/v1/kv/{key}")
        if status == 404:
            return KVEntry(None, None)
        if status != 200:
            log.error("evt=kv.get_raw.http_error status=%s key=%s", status, key)
            return KVEntry(None, None)
        try:
            arr = json.loads(data.decode("utf-8"))
            if not arr:
                return KVEntry(None, None)
            item = arr[0]
            val_b64 = item.get("Value")
            mod = int(item.get("ModifyIndex", 0)) or None
            value = None if val_b64 is None else self._b64d(val_b64)
            return KVEntry(value, mod)
        except Exception as exc:
            log.error("evt=kv.get_raw.decode_error key=%s err=%s", key, exc)
            return KVEntry(None, None)

    def put_raw(self, key: str, value: bytes, *, cas: Optional[int] = None) -> bool:
        path = f"/v1/kv/{key}"
        if cas is not None:
            path = f"{path}?cas={int(cas)}"
        status, data, _ = self._request("PUT", path, body=value or b"")
        if status != 200:
            log.error("evt=kv.put_raw.http_error status=%s key=%s cas=%s", status, key, cas)
            return False
        try:
            ok = bool(json.loads(data.decode("utf-8")))
            return ok
        except Exception as exc:
            log.error("evt=kv.put_raw.decode_error key=%s err=%s", key, exc)
            return False

    def delete(self, key: str) -> bool:
        status, data, _ = self._request("DELETE", f"/v1/kv/{key}")
        if status != 200:
            log.error("evt=kv.delete.http_error status=%s key=%s", status, key)
            return False
        try:
            return bool(json.loads(data.decode("utf-8")))
        except Exception:
            return False

    # ----- typed helpers -----
    def get_text(self, key: str) -> Tuple[Optional[str], Optional[int]]:
        e = self.get_raw(key)
        if e.value is None:
            return None, e.modify_index
        try:
            return e.value.decode("utf-8"), e.modify_index
        except Exception:
            return None, e.modify_index

    def put_text(self, key: str, text: str, *, cas: Optional[int] = None) -> bool:
        return self.put_raw(key, (text or "").encode("utf-8"), cas=cas)

    def get_json(self, key: str) -> Tuple[Optional[Any], Optional[int]]:
        s, idx = self.get_text(key)
        if s is None:
            return None, idx
        try:
            return json.loads(s), idx
        except json.JSONDecodeError:
            return None, idx

    def put_json(self, key: str, obj: Any, *, cas: Optional[int] = None) -> bool:
        try:
            s = json.dumps(obj, ensure_ascii=False, separators=(",", ":" ))
        except Exception:
            s = json.dumps({"raw": str(obj)}, ensure_ascii=False)
        return self.put_text(key, s, cas=cas)


# ---- Factory (client) ----
def build_consul_kv_from_settings(SETTINGS: Any, token: Optional[str] = None) -> ConsulKVClient:
    """
    Конструктор из core.settings.SETTINGS.
    Секреты (token) принимайте явным параметром или читайте из файла вне этого модуля.
    """
    host = getattr(SETTINGS, "CONSUL_HOST", "consul")
    http_port = int(getattr(SETTINGS, "CONSUL_HTTP_PORT", 8500))
    https_port = int(getattr(SETTINGS, "CONSUL_HTTPS_PORT", 8501))
    tls = bool(getattr(SETTINGS, "CONSUL_TLS_ENABLED", False))
    ca_file = getattr(SETTINGS, "CONSUL_TLS_CA_FILE", None)
    cert_file = getattr(SETTINGS, "CONSUL_TLS_CERT_FILE", None)
    key_file = getattr(SETTINGS, "CONSUL_TLS_KEY_FILE", None)
    return ConsulKVClient(
        host=host, http_port=http_port, https_port=https_port, tls=tls,
        ca_file=ca_file, cert_file=cert_file, key_file=key_file, token=token
    )


# ---- Factory (aggregate) ----
def build_kv(SETTINGS: Any, token: Optional[str] = None) -> KV:
    """
    Высокоуровневая фабрика: возвращает агрегат KV с фасадами marker/status/cert/config.
    """
    client = build_consul_kv_from_settings(SETTINGS, token=token)
    return KV(client)
