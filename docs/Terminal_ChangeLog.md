
# Журнал изменений (ChangeLog) Speculorg.Terminal (MVP)

---


## [2025.09.19]: Шлифовка KV-путей

- `source/core/kv/paths.py`:
  - Нормализованы префиксы: marker/…, status/<svc>/status, status/<svc>/heartbeat, certs/*, config/*.
  - Добавлены фабрики для сервисных маркеров (marker_svc_flag), статусов и конфигов.
  - Экспортированы именованные константы для часто используемых ключей: Consul/Vault/Traefik маркеры, CERTS_VERSION, CERTS_CA_PEM, и т.д.
  - Комментарии и чёткая группировка - чтобы не плодились "магические строки" по коду.


## [2025.09.19]: Шлифовка TLS-watch, KV, ACL

- `source/core/runtime/tls/reloaders.py`:
  - CallbackTLSReloader - вызывает произвольный callback на смене версии (используем для Consul → управляемый рестарт).
  - Оставлены и "подчистили" существующие: NoopTLSReloader, ProcSignalTLSReloader (для Traefik - SIGHUP).

- `source/core/base/service.py`:
  - Убран ранний KV-gate до initialize(); теперь KV проверяется после initialize().
  - В _kv_required() добавлен traefik в исключения: {"consul","vault","traefik"}.
  - Это совместимо со всеми сервисами: Consul/Vault стартуют без KV, остальные - либо инжектят KV заранее, либо подключают его в initialize().

- `source/services/consul/app/main.py`:
  - В __init__ сервиса - подключён CallbackTLSReloader, который по смене certs/version вызывает управляемый рестарт (через базовый каркас).
  - Больше никаких прямых вызовов старых probe_tls/probe_https: ждём порт и лидера, а TLS-переход делает watcher+reloader.
  - В POLICIES['traefik'] добавлено право: key_prefix "marker/traefik/" { policy = "write" }.

- `source/services/traefik/app/main.py`:
  - Убрали собственный watch_certs_version_loop и все связанные поля/таски.
  - Настроили self.deps.tls_reloader = ProcSignalTLSReloader("traefik", lambda: self._child, signum=SIGHUP), полностью полагаемся на общий watcher из базового класса.
  - Инициализационный маркер (initialized) - оставили (best-effort).


## [2025.09.18]: KV-sync для статусов/heartbeat

- `source/core/base/service.py`:
  - Добавлен минимальный "ready gate" перед RUNNING (опционально ждать активного TLS: require_tls_for_running).
  - Введён простой контур DEGRADED:
    - degrade(reason) фиксирует деградацию и переводит сервис в DEGRADED (без рестартов).
    - recover(reason) снимает конкретную причину; при отсутствии причин - возврат в RUNNING.
  - В KV при status.update() и heartbeat пишутся агрегированные причины деградации.
  - Логи/метрики скорректированы под новые переходы состояний.
  - Безопасная работа при отсутствии deps.kv сохранилась (ленивое подключение из сервисов).

- `source/core/kv/status.py`:
  - Унифицирована схема KV-статусов:
    - status/<svc>/status - "снимок" (service, phase, state, ts, reasons, degraded, domain).
    - status/<svc>/heartbeat - "пульс" (ts, epoch, expires_at, tls_active, degraded).
  - Реализован TTL по heartbeat через поле expires_at (без серверного TTL).
  - Добавлен get_recent(svc, within_s=None) для проверки "свежести" heartbeat.
  - Все записи делают CAS, где возможно; для heartbeat допускается best-effort без CAS.
  - Совместимость с исходным контрактом kv.status.update()/kv.status.heartbeat() сохранена.

- `source/services/consul/app/main.py`:
  - ACL-policy Traefik дополнена key_prefix "marker/traefik/" { policy = "write" } (для маркера initialized).
  - Убраны некорректные вызовы старого TLS-probe (несовпадение сигнатур), приведение к используемому варианту.
  - Без изменения логики bootstrap/перезапусков.

- `source/services/vault/app/main.py`:
  - В _publish_certs_to_kv поправлены маркеры готовности и порядок публикации: PEM → bundle → version (как триггер)
  - Поправлены импорты и логика initialize

- `source/services/traefik/app/main.py`:
  - Прямой TLS-probe периметра (HTTPS) + установка флага tls_active.
  - Ленивая интеграция с KV (если есть токен) и постановка маркера marker/traefik/initialized.
  - Вотчер certs/version: SIGHUP Traefik ⇒ проверка, что HTTPS снова поднят; одноразовый mTLS-smoke к Consul.
  - При неудачах - degrade("https_reload_failed" | "mtls_to_consul_failed" | "sighup_exception"), при восстановлении - recover(...).
  - Совместимость с базовым каркасом сохранена, регистрация/health остаются без изменений.


## [2025.09.18]: Heartbeat/health в KV + снятие жёсткой зависимости от KV в каркасе
- `source/core/base/service.py` - сделали KV-зависимость ленивой на уровне ContextMicroservice: сервис может стартовать без deps.kv, а сам подключит KV внутри initialize().
- `source/services/consul/app/main.py` - поправлены ACL-политики.
- `source/core/runtime/status.py` - добавлен статус STARTING.


## [2025.09.17]: Watch certs/version → hot-reload & client-TLS refresh для всех трёх сервисов
- `source/core/runtime/tls/version_watch.py` - выносим слежение за certs/version в отдельный переиспользуемый CertsVersionWatcher.
- `source/services/consul/app/main.py` - добавлен единый watcher.
- `source/services/vault/app/main.py` - добавлен единый watcher.
- `source/services/traefik/app/main.py` - добавлен единый watcher, старая локальная watch-логика удалена.


## [2025.09.17]: Клиентский TLS-релоадер
- `source/core/runtime/tls/client_reloader.py` - переиспользуемый клиентский TLS-релоадер, который автоматически подхватывает новые ключи/цепочки по событию certs/version (без рестартов)
- `source/core/runtime/tls/combined_reloader.py` - мультиплексор для нескольких реализаций TLSReloader
- `source/core/net/http/client.py` - синхронная GET-проба к HTTPS-ресурсу с клиентским TLS.
- `source/services/consul/app/main.py` - mTLS-проба + комбинированный релоадер
- `source/services/vault/app/main.py` - mTLS-проба + комбинированный релоадер
- `source/services/traefik/app/main.py` - mTLS-проба + комбинированный релоадер


## [2025.09.17]: Завершение KV-агрегата
- `source/core/kv/markers.py` - реализовали желаемый интерфейс вида KV.marker.consul.initialized и сохранили существующие generic-методы.
- `source/core/kv/configs.py` - глобальные ключи и ключи per-service формируются строго через paths.py (единый нейминг).
- `source/core/kv/certs.py` - ключи certs/* и marker/vault/certs_status формируются строго через paths.py. publish_bundle() синхронно обновляет и JSON-маркер, и "простую" версию (строка), которую уже читает наш TLS-watcher в каркасе сервиса.
- `source/core/base/service.py` - подключили запись маркеров в каркасе ContextMicroservice в правильные фазы.
- Используем фасады KV.marker.svc("<name>").* и специализированные KV.marker.vault.*/KV.marker.consul.*.
- `source/services/<svc>/main.py` - правки:
  - Публикация сертификатов и версии - через KV.cert.*.
  - Для Traefik убран самописный вотчер certs/version: теперь hot-reload делается через каркас (ContextMicroservice следит за certs/version, а мы передаём SignalTLSReloader(pid=...)).
  - Базовый класс сам пишет универсальные маркеры фаз, но у Consul/Vault KV подключается после запуска - потому идемпотентно дублируем нужные маркеры после attach KV (не мешает и не ломает).


## [2025.09.17]: Унификация логирования и метрик в каркасе ContextMicroservice
- `source/core/utils/fs.py` - Содержит функцию read_first_line для безопасного чтения первой строки файла и обрезки пробелов. Возвращает None при любой ошибке. Пригодится в entrypoint-ах сервисов для чтения токенов/путей без дублирования кода.
- `source/core/base/service.py` - добавлены унификация логов + базовые метрики.


## [2025.09.17]: TLS Hot-Reload интерфейс
- `source/core/runtime/tls_reload.py` - TLSReloader, новый интерфейс "горячей" перезагрузки TLS-материалов.
- `source/core/runtime/tls/sslcontext_reloader.py` - TLSReloader, который перечитывает PEM и вызывает переданный "применитель" (setter) нового SSLContext;
- `source/core/runtime/tls/signal_reloader.py` - signal_reloader.py - TLSReloader, который шлёт сигнал процессу (по PID или PID-файлу).
- `source/core/runtime/tls/utils.py` - новый набор для безопасной загрузки PEM и сборки ssl.SSLContext (client/server, с/без mTLS).
- `source/core/base/service.py` - добавлены зависимость tls_reloader, фоновый вотчер версии, вызов hot-reload.


## [2025.09.17]: Пакет-агрегатор core/net
- `source/core/net/__init__.py` - пакет агрегирует реализацию в `core/net/url.py` и делает единый публичный импорт.
- `source/core/base/service.py` - строка импорта `from core.net import build_url, fqdn`.


## [2025.09.16]: Разделение ответственности статусов
- `source/core/kv/status.py` - добавлен метод update(svc, status, meta) - устанавливает phase и status, поддерживая service/ts/meta. Старые методы set_phase и set_status оставлены для плавной миграции.
- `source/core/base/service.py` - вместо двух вызовов kv.status.set_phase(...) и kv.status.set_status(...) теперь один вызов kv.status.update(...).


## [2025.09.16]: Усиление DIP для KV
- `source/core/kv/consul.py` - добавлен агрегатный конструктор build_kv поверх build_consul_kv_from_settings
- `source/core/kv/__init__.py` - добавлен импорт/экспорт build_kv
- `source/core/base/service.py` - добавлен блок _kv_required() и проверка в начале serve()


## [2025.09.16]: Перенос observability в metrics
- `core/observability/metrics.py` - удалён
- `core/metrics/registry.py` - перенесли логику из metrics.py
- `core/metrics/__init.py__` - новый
- `source\core\base\service.py` - перенастроили импорт


## [2025.09.15]: Внедрение KV
- `core/kv`: добавлен агрегат `KV`, адаптер `ConsulKVClient`, фасады `marker`/`status`/`cert`/`config`.
- `core/base/service.py`: публикация `CONFIG_HASH` и `DOMAIN_ROOT` на старте в `config`; фиксация статусов/heartbeat в `status`.
- `services/consul/app/main.py`: публикация `marker/consul/*`; ужаты ACL-политики.
- `services/vault/app/main.py`: чтение/ожидание `marker/consul/mtls_ready`; публикация `certs/*`, `certs/version`, `marker/vault/*`; выпуск fullchain-сертификатов.
- `services/traefik/app/main.py`: чтение/ожидание `marker/vault/pki_leaf_ready`; watcher `certs/version` → `SIGHUP`.
- `core/settings/settings.py`: типобезопасные поля + флаги Consul TLS; временно оставлены плоские свойства для совместимости.


## [2025.09.04]: Реорганизована конфигурация
- Строгая модель конфигурации SETTINGS: settings.env → docker-compose.yml → core/settings/settings.py → код; добавлены производные значения (SAN, CONFIG_HASH), вычищены лишние флаги (*_HTTP_ADDR, tls_enabled).
- Обновлён ContextMicroservice: выровнен под SETTINGS, единые тикеры health/metrics, безопасное завершение, улучшена регистрация через Consul.
- Переписан начальный бутстрап Vault/PKI: параметризованные pki-mounts (root+intermediate), set-signed для intermediate, роль для выдачи листовых, сохранение fullchain; исправлены ошибки валидации цепочки сертификатов.
- Актуализированы main.py для Consul/Vault/Traefik под SETTINGS и схемы bootstrap → initialize → run: управляемый старт процессов, ожидание портов/здоровья/лидерства, переключение на mTLS после бутстрапа.


## [2025.09.01]: Реорганизовано логирование
- Консолидация логирования в единый модуль (`source\core\logging`), базовый класс для унификации форматов, JSON-логер.


## [2025.08.28]: Уточнение BackLog_MVP
- В [TERM-1] внесены уточнения про ядро, базовый класс ContextMicroservice, основные инфраструктурные микросервисы - Consul, Vault, Traefik.


## [2025.08.24]: Рефакторинг каркаса сервиса
- Каркас сервиса:
  - Переименовали и провели рефакторинг BaseService -> ContextMicroservice.
  - ContextMicroservice - теперь это минимальный, чистый контракт.
  - Добавлены статусы (BOOTSTRAPPING, INITIALIZING, SECURING, TLS_TRANSITION, REGISTERING, RUNNING, PAUSED, DEGRADED, STOPPING, ERROR).
  - Жизненный цикл, пробы TLS, порты, JSON-файлы состояния, healthchecks, секреты, регистрация - вынесены в отдельные пакеты (SRP/DIP).
- Core-модули по доменам (runtime, infra, observability, net, settings).
- Настройки:
  - Перенесли и упростили settings.py: основной источник окружения - settings.env, дополнительный - docker-compose.
  - Перенос и выравнивание имён переменных; разделение HTTP/HTTPS портов.
  - Перенесли `.\develop.env` -> `.\settings.env`
- Добавили новый том Docker - rintime для хранения временных данных (healthchecks).
- Упорядочили healthcheck’и: один скрипт /core/runtime/health_check.py для всех контейнеров.
- main.py consul/vault/traefik переписаны под новый скелет службы.
- Удалены init-vault.py и init-consul.py, теперь инициализация это часть каркаса ContextMicroservice с реализацией в main.py конкретного сервиса.


## [2025.08.05]: Запуск docker-compose из корня проекта
- Переименованы и перемещены файлы:
  - `.\configs\debug.env` -> `.\develop.env`
  - `.\configs\docker-compose.yml` -> `.\docker-compose.yml`
- Удалён каталог `configs\`.


## [2025.07.21]: Внедрён взаимный TLS и автоматизировано состояние запуска сервисов
- Сервисы Vault, Consul и Traefik переведены на внутренний взаимный TLS.
- Vault разворачивает собственный PKI (Root CA и leaf certificates).
- Consul переведён на HTTPS (порт 8501) с ACL и mTLS проверкой клиента.
- Traefik подключён к ConsulCatalog через mTLS, статический конфиг traefik.yml переработан (TLS-1.2+).
- Обновлены инициализационные скрипты init-consul.py и init-vault.py - усилена идемпотентность и проверки состояния, параметризованы задержки.


## [2025.07.06]: Vault переведён на Consul backend, унифицированы политики и токены
- Хранилище Vault переключено на Consul Storage backend, выполнены unseal, записаны KV, политики и approle.
- Переработаны политики ACL: отдельная политика регистрации сервисов удалена, её возможности добавлены в стандартные сервисные политики.
- Введена новая переменная окружения CONSUL_HTTP_TOKEN_FILE для унификации работы с токенами.
- Обновлена логика BaseService и docker-compose, удалены устаревшие переменные окружения (CONSUL_TOKEN_FILE, REGISTERING_CONSUL_TOKEN_FILE).


## [2025.06.04]: Автоматизированная инициализация Consul ACL и регистрация сервисов
- Автоматизировано создание ACL-политик и токенов Consul для всех сервисов.
- Инициализация Consul стала идемпотентной, выполняется только при первом запуске.
- Авторизация агента Consul и регистрация сервисов осуществляется через специально созданные ACL-токены.


## [2025.05.25]: Рефакторинг переменных окружения Vault
- Переменная VAULT_ADDR заменена на VAULT_HOST и VAULT_PORT в .env.
- Конструирование адреса Vault теперь происходит динамически в settings.py и init-vault.py.


## [2025.03.16]: Стандартизация регистрации сервисов и оптимизация конфигурации
- Удалены кастомные healthcheck'и в пользу стандартных Docker Healthcheck.
- Регистрация сервисов в Consul стандартизирована (без секции healthcheck).
- Убраны устаревшие переменные окружения CONSUL_TIMEOUT, CONSUL_CHECK_INTERVAL и CONSUL_CHECK_TIMEOUT.


## [2025.02.17]: Удалён суффикс "-service" в именах сервисов
- Упрощены DNS-имена внутри Docker: "consul", "vault", "traefik".
- Обновлены docker-compose.yml, .env и все ссылки на сервисы в исходниках.


## [2025.01.18]: Traefik переведён на 443 (TLS), UI сервисов проксируется
- Стандартный порт Traefik изменён на 443 (TLS), введён entrypoint websecure.
- Реализован доступ к UI сервисов через Traefik по доменам вида *.localhost.
- Конфигурации docker-compose приведены к единому стилю (labels с Host-правилами и entrypoint websecure).


## [2024.12.19]: Внедрено управление жизненным циклом сервисов
- Реализован централизованный graceful shutdown в BaseService.
- Введена корректная обработка сигналов SIGTERM/SIGINT.
- Обеспечено корректное завершение subprocess Vault, Consul, Traefik и healthcheck-сервера.


## [2024.11.20]: Инициализация репозитория
- Создан GitHub-репозиторий `Terminal` в аккаунте Speculorg.
- Инициализирована структура веток: `main`, `release`, `develop`.
- Настроены правила защиты веток: запрет прямых пушей, обязательное ревью для Pull Request.
- Определены правила для feature и bugfix веток.
- Внедрён процесс работы с Pull Request и ревью.

---
