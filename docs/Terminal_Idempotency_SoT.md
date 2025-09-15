
# Идемпотентность и маркеры состояния в Speculorg.Terminal (MVP)

Данный документ описывает идемпотентность и маркеры состояния, предназначенные для управления состоянием сервисов и последовательностью их запуска. Каждая смена состояния сервиса сопровождается записью через фасад `core.kv`, что позволяет повторять операции без нарушения целостности.


## Цели

1. Обеспечить детерминированный запуск сервисов без ручного вмешательства.
2. Исключить повторное выполнение уже завершённых шагов инициализации.
3. Обеспечить единый источник истины (State of Truth, SoT) для состояния системы.


## Общие принципы

- Все сервисы работают с KV только через объект `KV` (никаких прямых HTTP-запросов).
- CAS (check-and-set) и backoff-retry защищают от гонок при записи.
- Префиксы ключей унифицированы:  
  - `marker/*` - маркеры (вехи, идемпотентные факты).  
  - `status/*` - статусы сервисов (живые фазы/heartbeat).  
  - `certs/*` - публичные сертификаты и версия.  
  - `config/*` - несекретные конфигурации.  
- Секреты (токены, пароли, приватные ключи) не хранятся в KV.


## Структура KV

```
marker/consul/initialized
marker/consul/mtls_ready

marker/vault/initialized
marker/vault/pki_root_ready
marker/vault/pki_int_ready
marker/vault/pki_leaf_ready
marker/vault/certs_status        # JSON {version, updated_at, meta}

marker/traefik/initialized

status/<svc>                     # JSON ServiceStatus + heartbeat
certs/ca.crt
certs/<svc>.crt
certs/version
config/global/domain_root
config/global/config_hash
config/<svc>/<option>

```


## Использование в сервисах

- **Consul**
  - После bootstrap: `marker/consul/initialized`.
  - После старта mTLS: `marker/consul/mtls_ready`.
- **Vault**
  - Ждёт `marker/consul/mtls_ready`.
  - После init/unseal: `marker/vault/initialized`.
  - После PKI root/int/leaf: `marker/vault/pki_*`.
  - После публикации certs: обновляет `certs/*` и `marker/vault/certs_status`.
- **Traefik**
  - Ждёт `marker/vault/pki_leaf_ready`.
  - После изменения `certs/version` делает hot reload.


## Формат значений

- Метка-флаг: `{"status":"ok","ts":"2025-09-15T12:34:56Z"}`  
- Ошибка: `{"status":"failed","error":"...","ts":"..."}`  
- Статус сервиса: JSON из `ServiceStatus` + `heartbeat`.


## Работа через KV (Python)

```
from core.kv import KV, build_consul_kv_from_settings, paths
from core.settings.settings import SETTINGS

# подключение
kv = KV(build_consul_kv_from_settings(SETTINGS, token="..."))

# маркер
kv.marker.ensure_true(paths.M_CONSUL_INITIALIZED)

# статус
from core.runtime.status import ServiceStatus
kv.status.set_status("vault", ServiceStatus.RUNNING)

# сертификаты
kv.certs.publish_ca_pem(ca_pem)
kv.certs.publish_bundle({"traefik": pem}, version=42)

# конфиг
kv.configs.set_domain_root(SETTINGS.domain.root)
```


## Для новых сервисов

- Использовать только `KV.marker.*`, `KV.status.*`, `KV.certs.*`, `KV.configs.*`.
- Перед выполнением шага проверять маркер и пропускать уже выполненные действия.
- Все изменения в KV делать идемпотентно, через CAS.