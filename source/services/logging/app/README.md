# Logging Service App

This directory contains the Python application code for the `logging.service` microservice, including the core modules responsible for:

- **aggregator**: collecting and ingesting logs from all services
- **filter_engine**: filtering and processing log entries
- **index_mapper**: defining Elasticsearch index mappings
- **alerting**: generating alerts based on log patterns and thresholds

Each module is structured as a Python package and can be extended with additional functionality as needed.
