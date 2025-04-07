#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script: check_project_files.py
Description:
    This script recursively scans the current workspace directory, displays the file and directory
    tree structure using proper tree symbols, and logs the output along with detailed debug information.
    
    The algorithm steps are as follows:
      1. Parse command line arguments for options:
         --debug, --no-progress, --max-depth N, --workspace PATH, --help.
      2. Set configuration parameters (workspace root, debug mode, progress output, maximum recursion depth,
         excluded directories and files, tree symbols).
      3. Generate a timestamp (format: YYYY.MM.DD_HH-MM) and create a log file in the logs/ directory.
      4. Write a header and runtime environment information (workspace, OS version, max depth, debug mode)
         to the log file and, if enabled, to the console.
      5. Recursively traverse the workspace directory up to the specified maximum depth:
         - For each directory, list files and subdirectories separately.
         - Skip files and directories matching the excluded patterns.
         - Output each file and directory as a tree node using symbols:
           TREE_BRANCH (├──) or TREE_LAST (└──) depending on its position.
      6. At the end, output a finish message to the log and to the console if progress output is enabled.
      
Version: 0.3
Author: Speculorg Team
Date: 2025.04.07
History:
    0.1 - Initial implementation in batch.
    0.2 - Added runtime environment information and improved finish block in batch.
    0.3 - Ported to Python with modular, readable, and well-documented code.
"""

import os
import sys
import argparse
import datetime
import platform
import fnmatch

# ====================================================
# Configuration Parameters (Speculorg Standards)
# ====================================================
DEFAULT_WORKSPACE_ROOT = os.getcwd()  # Workspace root directory
DEFAULT_DEBUG_MODE = True             # Debug mode enabled by default
DEFAULT_SHOW_PROGRESS = True          # Show progress messages
DEFAULT_MAX_DEPTH = 10                # Maximum recursion depth

# Excluded directories and file patterns (lists)
EXCLUDE_DIRS = [".git", ".vscode", "__pycache__"]
EXCLUDE_FILES = ["*.pyc", "*.pyo", "*.pyd", "*.so", "*.dll", "*.exe"]

# Tree symbols for output
DIR_SYMBOL = "📁"
FILE_SYMBOL = "📄"
TREE_BRANCH = "├──"
TREE_LAST = "└──"
TREE_PIPE = "│    "
TREE_SPACE = "     "

# ====================================================
# Logging Initialization
# ====================================================
def get_timestamp():
    """Returns current timestamp in format YYYY.MM.DD_HH-MM."""
    now = datetime.datetime.now()
    return now.strftime("%Y.%m.%d_%H-%M")

def init_log_file(workspace_root):
    """Initializes the log file in the logs/ subdirectory of workspace_root."""
    timestamp = get_timestamp()
    logs_dir = os.path.join(workspace_root, "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    log_filename = os.path.join(logs_dir, f"{timestamp}_check_project_files_result.log")
    with open(log_filename, "w", encoding="utf-8") as log_file:
        log_file.write("Speculorg - Project Structure Report\n")
        log_file.write(f"Date: {timestamp}\n")
        log_file.write("---------------------------------------------\n\n")
    return log_filename, timestamp

# ====================================================
# Debug Logging Function
# ====================================================
def log_debug(message, log_file, show_progress):
    """Logs a debug message with a timestamp if debug mode is enabled."""
    debug_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    debug_message = f"[DEBUG] [{debug_time}] {message}\n"
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(debug_message)
    if show_progress:
        print(debug_message, end="")

# ====================================================
# Recursive Directory Traversal
# ====================================================
def is_excluded_file(filename):
    """Returns True if filename matches any of the EXCLUDE_FILES patterns."""
    for pattern in EXCLUDE_FILES:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False

def is_excluded_dir(dirname):
    """Returns True if dirname is in the EXCLUDE_DIRS list."""
    return dirname in EXCLUDE_DIRS

def process_dir(current_dir, prefix, depth, max_depth, workspace_root, debug_mode, show_progress, log_file):
    """
    Recursively processes a directory:
      - Lists files and directories (excluding those that match patterns).
      - Prints each item with proper tree symbols.
      - Recurses into directories if depth < max_depth.
    """
    if depth >= max_depth:
        return

    # Check if current_dir exists
    if not os.path.exists(current_dir):
        log_debug(f"WARNING: Directory '{current_dir}' does not exist. Skipping...", log_file, show_progress)
        return

    # Get files and directories separately
    try:
        items = os.listdir(current_dir)
    except Exception as e:
        log_debug(f"ERROR: Cannot list directory '{current_dir}': {e}", log_file, show_progress)
        return

    files = [item for item in items if os.path.isfile(os.path.join(current_dir, item)) and not is_excluded_file(item)]
    dirs  = [item for item in items if os.path.isdir(os.path.join(current_dir, item)) and not is_excluded_dir(item)]
    
    # Process files first
    num_files = len(files)
    for index, filename in enumerate(files):
        is_last = (index == num_files - 1 and len(dirs) == 0)
        symbol = TREE_LAST if is_last else TREE_BRANCH
        line = f"{prefix}{symbol} {FILE_SYMBOL} {filename}"
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(line + "\n")
        if show_progress:
            print(line)
    
    # Process directories
    num_dirs = len(dirs)
    for index, dirname in enumerate(dirs):
        is_last = (index == num_dirs - 1)
        symbol = TREE_LAST if is_last else TREE_BRANCH
        line = f"{prefix}{symbol} {DIR_SYMBOL} {dirname}/"
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(line + "\n")
        if show_progress:
            print(line)
        # Compute new prefix for subdirectories
        new_prefix = prefix + (TREE_SPACE if is_last else TREE_PIPE)
        subdir = os.path.join(current_dir, dirname)
        process_dir(subdir, new_prefix, depth + 1, max_depth, workspace_root, debug_mode, show_progress, log_file)

# ====================================================
# Main Function
# ====================================================
def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Recursively scan the workspace directory and output the project structure as a tree."
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode.")
    parser.add_argument("--no-progress", action="store_true", help="Hide progress messages.")
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH,
                        help="Set maximum recursion depth (default: 10).")
    parser.add_argument("--workspace", type=str, default=DEFAULT_WORKSPACE_ROOT,
                        help="Set workspace root directory (default: current directory).")
    args = parser.parse_args()

    debug_mode = args.debug if args.debug is not None else DEFAULT_DEBUG_MODE
    show_progress = not args.no_progress
    max_depth = args.max_depth
    workspace_root = os.path.abspath(args.workspace)

    # Initialize log file
    log_file, timestamp = init_log_file(workspace_root)

    # Log runtime environment information
    os_version = platform.platform()
    runtime_info = (
        "\nRuntime Environment Information:\n"
        f" - Workspace Root: {workspace_root}\n"
        f" - OS Version: {os_version}\n"
        f" - Maximum Recursion Depth: {max_depth}\n"
        f" - Debug Mode: {debug_mode}\n\n"
    )
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(runtime_info)
    if show_progress:
        print(runtime_info)

    # Get workspace root folder name and log it
    root_name = os.path.basename(workspace_root)
    header_line = f"{DIR_SYMBOL} {root_name}/"
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(header_line + "\n")
    if show_progress:
        print(header_line)

    # Start recursive processing from the workspace root
    process_dir(workspace_root, "", 0, max_depth, workspace_root, debug_mode, show_progress, log_file)

    # Finish: log finish message
    finish_message = (
        "\n---------------------------------------------\n"
        "Processing completed.\n"
        f"Results saved in: {log_file}\n"
        "---------------------------------------------\n"
    )
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(finish_message)
    if show_progress:
        print(finish_message)

if __name__ == "__main__":
    main()
