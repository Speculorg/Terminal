# Стек технологий Speculorg.Terminal

Система **Speculorg.Terminal** построена на современных технологиях и инструментах, обеспечивающих высокую производительность, гибкость и масштабируемость.

Выбор технологий продиктован необходимостью обработки больших объёмов данных в реальном времени, интеграции с внешними сервисами и обеспечения надёжной работы системы.

Ниже представлены основные компоненты технологического стека Speculorg.Terminal:

---

## Язык программирования

- **Python 3.13.1**: Основной язык разработки, используемый для реализации микросервисов, бизнес-логики, интеграций и аналитических инструментов.
    - Сайт: [python.org](https://www.python.org/)
    - GitHub: [python/cpython](https://github.com/python/cpython)

---

## Фреймворки и библиотеки

- **Django 5.1.8**: Фреймворк для реализации микросервисов контекстов (ContextMicroservice), обеспечивающий управление бизнес-логикой и данными.
    - Сайт: [django.com](https://www.djangoproject.com/)
    - GitHub: [django/django](https://github.com/django/django)

- **FastAPI 0.115.12**: Фреймворк для реализации микросервисов контекстов (ContextMicroservice) и адаптеров внешних сервисов (ExternalServiceAdapter).
    - Сайт: [fastapi.tiangolo.com](https://fastapi.tiangolo.com/)
    - GitHub: [tiangolo/fastapi](https://github.com/tiangolo/fastapi)

- **Celery 5.3.1**: Библиотека для реализации асинхронных задач и распределённой обработки.
    - Сайт: [celeryproject.org](https://docs.celeryq.dev/en/stable/)
    - GitHub: [celery/celery](https://github.com/celery/celery)

- **Keycloak 26.1.3**: Система управления идентификацией и доступом (IAM) для аутентификации и авторизации пользователей.
    - Сайт: [keycloak.org](https://www.keycloak.org/)
    - GitHub: [keycloak/keycloak](https://github.com/keycloak/keycloak)

---

## Хранение данных

- **PostgreSQL 17.4**: Реляционная база данных для хранения основной информации.
    - Сайт: [postgresql.org](https://www.postgresql.org/)
    - GitHub: [postgres/postgres](https://github.com/postgres/postgres)

- **TimescaleDB 2.19.0**: База данных для хранения временных рядов.
    - Сайт: [timescale.com](https://www.timescale.com/)
    - GitHub: [timescale/timescaledb](https://github.com/timescale/timescaledb)
    - *Примечание:* PostgreSQL 17.4 и TimescaleDB 2.19.0 протестированы на совместимость.

- **Redis 7.0**: Система кэширования данных в памяти и брокер сообщений для Celery.
    - Сайт: [redis.io](https://redis.io/)
    - GitHub: [redis/redis](https://github.com/redis/redis)

---

## Очереди сообщений и брокеры

- **RabbitMQ 4.0.7**: Брокер сообщений для асинхронного взаимодействия между микросервисами.
    - Сайт: [rabbitmq.com](https://www.rabbitmq.com/)
    - GitHub: [rabbitmq/rabbitmq-server](https://github.com/rabbitmq/rabbitmq-server)

- **Kafka 4.0.0** (опционально): Для обработки больших потоков данных и событий в реальном времени.
    - Сайт: [kafka.apache.org](https://kafka.apache.org/)
    - GitHub: [apache/kafka](https://github.com/apache/kafka)

---

## Инфраструктура и развёртывание

- **Docker 28**: Платформа для контейнеризации приложений.
    - Сайт: [docker.com](https://www.docker.com/)
    - GitHub: [moby/moby](https://github.com/moby/moby)

- **Docker Compose 2.34.0**: Система оркестрации контейнеров для управления развертыванием и масштабированием.
    - Сайт: [docs.docker.com/compose](https://docs.docker.com/compose/)
    - GitHub: [docker/compose](https://github.com/docker/compose)

- **Traefik 3.3.4**: Маршрутизатор и балансировщик нагрузки для управления входящими запросами.
    - Сайт: [traefik.io](https://traefik.io/)
    - GitHub: [traefik/traefik](https://github.com/traefik/traefik)

- **HashiCorp Consul 1.20.5**: Инструмент для сервисного обнаружения и управления конфигурациями.
    - Сайт: [consul.io](https://www.consul.io/)
    - GitHub: [hashicorp/consul](https://github.com/hashicorp/consul)

- **HashiCorp Vault 1.19.0**: Система для безопасного хранения и управления секретами.
    - Сайт: [vaultproject.io](https://www.vaultproject.io/)
    - GitHub: [hashicorp/vault](https://github.com/hashicorp/vault)

---

## Мониторинг и логирование

- **Prometheus 3.2.1**: Система мониторинга и оповещения.
    - Сайт: [prometheus.io](https://prometheus.io/)
    - GitHub: [prometheus/prometheus](https://github.com/prometheus/prometheus)

- **Grafana 11.6.0**: Платформа для визуализации метрик и создания дашбордов.
    - Сайт: [grafana.com](https://grafana.com/)
    - GitHub: [grafana/grafana](https://github.com/grafana/grafana)

- **ELK Stack**:
    - **Elasticsearch 8.17.4**: Поисковый движок и хранилище для логирования и аналитики.
        - Сайт: [elastic.co/elasticsearch](https://www.elastic.co/elasticsearch/)
        - GitHub: [elastic/elasticsearch](https://github.com/elastic/elasticsearch)
    - **Logstash 8.17.4**:
        - Сайт: [elastic.co/logstash](https://www.elastic.co/logstash)
        - GitHub: [elastic/logstash](https://github.com/elastic/logstash)
    - **Kibana 8.17.4**:
        - Сайт: [elastic.co/kibana](https://www.elastic.co/kibana)
        - GitHub: [elastic/kibana](https://github.com/elastic/kibana)

- **Sentry 24.0.0**: Инструмент для отслеживания и уведомления о критических ошибках.
    - Сайт: [sentry.io](https://sentry.io/)
    - GitHub: [getsentry/sentry](https://github.com/getsentry/sentry)

- **OpenTelemetry 1.14.0**: Инструменты для трассировки и мониторинга производительности приложений.
    - Сайт: [opentelemetry.io](https://opentelemetry.io/)
    - GitHub: [open-telemetry/opentelemetry-python](https://github.com/open-telemetry/opentelemetry-python)

---

## Инструменты разработки и тестирования

- **Git**: Система контроля версий.
    - Сайт: [git-scm.com](https://git-scm.com/)
    - GitHub: [git/git](https://github.com/git/git)

- **GitLab CI/CD**: Инструменты для непрерывной интеграции и доставки.
    - Сайт: [about.gitlab.com/stages-devops-lifecycle/continuous-integration/](https://about.gitlab.com/stages-devops-lifecycle/continuous-integration/)

- **PyTest 8.3.5**: Фреймворк для написания и запуска тестов.
    - Сайт: [docs.pytest.org](https://docs.pytest.org/)
    - GitHub: [pytest-dev/pytest](https://github.com/pytest-dev/pytest)

- **Swagger/OpenAPI (Swagger UI 4.18.3)**: Инструменты для документирования и тестирования API.
    - Сайт: [swagger.io/tools/swagger-ui/](https://swagger.io/tools/swagger-ui/)
    - GitHub: [swagger-api/swagger-ui](https://github.com/swagger-api/swagger-ui)
