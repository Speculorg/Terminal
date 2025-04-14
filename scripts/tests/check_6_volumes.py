#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check_6_volumes.py - Version 0.3
--------------------------------
Description:
  Script to validate volumes configuration in docker-compose.yml for the Speculorg.Terminal project.
  It checks that bind mounts for PostgreSQL, Redis, RabbitMQ, and ELK are defined correctly and do not conflict.
  It also ensures that the host directories exist and that 'docker-compose config' validates the configuration.

Version History:
  v0.1 - Initial version with basic volume checks.
  v0.2 - Added docker-compose config check and host-directory existence validation.
  v0.3 - Updated logging output to remove per-line timestamps, add overall execution timing,
         converted all log messages to English, and fixed docker-compose config call using -f option.
"""

import os
import sys
import yaml
import subprocess
import datetime
import logging
import time

# ----------------- VALIDATION DATA -----------------
# Expected volumes mapping for key services.
VALIDATION_DATA = {
    "infrastructure-database-module": {
        "expected_host": "./volumes/postgres_data",
        "expected_container": "/var/lib/postgresql/data",
        "description": "PostgreSQL"
    },
    "infrastructure-redis-module": {
        "expected_host": "./volumes/redis_data",
        "expected_container": "/data",
        "description": "Redis"
    },
    "infrastructure-rabbitmq-module": {
        "expected_host": "./volumes/rabbitmq_data",
        "expected_container": "/var/lib/rabbitmq",
        "description": "RabbitMQ"
    },
    "infrastructure-elk-module": {
        "expected_host": "./volumes/elk_data",
        "expected_container": "/var/lib/elasticsearch",
        "description": "ELK"
    }
}

# ----------------- SETTINGS -----------------
# Full path to the docker-compose.yml file.
DOCKER_COMPOSE_PATH = os.path.join(os.getcwd(), "docker", "docker-compose.yml")
LOGS_DIR = os.path.join(os.getcwd(), "logs")
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)
log_filename = os.path.join(LOGS_DIR, datetime.datetime.now().strftime("%Y.%m.%d_%H-%M_check_6_volumes.log"))

# Configure logging without timestamps for each line.
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

def load_compose_file(compose_path):
    try:
        with open(compose_path, "r", encoding="utf-8") as f:
            compose_data = yaml.safe_load(f)
        logging.info("✅ Successfully loaded docker-compose.yml from: %s", compose_path)
        return compose_data
    except Exception as e:
        logging.error("❌ Error loading docker-compose.yml: %s", str(e))
        sys.exit(1)

def check_bind_mount(volume_spec, expected_host, expected_container):
    """
    Verify that a volume specification string (in the format "host_path:container_path[:options]")
    matches the expected host and container paths.
    """
    parts = volume_spec.split(":")
    if len(parts) < 2:
        return False
    host_path = parts[0].strip()
    container_path = parts[1].strip()
    return (host_path == expected_host) and (container_path == expected_container)

def check_service_volumes(compose_data, service_name, expected_data):
    """
    For the given service, check if the expected bind mount exists and that the host directory is present.
    Returns a tuple (status, [messages]).
    """
    messages = []
    status = True
    services = compose_data.get("services", {})
    service_data = services.get(service_name)
    if service_data is None:
        messages.append(f"❌ Service '{service_name}' not found in docker-compose.yml.")
        return False, messages

    volumes_list = service_data.get("volumes", [])
    if not volumes_list:
        messages.append(f"❌ Service '{service_name}' has no volumes section defined.")
        return False, messages

    found = False
    for volume_spec in volumes_list:
        if isinstance(volume_spec, str):
            if check_bind_mount(volume_spec, expected_data["expected_host"], expected_data["expected_container"]):
                found = True
                break
        elif isinstance(volume_spec, dict):
            # Extend handling for dict format if needed.
            pass

    if not found:
        messages.append(
            f"❌ For '{expected_data['description']}' in service '{service_name}', expected bind mount '{expected_data['expected_host']}:{expected_data['expected_container']}' was not found."
        )
        status = False
    else:
        messages.append(f"✅ Bind mount for '{expected_data['description']}' in service '{service_name}' is found.")

    # Check that the host directory exists.
    host_dir = os.path.join(os.getcwd(), expected_data["expected_host"].replace("./", ""))
    if not os.path.exists(host_dir):
        messages.append(f"❌ Directory for '{expected_data['description']}' does not exist: {host_dir}")
        status = False
    else:
        messages.append(f"✅ Directory for '{expected_data['description']}' exists: {host_dir}")

    return status, messages

def check_docker_compose_config():
    """
    Run 'docker-compose -f <compose_file> config' to validate the configuration.
    Returns (True, output) if valid, (False, error) otherwise.
    """
    try:
        # Set working directory to the folder where docker-compose.yml is located.
        compose_dir = os.path.dirname(DOCKER_COMPOSE_PATH)
        # Run docker-compose config with the -f flag specifying the file.
        result = subprocess.run(
            ["docker-compose", "-f", DOCKER_COMPOSE_PATH, "config"],
            cwd=compose_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            logging.error("❌ docker-compose config returned error:\n%s", result.stderr.strip())
            return False, result.stderr.strip()
        logging.info("✅ docker-compose config: configuration is valid.")
        return True, result.stdout.strip()
    except Exception as e:
        logging.error("❌ Error executing 'docker-compose config': %s", str(e))
        return False, str(e)

def main():
    start_time = time.time()
    logging.info("====================================================")
    logging.info("Speculorg - Volumes Check Report")
    logging.info("Version: 0.3")
    logging.info("====================================================")
    
    compose_data = load_compose_file(DOCKER_COMPOSE_PATH)
    
    total_checks = 0
    successes = 0
    warnings = 0
    errors = 0
    report_lines = []
    
    # Check each expected service volume.
    for service_name, expected in VALIDATION_DATA.items():
        total_checks += 1
        status, msgs = check_service_volumes(compose_data, service_name, expected)
        for m in msgs:
            report_lines.append(m)
        if status:
            successes += 1
        else:
            errors += 1
    
    # Validate docker-compose configuration.
    total_checks += 1
    status, output = check_docker_compose_config()
    if status:
        successes += 1
        report_lines.append("✅ docker-compose config: configuration is valid.")
    else:
        errors += 1
        report_lines.append("❌ docker-compose config: errors encountered.")
    
    # Summary report.
    report_lines.append("----------------------------------------------------")
    report_lines.append(f"Total checks: {total_checks}")
    report_lines.append(f"Successful: {successes}")
    report_lines.append(f"Warnings: {warnings}")
    report_lines.append(f"Errors: {errors}")
    
    end_time = time.time()
    duration = end_time - start_time
    report_lines.append(f"Start time: {datetime.datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"End time: {datetime.datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Duration: {duration:.2f} seconds")
    report_lines.append(f"Log file path: {log_filename}")
    
    for line in report_lines:
        logging.info(line)

if __name__ == "__main__":
    main()
