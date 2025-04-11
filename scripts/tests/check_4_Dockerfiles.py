#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script: check_4_Dockerfiles.py
Description:
    This script verifies the presence and content of Dockerfile and requirements.txt files
    in each component directory within docker/. It validates that these files follow
    the standards established for the Speculorg.Terminal project.
    
    The script performs the following steps:
      1. Parse command line arguments for options:
         --debug, --no-progress, --max-depth N, --workspace PATH, --no-log, --no-console, --log-dir, --help.
      2. Set configuration parameters (workspace root, debug mode, progress output,
         maximum recursion depth, validation data for Docker files).
      3. Generate a timestamp (format: YYYY.MM.DD_HH-MM) and create a log file in the specified log directory.
      4. Write a header and runtime environment information (workspace, OS version, script version, debug mode)
         to the log file and, if enabled, to the console.
      5. For each microservice and module in docker/, check for the existence of:
         - Dockerfile
         - requirements.txt
      6. For each Dockerfile found, validate its content:
         - Checks for base image (python:3.13.1-slim)
         - Verifies WORKDIR is set to /app
         - Confirms proper COPY instructions for source code
         - Checks for RUN pip install command
         - Verifies HEALTHCHECK configuration
         - Confirms EXPOSE instruction with port
         - Checks for proper ENTRYPOINT
      7. For each requirements.txt file found:
         - Verifies file is not empty
         - Checks each line for proper package specification format
      8. For each check, output a formatted tree node with a status icon:
         ✅ if the check passed,
         ⚠ if a warning condition is met,
         ❌ if the check failed.
       The output for each component is presented as a tree with proper indentation.
      9. At the end, output a summary of the results (number of successes, warnings, errors)
         and list the absolute paths of problematic items.
      
Version: 0.1
Author: Speculorg Team
Date: 2025.04.12
History:
    0.1 - Initial version based on check_3_env_files.py and check_2_infrastructure_files.py.

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
GEAR_SYMBOL = "⚙️"
TREE_BRANCH = "├──"
TREE_LAST = "└──"
TREE_PIPE = "│   "
TREE_SPACE = "    "

# ====================================================
# Validation Data Configuration
# ====================================================

# List of docker directories to check
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

# Expected Docker file validation patterns
DOCKERFILE_VALIDATION = {
    "FROM": r"^FROM\s+python:3\.13\.1-slim",
    "WORKDIR": r"^WORKDIR\s+/app",
    "COPY": r"^COPY.*",
    "RUN_PIP": r"^RUN\s+pip\s+install\s+-r\s+requirements\.txt",
    "HEALTHCHECK": r"^HEALTHCHECK\s+CMD.*",
    "EXPOSE": r"^EXPOSE\s+\d+",
    "ENTRYPOINT": r"^ENTRYPOINT\s+\[\"python\",\s+\"main\.py\"\]"
}

# Requirements.txt validation pattern
REQUIREMENTS_VALIDATION = {
    "PACKAGE_SPEC": r"^[a-zA-Z0-9_-]+[a-zA-Z0-9_.-]*==\d+(\.\d+)*$"
}

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

def init_log_file(workspace_root, log_dir=None):
    """Initializes the log file in the logs/ subdirectory."""
    timestamp = get_timestamp()
    if log_dir:
        logs_dir = log_dir
    else:
        logs_dir = os.path.join(workspace_root, "logs")
    
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    log_filename = os.path.join(logs_dir, f"{timestamp}_check_4_Dockerfiles.log")
    with open(log_filename, "w", encoding="utf-8") as log_file:
        log_file.write("====================================================\n")
        log_file.write("Speculorg - Docker Files Check Report\n")
        log_file.write(f"Date: {timestamp}\n")
        log_file.write("====================================================\n\n")
    return log_filename, timestamp

def log_info(message, log_file, console_enabled=True):
    """Logs an info message to the log file and optionally to the console."""
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"[INFO] {message}\n")
    if console_enabled:
        print(f"[INFO] {message}")

def log_warning(message, log_file, console_enabled=True):
    """Logs a warning message to the log file and optionally to the console."""
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"[WARNING] {message}\n")
    if console_enabled:
        print(f"[WARNING] {message}")

def log_error(message, log_file, console_enabled=True):
    """Logs an error message to the log file and optionally to the console."""
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"[ERROR] {message}\n")
    if console_enabled:
        print(f"[ERROR] {message}")

def log_debug(message, log_file, debug_mode, console_enabled=True):
    """Logs a debug message if debug mode is enabled."""
    if debug_mode:
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"[DEBUG] {message}\n")
        if console_enabled:
            print(f"[DEBUG] {message}")

def print_group_header(title, log_file, show_progress):
    """Prints a group header to the log file and optionally to the console."""
    header = f"\n{'-' * 20} {title} {'-' * 20}\n"
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(header)
    if show_progress:
        print(header)

# ====================================================
# File and Directory Validation Functions
# ====================================================
def validate_item_exists(path, item_type="file"):
    """
    Validates if an item (file or directory) exists.
    Returns a tuple (status, message).
    """
    global SUCCESS_COUNT, WARNING_COUNT, ERROR_COUNT, PROBLEM_ITEMS
    
    if os.path.exists(path):
        if (item_type == "file" and os.path.isfile(path)) or (item_type == "dir" and os.path.isdir(path)):
            SUCCESS_COUNT += 1
            return STATUS_OK, ""
        else:
            ERROR_COUNT += 1
            message = f"exists but is not a {item_type}"
            PROBLEM_ITEMS.append((os.path.abspath(path), STATUS_ERR, message))
            return STATUS_ERR, message
    else:
        ERROR_COUNT += 1
        message = f"does not exist"
        PROBLEM_ITEMS.append((os.path.abspath(path), STATUS_ERR, message))
        return STATUS_ERR, message

def validate_dockerfile_content(dockerfile_path, log_file, debug_mode, console_enabled=True):
    """
    Validates the content of a Dockerfile against expected patterns.
    Returns a dictionary of validation results.
    """
    global SUCCESS_COUNT, WARNING_COUNT, ERROR_COUNT, PROBLEM_ITEMS
    
    results = {}
    
    if not os.path.exists(dockerfile_path):
        for check in DOCKERFILE_VALIDATION:
            results[check] = (STATUS_ERR, "Dockerfile does not exist")
        return results
    
    # Read the Dockerfile content
    try:
        with open(dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        log_error(f"Error reading Dockerfile {dockerfile_path}: {e}", log_file, console_enabled)
        for check in DOCKERFILE_VALIDATION:
            results[check] = (STATUS_ERR, f"Error reading file: {e}")
        return results
    
    # Process content line by line, skipping comments
    lines = content.splitlines()
    clean_lines = []
    
    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue
        
        # Skip comment lines
        if line.strip().startswith("#"):
            continue
            
        # For lines with inline comments, keep only the part before the comment
        if "#" in line:
            line = line[:line.index("#")].strip()
            if not line:  # If the line was just a comment
                continue
                
        clean_lines.append(line)
    
    # Initialize all checks to failed
    for check in DOCKERFILE_VALIDATION:
        results[check] = (STATUS_ERR, f"Missing {check} instruction")
    
    # Check each line against validation patterns
    for line in clean_lines:
        for check, pattern in DOCKERFILE_VALIDATION.items():
            if check not in results or results[check][0] != STATUS_OK:  # Only check if not already found
                if re.match(pattern, line):
                    results[check] = (STATUS_OK, "")
                    SUCCESS_COUNT += 1
    
    # Count errors for results that are still in error state
    for check, (status, message) in results.items():
        if status == STATUS_ERR:
            ERROR_COUNT += 1
            PROBLEM_ITEMS.append((os.path.abspath(dockerfile_path), STATUS_ERR, f"{check}: {message}"))
    
    return results

def validate_requirements_content(req_path, log_file, debug_mode, console_enabled=True):
    """
    Validates the content of a requirements.txt file.
    Returns a tuple (status, message, line_issues).
    """
    global SUCCESS_COUNT, WARNING_COUNT, ERROR_COUNT, PROBLEM_ITEMS
    
    if not os.path.exists(req_path):
        ERROR_COUNT += 1
        message = "requirements.txt does not exist"
        PROBLEM_ITEMS.append((os.path.abspath(req_path), STATUS_ERR, message))
        return STATUS_ERR, message, []
    
    # Read the requirements.txt content
    try:
        with open(req_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        log_error(f"Error reading requirements.txt {req_path}: {e}", log_file, console_enabled)
        ERROR_COUNT += 1
        message = f"Error reading file: {e}"
        PROBLEM_ITEMS.append((os.path.abspath(req_path), STATUS_ERR, message))
        return STATUS_ERR, message, []
    
    # Check if file is empty
    if not content.strip():
        ERROR_COUNT += 1
        message = "requirements.txt is empty"
        PROBLEM_ITEMS.append((os.path.abspath(req_path), STATUS_ERR, message))
        return STATUS_ERR, message, []
    
    # Process content line by line, skipping comments
    lines = content.splitlines()
    clean_lines = []
    line_issues = []
    
    for i, line in enumerate(lines, 1):
        # Skip empty lines
        if not line.strip():
            continue
        
        # Skip comment lines
        if line.strip().startswith("#"):
            continue
            
        # For lines with inline comments, keep only the part before the comment
        if "#" in line:
            line = line[:line.index("#")].strip()
            if not line:  # If the line was just a comment
                continue
                
        clean_lines.append((i, line))
    
    # Check if we have any non-comment lines
    if not clean_lines:
        WARNING_COUNT += 1
        message = "requirements.txt contains only comments or empty lines"
        PROBLEM_ITEMS.append((os.path.abspath(req_path), STATUS_WARN, message))
        return STATUS_WARN, message, []
    
    # Validate each package specification
    for line_num, line in clean_lines:
        if not re.match(REQUIREMENTS_VALIDATION["PACKAGE_SPEC"], line):
            line_issues.append((line_num, line))
    
    if line_issues:
        WARNING_COUNT += 1
        message = f"{len(line_issues)} line(s) with invalid package specification format"
        for line_num, line in line_issues:
            issue_detail = f"Line {line_num}: {line} - invalid format"
            PROBLEM_ITEMS.append((os.path.abspath(req_path), STATUS_WARN, issue_detail))
        return STATUS_WARN, message, line_issues
    
    SUCCESS_COUNT += 1
    return STATUS_OK, "", []

# ====================================================
# Group Validation Functions
# ====================================================
def validate_component_docker_files(component, docker_dir, log_file, show_progress, debug_mode):
    """
    Validates Docker files for a specific component.
    Outputs a tree of check results.
    """
    component_dir = os.path.join(docker_dir, component)
    
    # Check if the component directory exists
    comp_status, comp_msg = validate_item_exists(component_dir, "dir")
    
    line = f"{comp_status} {DIR_SYMBOL} {component}/" + (f" ({comp_msg})" if comp_msg else "")
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(line + "\n")
    if show_progress:
        print(line)
    
    if comp_status != STATUS_OK:
        return
    
    # Check for Dockerfile
    dockerfile_path = os.path.join(component_dir, "Dockerfile")
    df_status, df_msg = validate_item_exists(dockerfile_path, "file")
    
    line = f"{df_status} ├── {FILE_SYMBOL} Dockerfile" + (f" ({df_msg})" if df_msg else "")
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(line + "\n")
    if show_progress:
        print(line)
    
    # Check Dockerfile content if it exists
    if df_status == STATUS_OK:
        df_content_results = validate_dockerfile_content(dockerfile_path, log_file, debug_mode)
        
        for idx, (check, (status, message)) in enumerate(df_content_results.items()):
            is_last = idx == len(df_content_results) - 1
            prefix = "└──" if is_last else "├──"
            
            line = f"{status} │    {prefix} {GEAR_SYMBOL} {check}" + (f" ({message})" if message else "")
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(line + "\n")
            if show_progress:
                print(line)
    
    # Check for requirements.txt
    req_path = os.path.join(component_dir, "requirements.txt")
    req_status, req_msg = validate_item_exists(req_path, "file")
    
    line = f"{req_status} └── {FILE_SYMBOL} requirements.txt" + (f" ({req_msg})" if req_msg else "")
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(line + "\n")
    if show_progress:
        print(line)
    
    # Check requirements.txt content if it exists
    if req_status == STATUS_OK:
        req_content_status, req_content_msg, line_issues = validate_requirements_content(req_path, log_file, debug_mode)
        
        if line_issues:
            for idx, (line_num, line) in enumerate(line_issues):
                is_last = idx == len(line_issues) - 1
                prefix = "└──" if is_last else "├──"
                
                line_msg = f"Line {line_num}: {line} - invalid format"
                line_out = f"{STATUS_WARN}      {prefix} {GEAR_SYMBOL} {line_msg}"
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(line_out + "\n")
                if show_progress:
                    print(line_out)
        elif req_content_status != STATUS_OK:
            line_out = f"{req_content_status}      └── {GEAR_SYMBOL} {req_content_msg}"
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(line_out + "\n")
            if show_progress:
                print(line_out)

def print_problem_items(log_file, show_progress):
    """Prints the list of problem items."""
    if not PROBLEM_ITEMS:
        return
    
    header = "\n=============================================\n"
    header += "Problematic Items (Absolute Paths):\n"
    header += "=============================================\n"
    
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(header)
    if show_progress:
        print(header)
    
    for path, status, message in PROBLEM_ITEMS:
        line = f"{status} {path}: {message}"
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(line + "\n")
        if show_progress:
            print(line)

# ====================================================
# Main Function
# ====================================================
def main():
    parser = argparse.ArgumentParser(
        description="Verifies the presence and content of Dockerfile and requirements.txt files."
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
        timestamp = get_timestamp()

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

    # Define docker directory
    docker_dir = os.path.join(workspace_root, "docker")

    if not os.path.exists(workspace_root):
        if log_enabled:
            log_error(f"Workspace directory does not exist: {workspace_root}", log_file, console_enabled)
        else:
            print(f"{STATUS_ERR} Workspace directory does not exist: {workspace_root}")
        sys.exit(1)

    if not os.path.exists(docker_dir):
        if log_enabled:
            log_error(f"Docker directory does not exist: {docker_dir}", log_file, console_enabled)
        else:
            print(f"{STATUS_ERR} Docker directory does not exist: {docker_dir}")
        sys.exit(1)

    log_info("Starting Docker files check...", log_file, console_enabled)

    # Check Service Dockerfiles
    print_group_header("Service Dockerfiles", log_file, show_progress)
    for service in SERVICES:
        validate_component_docker_files(service, docker_dir, log_file, show_progress, debug_mode)
        if show_progress:
            print()  # Add blank line after each component for better readability

    # Check Module Dockerfiles
    print_group_header("Module Dockerfiles", log_file, show_progress)
    for module in MODULES:
        validate_component_docker_files(module, docker_dir, log_file, show_progress, debug_mode)
        if show_progress:
            print()  # Add blank line after each component for better readability

    finish_message = (
        "\n---------------------------------------------\n"
        "Docker files check completed.\n"
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

    # Print problematic items if any
    if log_enabled and (WARNING_COUNT > 0 or ERROR_COUNT > 0):
        print_problem_items(log_file, show_progress)

if __name__ == "__main__":
    main() 