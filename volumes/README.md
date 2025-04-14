# Volumes

This directory contains bind-mounted folders for persistent data storage during development. The following subdirectories are used to store data for critical services:

- **postgres_data/** — Stores the PostgreSQL database data.
- **redis_data/** — Contains the Redis cache and persistence data.
- **rabbitmq_data/** — Holds RabbitMQ messaging broker data.
- **elk_data/** — Used for data from the ELK stack (Elasticsearch, Logstash, Kibana).

