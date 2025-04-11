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
         - Confirms proper COPY instructions for source code and validates that the COPY path contains the expected substring (../../services/ for microservices, ../../modules/ for modules)
         - Checks for RUN pip install command (accepting optional --no-cache-dir)
         - Verifies HEALTHCHECK configuration (allowing optional parameters)
         - Confirms EXPOSE instruction with port
         - Checks for proper ENTRYPOINT (should be ENTRYPOINT ["python", "main.py"])
      7. For each requirements.txt file found:
         - Verifies file is not empty
         - Checks each non-comment line for proper package specification format (e.g. package==version)
      8. For each check, output a formatted tree node with a status icon:
         ✅ if the check passed,
         ⚠ if a warning condition is met,
         ❌ if the check failed.
         The output for each component is presented as a tree with proper indentation.
      9. At the end, output in this order:
         - List of problematic items with absolute paths
         - Summary of results (number of successes, warnings, errors)
         - Path to the log file

Version: 0.3
Author: Speculorg Team
Date: 2025.04.13
History:
    0.1 - Initial version based on check_3_env_files.py and check_2_infrastructure_files.py.
    0.2 - Updated per user requirements: swapped output blocks, expanded regex patterns, added path comparison and modularized functions.
    0.3 - Refactored: reorganized output blocks order, improved readability with empty lines, split checks into separate functions with comments.

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

# Expanded Dockerfile validation patterns
DOCKERFILE_VALIDATION = {
    "FROM": r"^FROM\s+python:3\.13\.1-slim",
    "WORKDIR": r"^WORKDIR\s+/app",
    "COPY": r"^COPY\s+.*",  # General COPY instruction; detailed check is done separately
    "RUN_PIP": r"^RUN\s+pip\s+install\s+(--no-cache-dir\s+)?-r\s+requirements\.txt",
    "HEALTHCHECK": r"^HEALTHCHECK\s+(--interval=[0-9]+s\s+--timeout=[0-9]+s\s+--retries=[0-9]+\s+)?CMD(\s+\[.*\]|.*)",
    "EXPOSE": r"^EXPOSE\s+\d+",
    "ENTRYPOINT": r"^ENTRYPOINT\s+\[\s*\"python\",\s*\"main\.py\"\s*\]"
}

# Requirements.txt validation pattern (unchanged)
REQUIREMENTS_VALIDATION = {
    "PACKAGE_SPEC": r"^[a-zA-Z0-9_-]+[a-zA-Z0-9_.-]*==\d+(\.\d+)*$"
}

# ====================================================
# Global Counters and Problem Items
# ====================================================
SUCCESS_COUNT = 0
WARNING_COUNT = 0
ERROR_COUNT = 0
PROBLEM_ITEMS = []  # List to store (absolute_path, status, message)

# ====================================================
# Logging and Utility Functions
# ====================================================
def get_timestamp():
    now = datetime.datetime.now()
    return now.strftime("%Y.%m.%d_%H-%M")

def init_log_file(workspace_root, log_dir=None):
    timestamp = get_timestamp()
    logs_dir = log_dir if log_dir else os.path.join(workspace_root, "logs")
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
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"[INFO] {message}\n")
    if console_enabled:
        print(f"[INFO] {message}")

def log_warning(message, log_file, console_enabled=True):
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"[WARNING] {message}\n")
    if console_enabled:
        print(f"[WARNING] {message}")

def log_error(message, log_file, console_enabled=True):
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"[ERROR] {message}\n")
    if console_enabled:
        print(f"[ERROR] {message}")

def log_debug(message, log_file, debug_mode, console_enabled=True):
    if debug_mode:
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"[DEBUG] {message}\n")
        if console_enabled:
            print(f"[DEBUG] {message}")

def print_group_header(title, log_file, show_progress):
    header = f"\n{'-' * 20} {title} {'-' * 20}\n"
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(header)
        lf.write("\n")  # Add blank line after header
    if show_progress:
        print(header)
        print()  # Add blank line after header

# ====================================================
# File and Directory Validation Functions
# ====================================================
def validate_item_exists(path, item_type="file"):
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
    
    Parameters:
    - dockerfile_path (str): Path to the Dockerfile to validate
    - log_file (str): Path to the log file
    - debug_mode (bool): Whether debug mode is enabled
    - console_enabled (bool): Whether to show output in console
    
    Returns:
    - dict: Results of validation with status and message for each check
    """
    global SUCCESS_COUNT, WARNING_COUNT, ERROR_COUNT, PROBLEM_ITEMS
    results = {}
    
    if not os.path.exists(dockerfile_path):
        for check in DOCKERFILE_VALIDATION:
            results[check] = (STATUS_ERR, "Dockerfile does not exist")
        return results
    
    try:
        with open(dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        log_error(f"Error reading Dockerfile {dockerfile_path}: {e}", log_file, console_enabled)
        for check in DOCKERFILE_VALIDATION:
            results[check] = (STATUS_ERR, f"Error reading file: {e}")
        return results
    
    lines = content.splitlines()
    clean_lines = []
    for line in lines:
        if not line.strip():
            continue
        if line.strip().startswith("#"):
            continue
        if "#" in line:
            line = line[:line.index("#")].strip()
            if not line:
                continue
        clean_lines.append(line)
    
    # Initialize all checks to failed
    for check in DOCKERFILE_VALIDATION:
        results[check] = (STATUS_ERR, f"Missing {check} instruction")
    
    # Check each line against validation patterns using individual check functions
    for line in clean_lines:
        if results["FROM"][0] != STATUS_OK and check_dockerfile_base_image(dockerfile_path, line):
            results["FROM"] = (STATUS_OK, "")
            SUCCESS_COUNT += 1
            
        if results["WORKDIR"][0] != STATUS_OK and check_dockerfile_workdir(dockerfile_path, line):
            results["WORKDIR"] = (STATUS_OK, "")
            SUCCESS_COUNT += 1
            
        if results["COPY"][0] != STATUS_OK and check_dockerfile_copy(dockerfile_path, line):
            results["COPY"] = (STATUS_OK, "")
            SUCCESS_COUNT += 1
            
        if results["RUN_PIP"][0] != STATUS_OK and check_dockerfile_run_pip(dockerfile_path, line):
            results["RUN_PIP"] = (STATUS_OK, "")
            SUCCESS_COUNT += 1
            
        if results["HEALTHCHECK"][0] != STATUS_OK and check_dockerfile_healthcheck(dockerfile_path, line):
            results["HEALTHCHECK"] = (STATUS_OK, "")
            SUCCESS_COUNT += 1
            
        if results["EXPOSE"][0] != STATUS_OK and check_dockerfile_expose(dockerfile_path, line):
            results["EXPOSE"] = (STATUS_OK, "")
            SUCCESS_COUNT += 1
            
        if results["ENTRYPOINT"][0] != STATUS_OK and check_dockerfile_entrypoint(dockerfile_path, line):
            results["ENTRYPOINT"] = (STATUS_OK, "")
            SUCCESS_COUNT += 1
    
    # Count errors for results that are still in error state
    for check, (status, message) in results.items():
        if status == STATUS_ERR:
            ERROR_COUNT += 1
            PROBLEM_ITEMS.append((os.path.abspath(dockerfile_path), STATUS_ERR, f"{check}: {message}"))
    
    return results

def validate_requirements_content(req_path, log_file, debug_mode, console_enabled=True):
    global SUCCESS_COUNT, WARNING_COUNT, ERROR_COUNT, PROBLEM_ITEMS
    if not os.path.exists(req_path):
        ERROR_COUNT += 1
        message = "requirements.txt does not exist"
        PROBLEM_ITEMS.append((os.path.abspath(req_path), STATUS_ERR, message))
        return STATUS_ERR, message, []
    
    try:
        with open(req_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        log_error(f"Error reading requirements.txt {req_path}: {e}", log_file, console_enabled)
        ERROR_COUNT += 1
        message = f"Error reading file: {e}"
        PROBLEM_ITEMS.append((os.path.abspath(req_path), STATUS_ERR, message))
        return STATUS_ERR, message, []
    
    if not content.strip():
        ERROR_COUNT += 1
        message = "requirements.txt is empty"
        PROBLEM_ITEMS.append((os.path.abspath(req_path), STATUS_ERR, message))
        return STATUS_ERR, message, []
    
    lines = content.splitlines()
    clean_lines = []
    line_issues = []
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if line.strip().startswith("#"):
            continue
        if "#" in line:
            line = line[:line.index("#")].strip()
            if not line:
                continue
        clean_lines.append((i, line))
    
    if not clean_lines:
        WARNING_COUNT += 1
        message = "requirements.txt contains only comments or empty lines"
        PROBLEM_ITEMS.append((os.path.abspath(req_path), STATUS_WARN, message))
        return STATUS_WARN, message, []
    
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
# New Function: Validate COPY Paths in Dockerfile
# ====================================================
def validate_copy_paths(dockerfile_path, component, log_file, debug_mode, console_enabled=True):
    """
    Validates that COPY instructions in the Dockerfile contain the expected path
    based on the component type:
      - For microservices (if component in SERVICES): expected to include "../../services/"
      - For modules (if component in MODULES): expected to include "../../modules/"
      
    Ignores COPY instructions that copy requirements.txt to avoid false positives.
    
    Parameters:
    - dockerfile_path (str): Path to the Dockerfile
    - component (str): Component name
    - log_file (str): Path to the log file
    - debug_mode (bool): Whether debug mode is enabled
    - console_enabled (bool): Whether to show output in console
    
    Returns:
    - list: List of tuples (line_number, warning_message) for invalid COPY instructions
    """
    global WARNING_COUNT, PROBLEM_ITEMS
    
    expected_substring = ""
    if component in SERVICES:
        expected_substring = "../../services/"
    elif component in MODULES:
        expected_substring = "../../modules/"
    
    warnings = []
    
    try:
        with open(dockerfile_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        log_error(f"Error reading Dockerfile for COPY check {dockerfile_path}: {e}", log_file, console_enabled)
        return warnings
    
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("COPY"):
            # Remove inline comments if any
            if "#" in stripped:
                stripped = stripped[:stripped.index("#")].strip()
                
            # Skip COPY instructions for requirements.txt which are typically:
            # COPY requirements.txt .
            if "requirements.txt" in stripped:
                continue
                
            # Check if the COPY instruction for source code contains the expected path
            if expected_substring and expected_substring not in stripped:
                warning_msg = f"COPY instruction does not contain expected path '{expected_substring}'"
                warnings.append((i, warning_msg))
                
                # Add to problem items but don't show in console (to avoid disrupting tree structure)
                PROBLEM_ITEMS.append((os.path.abspath(dockerfile_path), STATUS_WARN, f"Line {i}: {warning_msg}"))
                WARNING_COUNT += 1
                
                # Log only to file, not to console
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(f"[WARNING] {dockerfile_path}: Line {i}: {warning_msg}\n")
    
    return warnings

# ====================================================
# Group Validation Function for a Component
# ====================================================
def validate_component_docker_files(component, docker_dir, log_file, show_progress, debug_mode):
    """
    Validates Docker files for a specific component.
    
    Parameters:
    - component (str): Component name
    - docker_dir (str): Docker directory
    - log_file (str): Path to the log file
    - show_progress (bool): Whether to show progress in console
    - debug_mode (bool): Whether debug mode is enabled
    """
    component_dir = os.path.join(docker_dir, component)
    comp_status, comp_msg = validate_item_exists(component_dir, "dir")
    line = f"{comp_status} {DIR_SYMBOL} {component}/" + (f" ({comp_msg})" if comp_msg else "")
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(line + "\n")
    if show_progress:
        print(line)
    
    if comp_status != STATUS_OK:
        return
    
    # Validate Dockerfile existence and content
    dockerfile_path = os.path.join(component_dir, "Dockerfile")
    df_status, df_msg = validate_item_exists(dockerfile_path, "file")
    line = f"{df_status} ├── {FILE_SYMBOL} Dockerfile" + (f" ({df_msg})" if df_msg else "")
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(line + "\n")
    if show_progress:
        print(line)
    
    if df_status == STATUS_OK:
        # First run COPY validation to avoid disrupting tree structure
        copy_warnings = validate_copy_paths(dockerfile_path, component, log_file, debug_mode, False)  # Don't output to console
        
        # Then validate the rest of Dockerfile content
        df_content_results = validate_dockerfile_content(dockerfile_path, log_file, debug_mode)
        
        # Display validation results
        for idx, (check, (status, message)) in enumerate(df_content_results.items()):
            is_last = idx == len(df_content_results) - 1 and not copy_warnings
            prefix = "└──" if is_last else "├──"
            line = f"{status} │    {prefix} {GEAR_SYMBOL} {check}" + (f" ({message})" if message else "")
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(line + "\n")
            if show_progress:
                print(line)
        
        # Display COPY warnings within the tree structure
        for idx, (line_num, warn_msg) in enumerate(copy_warnings):
            is_last = idx == len(copy_warnings) - 1
            prefix = "└──" if is_last else "├──"
            line = f"{STATUS_WARN} │    {prefix} {GEAR_SYMBOL} Line {line_num}: {warn_msg}"
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(line + "\n")
            if show_progress:
                print(line)
    
    # Validate requirements.txt existence and content
    req_path = os.path.join(component_dir, "requirements.txt")
    req_status, req_msg = validate_item_exists(req_path, "file")
    line = f"{req_status} └── {FILE_SYMBOL} requirements.txt" + (f" ({req_msg})" if req_msg else "")
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(line + "\n")
    if show_progress:
        print(line)
    
    if req_status == STATUS_OK:
        req_content_status, req_content_msg, line_issues = validate_requirements_content(req_path, log_file, debug_mode)
        
        if line_issues:
            for idx, (line_num, issue_line) in enumerate(line_issues):
                prefix = "└──" if idx == len(line_issues) - 1 else "├──"
                line_msg = f"Line {line_num}: {issue_line} - invalid format"
                out_line = f"{STATUS_WARN}      {prefix} {GEAR_SYMBOL} {line_msg}"
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(out_line + "\n")
                if show_progress:
                    print(out_line)
        elif req_content_status != STATUS_OK:
            indent = "      └──"
            out_line = f"{req_content_status}{indent} {GEAR_SYMBOL} {req_content_msg}"
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(out_line + "\n")
            if show_progress:
                print(out_line)

# ====================================================
# New Function: Print Problematic Items
# ====================================================
def print_problem_items(log_file, show_progress):
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
    """
    Main execution function that parses arguments, initializes configurations,
    and orchestrates the Docker files verification process.
    """
    parser = argparse.ArgumentParser(
        description="Verifies the presence and content of Dockerfile and requirements.txt files."
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode.")
    parser.add_argument("--no-progress", action="store_true", help="Hide progress messages.")
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH, help="Set maximum recursion depth (default: 10).")
    parser.add_argument("--workspace", type=str, default=DEFAULT_WORKSPACE_ROOT, help="Set workspace root directory (default: current directory).")
    parser.add_argument("--no-log", action="store_true", help="Disable logging to file.")
    parser.add_argument("--no-console", action="store_true", help="Disable console output.")
    parser.add_argument("--log-dir", type=str, help="Set custom log directory.")
    args = parser.parse_args()

    debug_mode = args.debug
    show_progress = not args.no_progress
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
        f" - Maximum Recursion Depth: {DEFAULT_MAX_DEPTH}\n"
        f" - Debug Mode: {debug_mode}\n\n"
    )
    if log_enabled:
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(runtime_info)
    if show_progress and console_enabled:
        print(runtime_info)

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

    print_group_header("Service Dockerfiles", log_file, show_progress)
    
    for service in SERVICES:
        validate_component_docker_files(service, docker_dir, log_file, show_progress, debug_mode)
        # Add blank line after each service for better readability
        add_blank_line(log_file, show_progress)

    print_group_header("Module Dockerfiles", log_file, show_progress)
    
    for module in MODULES:
        validate_component_docker_files(module, docker_dir, log_file, show_progress, debug_mode)
        # Add blank line after each module for better readability
        add_blank_line(log_file, show_progress)

    # First print problematic items (if any)
    if log_enabled and (WARNING_COUNT > 0 or ERROR_COUNT > 0):
        print_problem_items(log_file, show_progress)

    # Then print the results summary
    finish_message = (
        "\n---------------------------------------------\n"
        "Docker files check completed.\n"
        f"Results:\n"
        f"   Successes: {SUCCESS_COUNT}\n"
        f"   Warnings: {WARNING_COUNT}\n"
        f"   Errors: {ERROR_COUNT}\n"
        f"Log file path: {log_file if log_file else 'N/A'}\n"
        "---------------------------------------------\n"
    )
    if log_enabled:
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(finish_message)
    if show_progress and console_enabled:
        print(finish_message)

# ====================================================
# Function to add a blank line in the output for better readability
# ====================================================
def add_blank_line(log_file, show_progress):
    """
    Adds a blank line to both the log file and console output for improved readability.
    
    Parameters:
    - log_file (str): Path to the log file
    - show_progress (bool): Whether to show progress in console
    """
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write("\n")
    if show_progress:
        print()

# ====================================================
# Split the validation of Dockerfile contents into separate functions
# ====================================================
def check_dockerfile_base_image(dockerfile_path, line):
    """
    Checks if the Dockerfile contains the correct base image.
    
    Parameters:
    - dockerfile_path (str): Path to the Dockerfile
    - line (str): Line from the Dockerfile to check
    
    Returns:
    - bool: True if the line matches the FROM pattern, False otherwise
    """
    return re.match(DOCKERFILE_VALIDATION["FROM"], line) is not None

def check_dockerfile_workdir(dockerfile_path, line):
    """
    Checks if the Dockerfile sets the correct working directory.
    
    Parameters:
    - dockerfile_path (str): Path to the Dockerfile
    - line (str): Line from the Dockerfile to check
    
    Returns:
    - bool: True if the line matches the WORKDIR pattern, False otherwise
    """
    return re.match(DOCKERFILE_VALIDATION["WORKDIR"], line) is not None

def check_dockerfile_copy(dockerfile_path, line):
    """
    Checks if the Dockerfile has a COPY instruction.
    
    Parameters:
    - dockerfile_path (str): Path to the Dockerfile
    - line (str): Line from the Dockerfile to check
    
    Returns:
    - bool: True if the line matches the COPY pattern, False otherwise
    """
    return re.match(DOCKERFILE_VALIDATION["COPY"], line) is not None

def check_dockerfile_run_pip(dockerfile_path, line):
    """
    Checks if the Dockerfile includes the correct pip install command.
    
    Parameters:
    - dockerfile_path (str): Path to the Dockerfile
    - line (str): Line from the Dockerfile to check
    
    Returns:
    - bool: True if the line matches the RUN_PIP pattern, False otherwise
    """
    return re.match(DOCKERFILE_VALIDATION["RUN_PIP"], line) is not None

def check_dockerfile_healthcheck(dockerfile_path, line):
    """
    Checks if the Dockerfile includes a HEALTHCHECK instruction.
    
    Parameters:
    - dockerfile_path (str): Path to the Dockerfile
    - line (str): Line from the Dockerfile to check
    
    Returns:
    - bool: True if the line matches the HEALTHCHECK pattern, False otherwise
    """
    return re.match(DOCKERFILE_VALIDATION["HEALTHCHECK"], line) is not None

def check_dockerfile_expose(dockerfile_path, line):
    """
    Checks if the Dockerfile exposes the correct port.
    
    Parameters:
    - dockerfile_path (str): Path to the Dockerfile
    - line (str): Line from the Dockerfile to check
    
    Returns:
    - bool: True if the line matches the EXPOSE pattern, False otherwise
    """
    return re.match(DOCKERFILE_VALIDATION["EXPOSE"], line) is not None

def check_dockerfile_entrypoint(dockerfile_path, line):
    """
    Checks if the Dockerfile sets the correct entrypoint.
    
    Parameters:
    - dockerfile_path (str): Path to the Dockerfile
    - line (str): Line from the Dockerfile to check
    
    Returns:
    - bool: True if the line matches the ENTRYPOINT pattern, False otherwise
    """
    return re.match(DOCKERFILE_VALIDATION["ENTRYPOINT"], line) is not None

if __name__ == "__main__":
    main()
