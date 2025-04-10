#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script: check_env_files.py (v0.4)
Description:
    This script validates environment configuration files (.env.develop and .env.release)
    for the Speculorg.Terminal project. It reads each file into a list of key-value pairs (ignoring
    fully-commented lines), detects duplicate keys (with line numbers), and then compares the found
    variables against the expected set defined in VALIDATION_DATA.

    For each variable, the following checks are made:
      - Existence: If the key is missing, it is logged as an error.
      - Duplicate keys: If the same key appears more than once, it is logged as an error.
      - Empty value: If the value is empty, it is logged as a warning.
      - Placeholder keywords: If placeholders ("TODO", "CHANGEME", "temp") are present in the value,
        it is logged as a warning.
      - Regex check: If an expected regex pattern is provided, the value is matched against it;
        a mismatch results in a warning.
      - Unknown keys: If a key is found that is not expected (i.e. not present in VALIDATION_DATA),
        it is logged as a warning.
      
    The report is printed as a tree grouped by environment file, with each variable preceded by ⚙️,
    and an overall summary is provided along with total execution time.

Version: 0.4
Author: Speculorg Team
Date: 2025.04.09
History:
    0.1 - Initial version.
    0.2 - Base for checking environment files.
    0.3 - Added structured categories, duplicate detection, etc.
    0.4 - Added check for unknown keys (logging them as warnings)

Visit for more information:
- https://specul.org/ - overview
- https://docs.specul.org/ - documentation
        
"""

import os
import sys
import argparse
import datetime
import platform
import re

# =========================
# --- CONFIGURATION ---
# =========================
DEFAULT_DEBUG_MODE = False
DEFAULT_SHOW_PROGRESS = True
ENV_FILES = [".env.develop", ".env.release"]

# Placeholder keywords to warn about.
PLACEHOLDER_KEYWORDS = ["password", "TODO", "CHANGEME", "temp"]

# Expected validation data per environment mode.
# For each key, the value is a regex pattern or None (if no specific regex check required).
VALIDATION_DATA = {
    ".env.develop": {
        "GLOBAL_DEBUG": r"^(true|false)$",
        "GLOBAL_ENVIRONMENT": r"^development$",
        "GLOBAL_HOSTNAME": r"^.+$",
        "GLOBAL_LOG_LEVEL": r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        "GLOBAL_SECRET_KEY": r"^.+$",
        "GLOBAL_TIMEZONE": r"^.+$",

        "INFRASTRUCTURE_SERVICE_HOST": r"^.+$",
        "INFRASTRUCTURE_SERVICE_PORT": r"^\d+$",
        "INFRASTRUCTURE_SERVICE_NAME": r"^.+$",
        "INFRASTRUCTURE_LOG_LEVEL": r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",

        "INFRASTRUCTURE_CONSUL_HOST": r"^.+$",
        "INFRASTRUCTURE_CONSUL_PORT": r"^\d+$",
        "INFRASTRUCTURE_CONSUL_TOKEN": r"^.*$",

        "INFRASTRUCTURE_VAULT_HOST": r"^.+$",
        "INFRASTRUCTURE_VAULT_PORT": r"^\d+$",
        "INFRASTRUCTURE_VAULT_TOKEN": r"^.+$",

        "INFRASTRUCTURE_KEYCLOAK_HOST": r"^.+$",
        "INFRASTRUCTURE_KEYCLOAK_PORT": r"^\d+$",
        "INFRASTRUCTURE_KEYCLOAK_REALM": r"^.+$",
        "INFRASTRUCTURE_KEYCLOAK_CLIENT_ID": r"^.+$",
        "INFRASTRUCTURE_KEYCLOAK_CLIENT_SECRET": r"^.+$",

        "INFRASTRUCTURE_TRAEFIK_HOST": r"^.+$",
        "INFRASTRUCTURE_TRAEFIK_PORT": r"^\d+$",
        "INFRASTRUCTURE_TRAEFIK_ADMIN_PORT": r"^\d+$",

        "INFRASTRUCTURE_CELERY_BROKER_URL": r"^.+$",
        "INFRASTRUCTURE_CELERY_RESULT_BACKEND": r"^.+$",

        "SECURITY_SERVICE_HOST": r"^.+$",
        "SECURITY_SERVICE_PORT": r"^\d+$",
        "SECURITY_SERVICE_NAME": r"^.+$",
        "SECURITY_LOG_LEVEL": r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",

        "MANAGEMENT_SERVICE_HOST": r"^.+$",
        "MANAGEMENT_SERVICE_PORT": r"^\d+$",
        "MANAGEMENT_SERVICE_NAME": r"^.+$",
        "MANAGEMENT_LOG_LEVEL": r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",

        "DATABASE_POSTGRES_DB": r"^.+$",
        "DATABASE_POSTGRES_HOST": r"^.+$",
        "DATABASE_POSTGRES_PORT": r"^\d+$",
        "DATABASE_POSTGRES_USER": r"^.+$",
        "DATABASE_POSTGRES_PASSWORD": r"^.*$",

        "DATABASE_REDIS_HOST": r"^.+$",
        "DATABASE_REDIS_PORT": r"^\d+$",
        "DATABASE_REDIS_DB": r"^\d+$",
        "DATABASE_REDIS_PASSWORD": r"^.*$",

        "LOGGING_ELK_ELASTICSEARCH_HOST": r"^.+$",
        "LOGGING_ELK_ELASTICSEARCH_PORT": r"^\d+$",
        "LOGGING_ELK_LOGSTASH_HOST": r"^.+$",
        "LOGGING_ELK_LOGSTASH_PORT": r"^\d+$",
        "LOGGING_ELK_KIBANA_HOST": r"^.+$",
        "LOGGING_ELK_KIBANA_PORT": r"^\d+$",

        "MONITORING_OPENTELEMETRY_ENDPOINT": r"^https?://.+:\d+$",
        "MONITORING_OPENTELEMETRY_SERVICE_NAME": r"^.+$",

        "MONITORING_PROMETHEUS_HOST": r"^.+$",
        "MONITORING_PROMETHEUS_PORT": r"^\d+$",

        "MONITORING_GRAFANA_HOST": r"^.+$",
        "MONITORING_GRAFANA_PORT": r"^\d+$",
        "MONITORING_GRAFANA_ADMIN_USER": r"^.+$",
        "MONITORING_GRAFANA_ADMIN_PASSWORD": r"^.+$",

        "MONITORING_SENTRY_DSN": r"^https?://.+$",
        "MONITORING_SENTRY_ENVIRONMENT": r"^.+$",
    },
    ".env.release": {
        "GLOBAL_DEBUG": r"^(true|false)$",
        "GLOBAL_ENVIRONMENT": r"^production$",
        "GLOBAL_HOSTNAME": r"^.+$",
        "GLOBAL_LOG_LEVEL": r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        "GLOBAL_SECRET_KEY": r"^.+$",
        "GLOBAL_TIMEZONE": r"^.+$",

        "INFRASTRUCTURE_SERVICE_HOST": r"^.+$",
        "INFRASTRUCTURE_SERVICE_PORT": r"^\d+$",
        "INFRASTRUCTURE_SERVICE_NAME": r"^.+$",
        "INFRASTRUCTURE_LOG_LEVEL": r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",

        "INFRASTRUCTURE_CONSUL_HOST": r"^.+$",
        "INFRASTRUCTURE_CONSUL_PORT": r"^\d+$",
        "INFRASTRUCTURE_CONSUL_TOKEN": r"^.+$",

        "INFRASTRUCTURE_VAULT_HOST": r"^.+$",
        "INFRASTRUCTURE_VAULT_PORT": r"^\d+$",
        "INFRASTRUCTURE_VAULT_TOKEN": r"^.+$",

        "INFRASTRUCTURE_KEYCLOAK_HOST": r"^.+$",
        "INFRASTRUCTURE_KEYCLOAK_PORT": r"^\d+$",
        "INFRASTRUCTURE_KEYCLOAK_REALM": r"^.+$",
        "INFRASTRUCTURE_KEYCLOAK_CLIENT_ID": r"^.+$",
        "INFRASTRUCTURE_KEYCLOAK_CLIENT_SECRET": r"^.+$",

        "INFRASTRUCTURE_TRAEFIK_HOST": r"^.+$",
        "INFRASTRUCTURE_TRAEFIK_PORT": r"^\d+$",
        "INFRASTRUCTURE_TRAEFIK_ADMIN_PORT": r"^\d+$",

        "INFRASTRUCTURE_CELERY_BROKER_URL": r"^.+$",
        "INFRASTRUCTURE_CELERY_RESULT_BACKEND": r"^.+$",

        "SECURITY_SERVICE_HOST": r"^.+$",
        "SECURITY_SERVICE_PORT": r"^\d+$",
        "SECURITY_SERVICE_NAME": r"^.+$",
        "SECURITY_LOG_LEVEL": r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",

        "MANAGEMENT_SERVICE_HOST": r"^.+$",
        "MANAGEMENT_SERVICE_PORT": r"^\d+$",
        "MANAGEMENT_SERVICE_NAME": r"^.+$",
        "MANAGEMENT_LOG_LEVEL": r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",

        "DATABASE_POSTGRES_DB": r"^.+$",
        "DATABASE_POSTGRES_HOST": r"^.+$",
        "DATABASE_POSTGRES_PORT": r"^\d+$",
        "DATABASE_POSTGRES_USER": r"^.+$",
        "DATABASE_POSTGRES_PASSWORD": r"^.+$",

        "DATABASE_REDIS_HOST": r"^.+$",
        "DATABASE_REDIS_PORT": r"^\d+$",
        "DATABASE_REDIS_DB": r"^\d+$",
        "DATABASE_REDIS_PASSWORD": r"^.+$",

        "LOGGING_ELK_ELASTICSEARCH_HOST": r"^.+$",
        "LOGGING_ELK_ELASTICSEARCH_PORT": r"^\d+$",
        "LOGGING_ELK_LOGSTASH_HOST": r"^.+$",
        "LOGGING_ELK_LOGSTASH_PORT": r"^\d+$",
        "LOGGING_ELK_KIBANA_HOST": r"^.+$",
        "LOGGING_ELK_KIBANA_PORT": r"^\d+$",

        "MONITORING_OPENTELEMETRY_ENDPOINT": r"^https?://.+:\d+$",
        "MONITORING_OPENTELEMETRY_SERVICE_NAME": r"^.+$",

        "MONITORING_PROMETHEUS_HOST": r"^.+$",
        "MONITORING_PROMETHEUS_PORT": r"^\d+$",

        "MONITORING_GRAFANA_HOST": r"^.+$",
        "MONITORING_GRAFANA_PORT": r"^\d+$",
        "MONITORING_GRAFANA_ADMIN_USER": r"^.+$",
        "MONITORING_GRAFANA_ADMIN_PASSWORD": r"^.+$",

        "MONITORING_SENTRY_DSN": r"^https?://.+$",
        "MONITORING_SENTRY_ENVIRONMENT": r"^.+$",
    }
}

# =========================
# --- VALIDATION RESULTS STORAGE ---
# =========================
STATUS_OK_OUT = "✅ "
STATUS_WARN_OUT = "⚠️ "
STATUS_ERR_OUT = "❌ "

SUCCESS_COUNT = 0
WARNING_COUNT = 0
ERROR_COUNT = 0

PROBLEM_ITEMS = []    # List of tuples: (mode, key, status, message)
DUPLICATE_KEYS = {}   # { mode: { key: [line_numbers] } }

time_start = None
time_finish = None

# =========================
# --- LOGGING UTILS ---
# =========================
def current_time_str():
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

def init_log_file(workspace_root):
    timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H-%M")
    logs_dir = os.path.join(workspace_root, "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    log_filename = os.path.join(logs_dir, f"{timestamp}_check_3_env_files.log")
    with open(log_filename, "w", encoding="utf-8") as lf:
        lf.write("====================================================\n")
        lf.write("Speculorg - Environment Variable Check Report\n")
        lf.write(f"Date: {timestamp}\n")
        lf.write("====================================================\n\n")
    return log_filename

def log_msg(msg_type, message, log_file, console_enabled=True):
    msg = f"[{current_time_str()}] [{msg_type}] {message}"
    if log_file:
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(msg + "\n")
    if console_enabled:
        print(msg)

def log_info(message, log_file, console_enabled=True):
    log_msg("INFO", message, log_file, console_enabled)

def log_warn(message, log_file, console_enabled=True):
    global WARNING_COUNT
    WARNING_COUNT += 1
    log_msg("WARN", message, log_file, console_enabled)

def log_err(message, log_file, console_enabled=True):
    global ERROR_COUNT
    ERROR_COUNT += 1
    log_msg("ERROR", message, log_file, console_enabled)

def log_debug(message, debug_mode, log_file, console_enabled=True):
    if debug_mode:
        log_msg("DEBUG", message, log_file, console_enabled)

# =========================
# --- ENV FILE PARSING UTILS ---
# =========================
def parse_env_file(env_path, debug_mode, log_file, console_enabled):
    """
    Reads an .env file and returns a list of tuples: (key, value, line_number)
    Ignores lines that are entirely commented out.
    """
    env_vars = []
    if not os.path.exists(env_path):
        log_err(f"File does not exist: {env_path}", log_file, console_enabled)
        return env_vars

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue  # Skip empty or fully commented lines
        # Remove inline comments: split at first '#' if present
        if "#" in stripped:
            stripped = stripped.split("#", 1)[0].strip()
        if not stripped:
            continue
        if "=" not in stripped:
            log_warn(f"Line {i}: Missing '=' in: {line.strip()}", log_file, console_enabled)
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        env_vars.append((key, value, i))
    return env_vars

def check_duplicates(env_list, mode, log_file, console_enabled):
    """
    Checks for duplicate keys in the provided env_list (list of tuples).
    Updates DUPLICATE_KEYS and logs errors for duplicates.
    """
    for key, _, line_num in env_list:
        if mode not in DUPLICATE_KEYS:
            DUPLICATE_KEYS[mode] = {}
        if key not in DUPLICATE_KEYS[mode]:
            DUPLICATE_KEYS[mode][key] = [line_num]
        else:
            DUPLICATE_KEYS[mode][key].append(line_num)
    # Log duplicates as errors (unknown keys already logged as warning later)
    for key, lines in DUPLICATE_KEYS.get(mode, {}).items():
        if len(lines) > 1:
            lines_str = ", ".join(str(x) for x in lines)
            msg = f"Duplicate key '{key}' found at lines: {lines_str}"
            log_err(f"[{mode}] {msg}", log_file, console_enabled)
            PROBLEM_ITEMS.append((mode, key, STATUS_ERR_OUT, msg))

def check_line(mode, line, line_num, debug_mode, log_file, console_enabled):
    """
    Parses a line (KEY=VALUE), and performs checks:
      - Unknown key check: if key not in VALIDATION_DATA => warning.
      - Empty value check.
      - Placeholder check.
      - Regex pattern check.
    """
    raw_line = line.strip()
    if "#" in raw_line:
        raw_line = raw_line.split("#", 1)[0].strip()
    if not raw_line:
        log_debug(f"{mode}: Line {line_num} empty or comment", debug_mode, log_file, console_enabled)
        return None
    if "=" not in raw_line:
        log_warn(f"[{mode}] Missing '=' at line {line_num}: '{line.strip()}'", log_file, console_enabled)
        PROBLEM_ITEMS.append((mode, raw_line, STATUS_WARN_OUT, "No '=' found"))
        return None
    key, value = raw_line.split("=", 1)
    key = key.strip()
    value = value.strip()
    return key, value, line_num

def validate_variables(mode, env_vars, log_file, console_enabled, debug_mode):
    """
    Validates each variable in the env_vars list.
    Checks against the expected keys in VALIDATION_DATA[mode].
    Returns a dictionary mapping key -> (value, line_number) for found variables.
    Logs warnings for:
      - Unknown keys (if key not in VALIDATION_DATA[mode])
      - Empty values
      - Placeholders
      - Regex mismatches.
    """
    found_vars = {}  # key -> (value, line_number)
    for key, value, line_num in env_vars:
        # Check for unknown key:
        if key not in VALIDATION_DATA[mode]:
            log_warn(f"[{mode}] Unknown key '{key}' at line {line_num}", log_file, console_enabled)
            PROBLEM_ITEMS.append((mode, key, STATUS_WARN_OUT, "Unknown key"))
        else:
            # If key exists, record first occurrence for validation
            if key not in found_vars:
                found_vars[key] = (value, line_num)
            # Check for empty value:
            if value == "":
                log_warn(f"[{mode}] '{key}' is empty at line {line_num}", log_file, console_enabled)
                PROBLEM_ITEMS.append((mode, key, STATUS_WARN_OUT, "Empty value"))
            # Check for placeholders in value:
            for placeholder in PLACEHOLDER_KEYWORDS:
                if placeholder.lower() in value.lower():
                    log_warn(f"[{mode}] '{key}' contains placeholder '{placeholder}' at line {line_num}", log_file, console_enabled)
                    PROBLEM_ITEMS.append((mode, key, STATUS_WARN_OUT, f"Placeholder {placeholder}"))
            # Check regex if defined:
            pattern = VALIDATION_DATA[mode][key]
            if pattern is not None and value != "":
                if not re.fullmatch(pattern, value):
                    log_warn(f"[{mode}] '{key}' value '{value}' does not match pattern '{pattern}' at line {line_num}", log_file, console_enabled)
                    PROBLEM_ITEMS.append((mode, key, STATUS_WARN_OUT, "Regex mismatch"))
    # Check for missing expected keys:
    for expected_key in sorted(VALIDATION_DATA[mode].keys()):
        if expected_key not in found_vars:
            log_err(f"[{mode}] Expected key '{expected_key}' is missing", log_file, console_enabled)
            PROBLEM_ITEMS.append((mode, expected_key, STATUS_ERR_OUT, "Key missing"))
    return found_vars

def output_tree(mode, log_file, console_enabled):
    """
    Outputs a tree-like structure of expected variables for the given mode,
    sorted alphabetically. Each line shows a status icon, the variable name,
    and an indication of its validation result.
    """
    keys_sorted = sorted(VALIDATION_DATA[mode].keys())
    for idx, key in enumerate(keys_sorted):
        # Determine worst status among PROBLEM_ITEMS for this key.
        result_status = STATUS_OK_OUT
        result_text = "OK"
        for item in PROBLEM_ITEMS:
            pmode, pkey, pstatus, _ = item
            if pmode == mode and pkey == key:
                if pstatus.strip() == STATUS_ERR_OUT.strip():
                    result_status = STATUS_ERR_OUT
                    result_text = "Error"
                    break
                elif pstatus.strip() == STATUS_WARN_OUT.strip():
                    result_status = STATUS_WARN_OUT
                    result_text = "Warn"
        branch = "└──" if idx == len(keys_sorted) - 1 else "├──"
        line = f"{result_status}    {branch} ⚙️  {key}:{result_text}"
        if log_file:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(line + "\n")
        if console_enabled:
            print(line)

# =========================
# --- MAIN FUNCTION ---
# =========================
def main():
    global time_start, time_finish
    time_start = datetime.datetime.now()

    parser = argparse.ArgumentParser(
        description="Validates environment configuration files (.env.develop and .env.release) for Speculorg.Terminal."
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode.")
    parser.add_argument("--no-progress", action="store_true", help="Disable console output.")
    parser.add_argument("--workspace", type=str, default=os.getcwd(),
                        help="Set workspace root directory (default: current directory).")
    args = parser.parse_args()

    debug_mode = args.debug
    console_enabled = not args.no_progress
    workspace_root = os.path.abspath(args.workspace)

    log_file = init_log_file(workspace_root)
    log_info("Starting environment variable check...", log_file, console_enabled)

    # Print runtime info header
    runtime_info = (
        f"Runtime Environment Information:\n"
        f" - Workspace Root: {workspace_root}\n"
        f" - OS Version: {platform.platform()}\n"
        f" - Script Version: 0.4\n"
        f" - Debug Mode: {debug_mode}\n\n"
    )
    log_info(runtime_info, log_file, console_enabled)

    config_dir = os.path.join(workspace_root, "configs")
    if not os.path.isdir(config_dir):
        log_err(f"configs/ directory does not exist: {config_dir}", log_file, console_enabled)
        sys.exit(1)

    # Process each environment file mode
    for mode in ENV_FILES:
        # Reset duplicate keys tracker for this mode
        DUPLICATE_KEYS[mode] = {}
        log_info(f"\n====================\n📄 {mode}\n====================", log_file, console_enabled)
        env_path = os.path.join(config_dir, mode)
        env_vars = parse_env_file(env_path, debug_mode, log_file, console_enabled)
        check_duplicates(env_vars, mode, log_file, console_enabled)
        validate_variables(mode, env_vars, log_file, console_enabled, debug_mode)
        output_tree(mode, log_file, console_enabled)

    # Summary
    finish_report = (
        "\n---------------------------------------------\n"
        "Environment variable check completed.\n"
        f"Results:\n"
        f"  {STATUS_OK_OUT} Successes: {SUCCESS_COUNT}\n"
        f"  {STATUS_WARN_OUT} Warnings: {WARNING_COUNT}\n"
        f"  {STATUS_ERR_OUT} Errors: {ERROR_COUNT}\n"
        f"Results saved in: {log_file}\n"
        "---------------------------------------------\n"
    )
    log_info(finish_report, log_file, console_enabled)

    # Print problematic items:
    log_info("Problematic Items:", log_file, console_enabled)
    if not PROBLEM_ITEMS:
        log_info("None", log_file, console_enabled)
    else:
        for item in PROBLEM_ITEMS:
            mode_str, key, status, msg = item
            log_info(f"{status} [{mode_str}] {key} => {msg}", log_file, console_enabled)

    time_finish = datetime.datetime.now()
    duration = (time_finish - time_start).total_seconds()
    log_info(f"Completed in {duration:.4f} sec.", log_file, console_enabled)

if __name__ == "__main__":
    main()
