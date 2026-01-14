# Структура проекта

## Основные директории

* `core/`: Ядро системы. Содержит инфраструктурные компоненты, реализующие архитектурные принципы.
* `services/`: Тонкие сервисы, использующие ядро для взаимодействия с инфраструктурой и управления демонами.
* `tests/`: Модульные, интеграционные и сквозные тесты.
* `docs/`: Документация проекта.
* `volumes/`: Директория для монтирования томов.


```
speculorg-terminal/
├── docs/
│   ├── project_structure.md
│   ├── architecture_overview.md
│   ├── error_handling.md
│   ├── api_reference.md
│   ├── component_interaction_diagram.puml
│   ├── service_lifecycle_fsm_diagram.puml
│   └── tls_flow_diagram.puml
├── core/
│   ├── __init__.py
│   ├── _entities/
│   │   ├── __init__.py
│   │   ├── health_snapshot_type.py
│   │   ├── policy_result_type.py
│   │   ├── error_code_enum.py
│   │   ├── event_code_enum.py
│   │   ├── log_level_enum.py
│   │   ├── policy_status_enum.py
│   │   ├── run_mode_enum.py
│   │   └── state_enum.py
│   ├── _interfaces/
│   │   ├── __init__.py
│   │   ├── i_deps.py
│   │   ├── i_configs.py
│   │   ├── i_logger.py
│   │   ├── i_fs.py
│   │   ├── i_markers.py
│   │   ├── i_net.py
│   │   ├── i_tls.py
│   │   ├── i_registrar.py
│   │   ├── i_fsm.py
│   │   ├── i_policy.py
│   │   ├── i_run_profile.py
│   │   └── i_service.py
│   ├── _base/
│   │   ├── __init__.py
│   │   ├── base_deps.py
│   │   ├── base_configs.py
│   │   ├── base_logger.py
│   │   ├── base_fs.py
│   │   ├── base_markers.py
│   │   ├── base_net.py
│   │   ├── base_tls.py
│   │   ├── base_registrar.py
│   │   ├── base_fsm.py
│   │   ├── base_policy.py
│   │   └── base_service.py
│   ├── deps/
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   └── factory.py
│   ├── configs/
│   │   ├── __init__.py
│   │   ├── model.py
│   │   └── configs.py
│   ├── logger/
│   │   ├── __init__.py
│   │   ├── logger.py
│   │   └── adapters/
│   │       ├── __init__.py
│   │       └── json_logger.py
│   ├── fs/
│   │   ├── __init__.py
│   │   └── fs.py
│   ├── markers/
│   │   ├── __init__.py
│   │   └── markers.py
│   ├── net/
│   │   ├── __init__.py
│   │   └── net.py
│   ├── tls/
│   │   ├── __init__.py
│   │   └── tls.py
│   ├── registrar/
│   │   ├── __init__.py
│   │   ├── registrar.py
│   │   └── adapters/
│   │       ├── __init__.py
│   │       └── consul_registrar.py
│   └── fsm/
│       ├── __init__.py
│       ├── fsm.py
│       ├── policies/
│       │   ├── __init__.py
│       │   ├── marker_policy.py
│       │   ├── net_policy.py
│       │   ├── bootstrap_policy.py
│       │   ├── registrar_policy.py
│       │   ├── tls_policy.py
│       │   └── daemon_policy.py
│       └── daemon/
│           ├── __init__.py
│           └── runner.py
├── services/
│   ├── __init__.py
│   ├── consul/
│   │   ├── __init__.py
│   │   ├── app/
│   │   │   └── main.py
│   │   ├── configs/
│   │   │   ├── consul_http.hcl
│   │   │   ├── consul_https.hcl
│   │   │   └── bootstrap.py
│   │   └── Dockerfile
│   ├── vault/
│   │   ├── __init__.py
│   │   ├── app/
│   │   │   └── main.py
│   │   ├── configs/
│   │   │   ├── vault_http.hcl
│   │   │   ├── vault_https.hcl
│   │   │   └── bootstrap.py
│   │   └── Dockerfile
│   ├── traefik/
│   │   ├── __init__.py
│   │   ├── app/
│   │   │   └── main.py
│   │   ├── configs/
│   │   │   └── traefik_https.yaml
│   │   └── Dockerfile
│   └── example_service/
│       ├── __init__.py
│       ├── app/
│       │   └── main.py
│       ├── configs/
│       │   ├── service_http.cfg
│       │   ├── service_https.cfg
│       │   └── bootstrap.py
│       └── Dockerfile
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_deps.py
│   │   ├── test_configs.py
│   │   ├── test_logger.py
│   │   ├── test_fs.py
│   │   ├── test_markers.py
│   │   ├── test_net.py
│   │   ├── test_tls.py
│   │   ├── test_registrar.py
│   │   ├── test_policies.py
│   │   └── test_fsm.py
│   └── integration/
│       ├── __init__.py
│       ├── test_consul_service.py
│       ├── test_vault_service.py
│       └── test_traefik_service.py
├── README.md
├── configs.env
└── docker-compose.yml

```
