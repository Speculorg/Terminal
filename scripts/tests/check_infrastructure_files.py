#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script: check_infrastructure_files.py
Description:
    This script verifies the presence and structure of infrastructure files and folders
    across various groups in the project. The script performs the following steps:
    
      1. Parse command line arguments for options:
         --debug, --no-progress, --max-depth N, --workspace PATH, --no-log, --no-console, --log-dir, --help.
      2. Set configuration parameters including workspace root, debug mode, progress output,
         maximum recursion depth, and validation data for infrastructure components.
      3. Generate a timestamp (format: YYYY.MM.DD_HH-MM) and create a log file in the specified log directory.
      4. Write a header and runtime environment information (workspace, OS version, script version, debug mode)
         to the log file and, if enabled, to the console.
      5. Validate groups of infrastructure elements:
         - Core Directories: Check that key directories (docker, services, modules, configs, scripts, logs) exist.
         - Environment Configuration Files: In "configs/", verify that .env.develop, .env.release, and README.md exist.
         - Service Source Structure: In "services/", for each service, verify that the source directory,
           required files (README.md, main.py) and config subdirectory with its files (README.md, config.yml) exist.
         - Module Source Structure: In "modules/", for each module, verify a similar structure.
         - Docker Structure: In "docker/", for each service/module, verify that the docker directory exists
           with required files (README.md, Dockerfile, requirements.txt).
         - Infrastructure Orchestration: Verify that the docker-compose.yml file exists in "docker/".
         In addition, for each directory (except those excluded) the script checks for the mandatory presence
         of a README.md file.
      6. For each check, output a formatted tree node with a status icon:
           ✅ if the check passed,
           ⚠ if a warning condition is met (e.g. missing README.md),
           ❌ if the check failed.
         The output for each group is presented as a tree with proper indentation.
      7. At the end, output a summary of the results (number of successes, warnings, errors)
         and list the absolute paths of problematic items.
    
Version: 0.3
Author: Speculorg Team
Date: 2025.04.07
History:
    0.1 - Initial version based on batch script.
    0.2 - Added runtime environment info and detailed finish block (in batch).
    0.3 - Ported to Python with modular, readable, and tree-based formatted output.
"""

import os
import sys
import argparse
import datetime
import platform
import fnmatch

# ====================================================
# Global Configuration Parameters (Speculorg Standards)
# ====================================================
DEFAULT_WORKSPACE_ROOT = os.getcwd()  # Workspace root directory
DEFAULT_DEBUG_MODE = False              # Debug mode (can be enabled via --debug)
DEFAULT_SHOW_PROGRESS = True            # Show progress messages
DEFAULT_MAX_DEPTH = 10                  # Maximum recursion depth

# Status symbols
STATUS_OK = "✅"
STATUS_WARN = "⚠"
STATUS_ERR = "❌"

# Tree symbols for output
DIR_SYMBOL = "📁"
FILE_SYMBOL = "📄"
TREE_BRANCH = "├──"
TREE_LAST = "└──"
TREE_PIPE = "│   "
TREE_SPACE = "    "

# ====================================================
# Validation Data Configuration
# ====================================================
CORE_DIRS = ["docker", "services", "modules", "configs", "scripts", "logs"]
ENV_FILES = [".env.develop", ".env.release", "README.md"]

SRC_FILES = ["README.md", "main.py"]
CONFIG_FILES = ["README.md", "config.yml"]
DOCKER_FILES = ["README.md", "Dockerfile", "requirements.txt"]
DOCKER_COMPOSE = "docker-compose.yml"

SERVICES = [
    "infrastructure-service",
    "management-service",
    "security-service"
]
MODULES = [
    "infrastructure-consul-module",
    "infrastructure-vault-module",
    "infrastructure-database-module",
    "infrastructure-docker-module",
    "infrastructure-redis-module",
    "infrastructure-rabbitmq-module",
    "infrastructure-celery-module",
    "infrastructure-keycloak-module",
    "infrastructure-traefik-module",
    "infrastructure-opentelemetry-module",
    "infrastructure-prometheus-module",
    "infrastructure-grafana-module",
    "infrastructure-sentry-module",
    "infrastructure-elk-module",
    "management-logs-module",
    "management-configurations-module",
    "management-users-module",
    "security-audit-module",
    "security-authentication-module",
    "security-authorization-module"
]

EXCLUDE_README_CHECK_DIRS = ["logs"]

# ====================================================
# Global Counters and Problem Items
# ====================================================
SUCCESS_COUNT = 0
WARNING_COUNT = 0
ERROR_COUNT = 0
PROBLEM_ITEMS = []  # List to store (absolute_path, status, message) for problematic items

# ====================================================
# Logging and Utility Functions
# ====================================================
def get_timestamp():
    """Returns the current timestamp in format YYYY.MM.DD_HH-MM."""
    now = datetime.datetime.now()
    return now.strftime("%Y.%m.%d_%H-%M")

def init_log_file(workspace_root, log_dir_override=None):
    """Initializes the log file in the specified log directory."""
    timestamp = get_timestamp()
    log_dir = log_dir_override if log_dir_override else os.path.join(workspace_root, "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_filename = os.path.join(log_dir, f"{timestamp}_check_infrastructure_files.log")
    with open(log_filename, "w", encoding="utf-8") as lf:
        lf.write("====================================================\n")
        lf.write("Speculorg - Infrastructure Check Report\n")
        lf.write(f"Date: {timestamp}\n")
        lf.write("====================================================\n\n")
        lf.write("Runtime Environment Information:\n")
        lf.write(f" - Workspace Root: {workspace_root}\n")
        lf.write(f" - OS Version: {platform.platform()}\n")
        lf.write(" - Script Version: 0.3\n")
        lf.write(f" - Debug Mode: {DEFAULT_DEBUG_MODE}\n")
        lf.write("====================================================\n\n")
    return log_filename, timestamp

def log_message(msg_type, message, log_file, console_enabled=True):
    """Logs a message with a timestamp to the log file and optionally to the console."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] [{msg_type}] {message}"
    try:
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(formatted + "\n")
    except Exception as e:
        print(f"Logging error: {e}")
    if console_enabled:
        if msg_type.upper() == "ERROR":
            print(f"{STATUS_ERR} {formatted}")
        elif msg_type.upper() == "WARN":
            print(f"{STATUS_WARN} {formatted}")
        else:
            print(formatted)

def log_debug(message, log_file, console_enabled, debug_mode):
    """Logs a debug message if debug mode is enabled."""
    if debug_mode:
        log_message("DEBUG", message, log_file, console_enabled)

def log_info(message, log_file, console_enabled):
    """Logs an info message."""
    log_message("INFO", message, log_file, console_enabled)

def log_warning(message, log_file, console_enabled):
    """Logs a warning message and updates global WARNING_COUNT."""
    global WARNING_COUNT
    WARNING_COUNT += 1
    log_message("WARN", message, log_file, console_enabled)

def log_error(message, log_file, console_enabled):
    """Logs an error message and updates global ERROR_COUNT."""
    global ERROR_COUNT
    ERROR_COUNT += 1
    log_message("ERROR", message, log_file, console_enabled)

# ====================================================
# Validation Function (with Problem Items collection)
# ====================================================
def validate_item(rel_path, full_path, item_type):
    """
    Checks existence and mandatory README for directories.
    Returns (status, message).
    Also updates counters and appends problematic items (non-OK) to PROBLEM_ITEMS.
    """
    global SUCCESS_COUNT, WARNING_COUNT, ERROR_COUNT, PROBLEM_ITEMS

    status = STATUS_OK
    message = ""

    if not os.path.exists(full_path):
        status = STATUS_ERR
        message = "does not exist"
    else:
        if item_type == "dir":
            base_name = os.path.basename(rel_path.rstrip("/"))
            if base_name not in EXCLUDE_README_CHECK_DIRS:
                readme_path = os.path.join(full_path, "README.md")
                if not os.path.exists(readme_path):
                    status = STATUS_WARN
                    message = "missing README.md"
        elif item_type == "file":
            if not os.access(full_path, os.R_OK):
                status = STATUS_WARN
                message = "cannot read"
            if os.path.islink(full_path):
                status = STATUS_WARN
                message = (message + " is symlink").strip()

    # Update counters and record problematic items if not OK
    if status == STATUS_OK:
        SUCCESS_COUNT += 1
    elif status == STATUS_WARN:
        WARNING_COUNT += 1
        PROBLEM_ITEMS.append((os.path.abspath(full_path), status, message))
    elif status == STATUS_ERR:
        ERROR_COUNT += 1
        PROBLEM_ITEMS.append((os.path.abspath(full_path), status, message))

    return status, message

# ====================================================
# Tree Formatting Helper Function
# ====================================================
def make_tree_line(status, icon, name, message, indent, branch):
    """
    Formats one line of tree output with correct symbols.
    For example: "✅    ├── 📁 directory" or "⚠    └── 📄 file (missing README.md)".
    """
    msg_suffix = f" ({message})" if message else ""
    return f"{status}{indent}{branch} {icon} {name}{msg_suffix}"

def print_group_header(title, log_file, show_progress):
    header = f"====================\n{title}:\n===================="
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(header + "\n")
    if show_progress:
        print(header)

# ====================================================
# Group Validation Functions with Tree Output
# ====================================================
def validate_group_core_dirs(workspace_root, log_file, show_progress):
    print_group_header("Core Directories", log_file, show_progress)
    root_name = os.path.basename(workspace_root)
    root_line = f"{DIR_SYMBOL} {root_name}\\"
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(root_line + "\n")
    if show_progress:
        print(root_line)

    n = len(CORE_DIRS)
    for i, dirname in enumerate(CORE_DIRS):
        full_path = os.path.join(workspace_root, dirname)
        status, msg = validate_item(dirname, full_path, "dir")
        branch = TREE_LAST if i == (n - 1) else TREE_BRANCH
        line = make_tree_line(status, DIR_SYMBOL, dirname, msg, "    ", branch)
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(line + "\n")
        if show_progress:
            print(line)
    print("")

def validate_group_env_files(config_dir, log_file, show_progress):
    print_group_header('Environment Configuration Files in "configs\\"', log_file, show_progress)
    for filename in ENV_FILES:
        full_path = os.path.join(config_dir, filename)
        status, msg = validate_item(filename, full_path, "file")
        line = f"{status} {FILE_SYMBOL} {filename}" + (f" ({msg})" if msg else "")
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(line + "\n")
        if show_progress:
            print(line)
    print("")

def validate_group_services(services_dir, log_file, show_progress):
    print_group_header("Service Source Structure", log_file, show_progress)
    root_line = f"{DIR_SYMBOL} services\\"
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(root_line + "\n")
    if show_progress:
        print(root_line)

    n = len(SERVICES)
    for i, service in enumerate(SERVICES):
        base_path = os.path.join(services_dir, service)
        status_dir, msg_dir = validate_item(service, base_path, "dir")
        branch_service = TREE_LAST if i == (n - 1) else TREE_BRANCH
        service_line = make_tree_line(status_dir, DIR_SYMBOL, f"{service}\\", msg_dir, "    ", branch_service)
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(service_line + "\n")
        if show_progress:
            print(service_line)

        service_indent = "    " + (TREE_SPACE if branch_service == TREE_LAST else TREE_PIPE)

        for src_file in SRC_FILES:
            status_f, msg_f = validate_item(src_file, os.path.join(base_path, src_file), "file")
            branch_file = TREE_BRANCH  # Always use TREE_BRANCH here since config is treated as last
            file_line = make_tree_line(status_f, FILE_SYMBOL, src_file, msg_f, service_indent, branch_file)
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(file_line + "\n")
            if show_progress:
                print(file_line)

        config_path = os.path.join(base_path, "config")
        status_cfg, msg_cfg = validate_item("config", config_path, "dir")
        branch_cfg = TREE_LAST  # Config directory is considered last in the service node
        config_line = make_tree_line(status_cfg, DIR_SYMBOL, "config\\", msg_cfg, service_indent, branch_cfg)
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(config_line + "\n")
        if show_progress:
            print(config_line)

        indent_cfg = service_indent + TREE_SPACE
        for k, cf in enumerate(CONFIG_FILES):
            status_cf, msg_cf = validate_item(cf, os.path.join(config_path, cf), "file")
            branch_cfile = TREE_LAST if k == (len(CONFIG_FILES) - 1) else TREE_BRANCH
            cf_line = make_tree_line(status_cf, FILE_SYMBOL, cf, msg_cf, indent_cfg, branch_cfile)
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(cf_line + "\n")
            if show_progress:
                print(cf_line)
    print("")

def validate_group_modules(modules_dir, log_file, show_progress):
    print_group_header("Module Source Structure", log_file, show_progress)
    root_line = f"{DIR_SYMBOL} modules\\"
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(root_line + "\n")
    if show_progress:
        print(root_line)

    n = len(MODULES)
    for i, module in enumerate(MODULES):
        base_path = os.path.join(modules_dir, module)
        status_mod, msg_mod = validate_item(module, base_path, "dir")
        branch_module = TREE_LAST if i == (n - 1) else TREE_BRANCH
        module_line = make_tree_line(status_mod, DIR_SYMBOL, f"{module}\\", msg_mod, "    ", branch_module)
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(module_line + "\n")
        if show_progress:
            print(module_line)

        module_indent = "    " + (TREE_SPACE if branch_module == TREE_LAST else TREE_PIPE)

        for sfile in SRC_FILES:
            status_sf, msg_sf = validate_item(sfile, os.path.join(base_path, sfile), "file")
            branch_sfile = TREE_BRANCH  # always TREE_BRANCH for source files; config will be last
            file_line = make_tree_line(status_sf, FILE_SYMBOL, sfile, msg_sf, module_indent, branch_sfile)
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(file_line + "\n")
            if show_progress:
                print(file_line)

        config_path = os.path.join(base_path, "config")
        status_cfg, msg_cfg = validate_item("config", config_path, "dir")
        branch_cdir = TREE_LAST
        config_line = make_tree_line(status_cfg, DIR_SYMBOL, "config\\", msg_cfg, module_indent, branch_cdir)
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(config_line + "\n")
        if show_progress:
            print(config_line)

        conf_indent = module_indent + TREE_SPACE
        for k, cf in enumerate(CONFIG_FILES):
            status_cf, msg_cf = validate_item(cf, os.path.join(config_path, cf), "file")
            branch_cf = TREE_LAST if k == (len(CONFIG_FILES) - 1) else TREE_BRANCH
            cf_line = make_tree_line(status_cf, FILE_SYMBOL, cf, msg_cf, conf_indent, branch_cf)
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(cf_line + "\n")
            if show_progress:
                print(cf_line)
    print("")

def validate_group_docker(services_dir, modules_dir, docker_dir, log_file, show_progress):
    print_group_header("Docker Structure", log_file, show_progress)
    root_line = f"{DIR_SYMBOL} docker\\"
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(root_line + "\n")
    if show_progress:
        print(root_line)
    components = SERVICES + MODULES
    n = len(components)
    for i, comp in enumerate(components):
        full_path = os.path.join(docker_dir, comp)
        status_c, msg_c = validate_item(comp, full_path, "dir")
        branch_comp = TREE_LAST if i == (n - 1) else TREE_BRANCH
        comp_line = make_tree_line(status_c, DIR_SYMBOL, comp, msg_c, "    ", branch_comp)
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(comp_line + "\n")
        if show_progress:
            print(comp_line)

        comp_indent = "    " + (TREE_SPACE if branch_comp == TREE_LAST else TREE_PIPE)

        for j, df_name in enumerate(DOCKER_FILES):
            status_df, msg_df = validate_item(df_name, os.path.join(full_path, df_name), "file")
            branch_df = TREE_LAST if j == (len(DOCKER_FILES) - 1) else TREE_BRANCH
            df_line = make_tree_line(status_df, FILE_SYMBOL, df_name, msg_df, comp_indent, branch_df)
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(df_line + "\n")
            if show_progress:
                print(df_line)
    print("")

def validate_group_infra_orchestration(docker_dir, log_file, show_progress):
    print_group_header("Infrastructure Orchestration", log_file, show_progress)
    full_path = os.path.join(docker_dir, DOCKER_COMPOSE)
    status, msg = validate_item(DOCKER_COMPOSE, full_path, "file")
    line = f"{status} {FILE_SYMBOL} {DOCKER_COMPOSE}" + (f" ({msg})" if msg else "")
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(line + "\n")
    if show_progress:
        print(line)
    print("")

# ====================================================
# New Function: Print Problematic Items
# ====================================================
def print_problem_items(log_file, show_progress):
    """
    Prints a block at the end of the report with absolute paths to problematic items.
    Each line shows the status icon, the absolute path, and the problem message.
    """
    global PROBLEM_ITEMS
    header = "\nProblematic Items (absolute paths):\n---------------------------------------------"
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(header + "\n")
    if show_progress:
        print(header)
    if not PROBLEM_ITEMS:
        none_line = "None"
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(none_line + "\n")
        if show_progress:
            print(none_line)
    else:
        for item in PROBLEM_ITEMS:
            abs_path, status, msg = item
            line = f"{status} {abs_path}" + (f" ({msg})" if msg else "")
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(line + "\n")
            if show_progress:
                print(line)
    footer = "---------------------------------------------\n"
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(footer)
    if show_progress:
        print(footer)

# ====================================================
# Modified Validation Function: validate_item
# ====================================================
def validate_item(rel_path, full_path, item_type):
    """
    Checks existence and mandatory README for directories.
    Returns (status, message).
    Also updates counters and appends problematic items (non-OK) to PROBLEM_ITEMS.
    """
    global SUCCESS_COUNT, WARNING_COUNT, ERROR_COUNT, PROBLEM_ITEMS

    status = STATUS_OK
    message = ""

    if not os.path.exists(full_path):
        status = STATUS_ERR
        message = "does not exist"
    else:
        if item_type == "dir":
            base_name = os.path.basename(rel_path.rstrip("/"))
            if base_name not in EXCLUDE_README_CHECK_DIRS:
                readme_path = os.path.join(full_path, "README.md")
                if not os.path.exists(readme_path):
                    status = STATUS_WARN
                    message = "missing README.md"
        elif item_type == "file":
            if not os.access(full_path, os.R_OK):
                status = STATUS_WARN
                message = "cannot read"
            if os.path.islink(full_path):
                status = STATUS_WARN
                message = (message + " is symlink").strip()

    if status == STATUS_OK:
        SUCCESS_COUNT += 1
    elif status == STATUS_WARN:
        WARNING_COUNT += 1
        PROBLEM_ITEMS.append((os.path.abspath(full_path), status, message))
    elif status == STATUS_ERR:
        ERROR_COUNT += 1
        PROBLEM_ITEMS.append((os.path.abspath(full_path), status, message))
    return status, message

# ====================================================
# Main Function
# ====================================================
def main():
    parser = argparse.ArgumentParser(
        description="Verifies the presence and structure of infrastructure files and folders."
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode.")
    parser.add_argument("--no-progress", action="store_true", help="Hide progress messages.")
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH,
                        help="Set maximum recursion depth (default: 10).")
    parser.add_argument("--workspace", type=str, default=DEFAULT_WORKSPACE_ROOT,
                        help="Set workspace root directory (default: current directory).")
    parser.add_argument("--no-log", action="store_true", help="Disable logging to file.")
    parser.add_argument("--no-console", action="store_true", help="Disable console output.")
    parser.add_argument("--log-dir", type=str, help="Set custom log directory.")
    args = parser.parse_args()

    debug_mode = args.debug
    show_progress = not args.no_progress
    max_depth = args.max_depth  # Currently unused in tree output functions, but available for future use.
    workspace_root = os.path.abspath(args.workspace)
    log_enabled = not args.no_log
    console_enabled = not args.no_console
    log_dir = args.log_dir if args.log_dir else None

    if log_enabled:
        log_file, timestamp = init_log_file(workspace_root, log_dir)
    else:
        log_file = None

    runtime_info = (
        "\nRuntime Environment Information:\n"
        f" - Workspace Root: {workspace_root}\n"
        f" - OS Version: {platform.platform()}\n"
        f" - Maximum Recursion Depth: {max_depth}\n"
        f" - Debug Mode: {debug_mode}\n\n"
    )
    if log_enabled:
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(runtime_info)
    if show_progress and console_enabled:
        print(runtime_info)

    # Define key paths
    config_dir = os.path.join(workspace_root, "configs")
    services_dir = os.path.join(workspace_root, "services")
    modules_dir = os.path.join(workspace_root, "modules")
    docker_dir = os.path.join(workspace_root, "docker")

    if not os.path.exists(workspace_root):
        if log_enabled:
            log_error(f"Workspace directory does not exist: {workspace_root}", log_file, console_enabled)
        else:
            print(f"{STATUS_ERR} Workspace directory does not exist: {workspace_root}")
        sys.exit(1)

    log_info("Starting infrastructure structure check...", log_file, console_enabled)

    # Execute validation groups (tree output)
    validate_group_core_dirs(workspace_root, log_file, show_progress)
    validate_group_env_files(config_dir, log_file, show_progress)
    validate_group_services(services_dir, log_file, show_progress)
    validate_group_modules(modules_dir, log_file, show_progress)
    validate_group_docker(services_dir, modules_dir, docker_dir, log_file, show_progress)
    validate_group_infra_orchestration(docker_dir, log_file, show_progress)

    finish_message = (
        "\n---------------------------------------------\n"
        "Infrastructure structure check completed.\n"
        f"Results:\n"
        f"   Successes: {SUCCESS_COUNT}\n"
        f"   Warnings: {WARNING_COUNT}\n"
        f"   Errors: {ERROR_COUNT}\n"
        f"Results saved in: {log_file if log_file else 'N/A'}\n"
        "---------------------------------------------\n"
    )
    if log_enabled:
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(finish_message)
    if show_progress and console_enabled:
        print(finish_message)

    # NEW: Print block with absolute paths to problematic items
    if log_enabled:
        print_problem_items(log_file, show_progress)

if __name__ == "__main__":
    main()
