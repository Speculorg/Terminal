
# Журнал изменений (ChangeLog) Speculorg.Terminal (MVP)

---

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
