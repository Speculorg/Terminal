# source/core/kv/status.py

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.logging import get_logger
from core.settings.settings import SETTINGS
from core.runtime.status import ServiceStatus

log = get_logger("kv.status")


def _now_epoch() -> float:
    return time.time()


def _now_iso() -> str:
    # Достаточно для телеметрии и человекочитаемых логов
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


def _compute_state(st: ServiceStatus) -> str:
    if st is ServiceStatus.RUNNING:
        return "up"
    if st is ServiceStatus.DEGRADED:
        return "degraded"
    if st in {
        ServiceStatus.BOOTSTRAPPING,
        ServiceStatus.INITIALIZING,
        ServiceStatus.SECURING,
        ServiceStatus.TLS_TRANSITION,
        ServiceStatus.REGISTERING,
    }:
        return "init"
    return "down"


def _key_status(svc: str) -> str:
    return f"status/{svc}/status"


def _key_heartbeat(svc: str) -> str:
    return f"status/{svc}/heartbeat"


@dataclass(slots=True)
class StatusFacade:
    """
    Фасад для работы со статусами и heartbeat в Consul KV (SoT).
    Старается использовать CAS; при отсутствии поддержки в клиенте – best-effort путь.
    """
    _kv: Any  # агрегат KV (core.kv.KV)

    # ----------- Публичный контракт, используемый ContextMicroservice -----------

    def update(self, svc: str, st: ServiceStatus, *, meta: Optional[Dict[str, Any]] = None) -> bool:
        """
        Записать «снимок» статуса сервиса в status/<svc>/status (идемпотентно, CAS-перезапись).
        Поля:
          service, phase, state, ts, reasons, degraded, domain
        """
        meta = meta or {}
        payload = {
            "service": svc,
            "phase": st.value,
            "state": _compute_state(st),
            "ts": _now_iso(),
            "reasons": list(meta.get("reasons") or []),
            "degraded": list(meta.get("degraded") or []),
            "domain": SETTINGS.domain.root,
        }
        key = _key_status(svc)
        return self._cas_upsert_json(key, payload, label="status")

    def heartbeat(
        self,
        svc: str,
        *,
        tls_active: Optional[bool] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Записать heartbeat в status/<svc>/heartbeat.
        Поля:
          service, ts, epoch, expires_at, tls_active, degraded
        TTL реализован полем expires_at (epoch).
        """
        meta = meta or {}
        now = _now_epoch()
        ttl_default = 45.0  # сек; > интервала записи из ContextMicroservice.write_health_every_sec
        ttl = float(getattr(getattr(SETTINGS, "timeouts", object()), "heartbeat_ttl_s", ttl_default))
        payload = {
            "service": svc,
            "ts": _now_iso(),
            "epoch": now,
            "expires_at": now + ttl,
            "tls_active": bool(tls_active) if tls_active is not None else None,
            "degraded": list(meta.get("degraded") or []),
        }
        key = _key_heartbeat(svc)
        # Heartbeat — допускаем best-effort без CAS, если клиент не поддерживает CAS
        ok = self._try_put_json_best_effort(key, payload, cas_preferred=True)
        if not ok:
            log.warning("evt=heartbeat.write.false key=%s", key)
        return ok

    # ----------- Диагностика/чтение -----------

    def get_recent(self, svc: str, within_s: Optional[float] = None) -> Tuple[Optional[Dict[str, Any]], bool, float]:
        """
        Прочитать heartbeat и проверить «свежесть».
        Возвращает: (payload|None, is_recent, age_seconds)
        """
        key = _key_heartbeat(svc)
        obj, _idx = self._try_get_json(key)
        if not isinstance(obj, dict):
            return None, False, float("inf")

        now = _now_epoch()
        epoch = float(obj.get("epoch") or 0.0)
        age = max(0.0, now - epoch) if epoch > 0 else float("inf")

        # within_s по умолчанию = TTL, если он есть; иначе 45с
        ttl_default = 45.0
        ttl = float(obj.get("expires_at", 0.0)) - epoch if epoch > 0 else float(getattr(getattr(SETTINGS, "timeouts", object()), "heartbeat_ttl_s", ttl_default))
        window = float(within_s) if within_s is not None else float(ttl if ttl > 0 else ttl_default)

        is_recent = age <= window
        return obj, is_recent, age

    # ----------- Внутренние утилиты (адаптируются к возможностям клиента) -----------

    def _cas_upsert_json(self, key: str, payload: Dict[str, Any], *, label: str) -> bool:
        """
        CAS-обновление (или создание) JSON по ключу.
        Пробуем публичные методы KV; при их отсутствии — прямой вызов клиента.
        """
        # 1) Попытка через публичный API агрегата
        get_json = getattr(self._kv, "get_json", None)
        put_json = getattr(self._kv, "put_json", None)  # ожидаем сигнатуру put_json(key, obj, cas=?)

        if callable(get_json):
            data, idx = get_json(key)  # type: ignore[misc]
            cas = idx if isinstance(idx, int) else 0
            if callable(put_json):
                try:
                    # предпочтительно CAS
                    try:
                        return bool(put_json(key, payload, cas=cas))  # type: ignore[misc]
                    except TypeError:
                        # реализация без cas-параметра
                        return bool(put_json(key, payload))  # type: ignore[misc]
                except Exception as exc:  # noqa: BLE001
                    log.warning("evt=%s.put_json.fail key=%s err=%s", label, key, exc)

        # 2) Попытка через «сырое» API клиента
        client = getattr(self._kv, "client", None) or getattr(self._kv, "_client", None)
        if client is not None:
            get_raw = getattr(client, "get_raw", None)
            put_raw = getattr(client, "put_raw", None)
            if callable(get_raw) and callable(put_raw):
                try:
                    raw, idx = get_raw(key)  # type: ignore[misc]
                    cas = idx if isinstance(idx, int) else 0
                except Exception:
                    cas = 0  # новой записи допустим cas=0
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                try:
                    return bool(put_raw(key, body, cas=cas))  # type: ignore[misc]
                except TypeError:
                    # у некоторых реализаций put_raw нет cas — делаем best-effort
                    return bool(put_raw(key, body))  # type: ignore[misc]
                except Exception as exc:  # noqa: BLE001
                    log.warning("evt=%s.put_raw.fail key=%s err=%s", label, key, exc)

        # 3) Попытка через общий set_json (если есть)
        set_json = getattr(self._kv, "set_json", None)
        if callable(set_json):
            try:
                return bool(set_json(key, payload))  # type: ignore[misc]
            except Exception as exc:  # noqa: BLE001
                log.warning("evt=%s.set_json.fail key=%s err=%s", label, key, exc)

        return False

    def _try_put_json_best_effort(self, key: str, payload: Dict[str, Any], *, cas_preferred: bool) -> bool:
        """
        Универсальная запись JSON:
          - если есть put_json(cas=...) — используем;
          - если есть put_json(...) без cas — используем;
          - если есть put_raw(cas=...) — используем;
          - если есть put_raw(...) — используем;
          - иначе set_json(...).
        """
        # put_json сначала
        put_json = getattr(self._kv, "put_json", None)
        if callable(put_json):
            if cas_preferred:
                # попытаемся добыть cas
                get_json = getattr(self._kv, "get_json", None)
                cas = 0
                if callable(get_json):
                    try:
                        _d, idx = get_json(key)  # type: ignore[misc]
                        cas = idx if isinstance(idx, int) else 0
                    except Exception:
                        cas = 0
                try:
                    try:
                        return bool(put_json(key, payload, cas=cas))  # type: ignore[misc]
                    except TypeError:
                        return bool(put_json(key, payload))  # type: ignore[misc]
                except Exception as exc:  # noqa: BLE001
                    log.warning("evt=put_json.fail key=%s err=%s", key, exc)
            else:
                try:
                    return bool(put_json(key, payload))  # type: ignore[misc]
                except Exception as exc:  # noqa: BLE001
                    log.warning("evt=put_json.fail key=%s err=%s", key, exc)

        # затем «сырой» клиент
        client = getattr(self._kv, "client", None) or getattr(self._kv, "_client", None)
        if client is not None:
            put_raw = getattr(client, "put_raw", None)
            if callable(put_raw):
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                if cas_preferred:
                    # попытаемся добыть cas
                    get_raw = getattr(client, "get_raw", None)
                    cas = 0
                    if callable(get_raw):
                        try:
                            _raw, idx = get_raw(key)  # type: ignore[misc]
                            cas = idx if isinstance(idx, int) else 0
                        except Exception:
                            cas = 0
                    try:
                        try:
                            return bool(put_raw(key, body, cas=cas))  # type: ignore[misc]
                        except TypeError:
                            return bool(put_raw(key, body))  # type: ignore[misc]
                    except Exception as exc:  # noqa: BLE001
                        log.warning("evt=put_raw.fail key=%s err=%s", key, exc)
                else:
                    try:
                        return bool(put_raw(key, body))  # type: ignore[misc]
                    except Exception as exc:  # noqa: BLE001
                        log.warning("evt=put_raw.fail key=%s err=%s", key, exc)

        # общий set_json как последний шанс
        set_json = getattr(self._kv, "set_json", None)
        if callable(set_json):
            try:
                return bool(set_json(key, payload))  # type: ignore[misc]
            except Exception as exc:  # noqa: BLE001
                log.warning("evt=set_json.fail key=%s err=%s", key, exc)

        return False

    def _try_get_json(self, key: str) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
        """
        Универсальное чтение JSON: get_json(...) или client.get_raw(...).
        Возвращает (obj|None, modify_index|None).
        """
        get_json = getattr(self._kv, "get_json", None)
        if callable(get_json):
            try:
                obj, idx = get_json(key)  # type: ignore[misc]
                if isinstance(obj, (dict, list, str, int, float)) or obj is None:
                    return obj, idx if isinstance(idx, int) else None  # type: ignore[return-value]
            except Exception as exc:  # noqa: BLE001
                log.warning("evt=get_json.fail key=%s err=%s", key, exc)

        client = getattr(self._kv, "client", None) or getattr(self._kv, "_client", None)
        if client is not None:
            get_raw = getattr(client, "get_raw", None)
            if callable(get_raw):
                try:
                    raw, idx = get_raw(key)  # type: ignore[misc]
                    if raw is None:
                        return None, idx if isinstance(idx, int) else None
                    try:
                        obj = json.loads(raw.decode("utf-8"))
                    except Exception:
                        obj = None
                    return obj, idx if isinstance(idx, int) else None
                except Exception as exc:  # noqa: BLE001
                    log.warning("evt=get_raw.fail key=%s err=%s", key, exc)

        return None, None
