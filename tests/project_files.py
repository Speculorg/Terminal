#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Project Structure Analyzer
Version: 0.1
Author: Speculorg Team
Description: Script for analyzing and visualizing project directory structure
Algorithm: Recursive directory traversal with tree-like visualization
Version History:
    - 0.1: Initial version with basic functionality
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional


# Constants
SCRIPT_VERSION = "0.1"
SCRIPT_AUTHOR = "AI Assistant"
SCRIPT_DESCRIPTION = "Project Structure Analyzer"
LOG_DIR = "logs"  # Directory for log files
ROOT_DIR = "."    # Directory to analyze
TREE_SYMBOLS = {
    'branch': '  ├',
    'last_branch': '  └',
    'vertical': '  │',
    'horizontal': '─'
}
ICONS = {
    'directory': '📁',
    'file': '📄'
}


class ProjectAnalyzer:
    """Main class for project structure analysis"""

    def __init__(self, root_dir: str, exclude_dirs: Optional[List[str]] = None):
        """
        Initialize the analyzer

        Args:
            root_dir (str): Root directory to analyze
            exclude_dirs (List[str], optional): Directories to exclude
        """
        self.root_dir = Path(root_dir).resolve()
        self.exclude_dirs = exclude_dirs or ['.git', '__pycache__', 'venv', '.env']
        self.start_time = None
        self.end_time = None
        self.stats = {
            'total_dirs': 0,
            'total_files': 0,
            'total_size': 0
        }

    def setup_logging(self) -> str:
        """
        Setup logging configuration

        Returns:
            str: Path to the log file
        """
        log_dir = Path(LOG_DIR)
        log_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y.%m.%d_%H-%M')
        log_file = log_dir / f'{timestamp}_project_files_result.log'

        logging.basicConfig(
            level=logging.INFO,
            format='%(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )

        return str(log_file)

    def get_directory_size(self, path: Path) -> int:
        """
        Calculate total size of directory

        Args:
            path (Path): Directory path

        Returns:
            int: Total size in bytes
        """
        total_size = 0
        for dirpath, _, filenames in os.walk(path):
            for filename in filenames:
                file_path = Path(dirpath) / filename
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        return total_size

    def format_size(self, size_bytes: int) -> str:
        """
        Format size in bytes to human readable format

        Args:
            size_bytes (int): Size in bytes

        Returns:
            str: Formatted size string
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

    def sort_items(self, items: List[Path]) -> List[Path]:
        """
        Sort items: directories first, then files, both alphabetically

        Args:
            items (List[Path]): List of paths to sort

        Returns:
            List[Path]: Sorted list of paths
        """
        # Split into directories and files
        dirs = [item for item in items if item.is_dir()]
        files = [item for item in items if item.is_file()]

        # Sort each list alphabetically
        dirs.sort(key=lambda x: x.name.lower())
        files.sort(key=lambda x: x.name.lower())

        # Return combined list with directories first
        return dirs + files

    def print_tree(self, path: Path, prefix: str = '', is_last: bool = True,
                  is_root: bool = False) -> None:
        """
        Print directory tree structure

        Args:
            path (Path): Current path to process
            prefix (str): Prefix for current level
            is_last (bool): Whether current item is last in its level
            is_root (bool): Whether this is the root directory
        """
        # Skip excluded directories
        if path.name in self.exclude_dirs:
            return

        # Update statistics
        if path.is_dir():
            self.stats['total_dirs'] += 1
            size = self.get_directory_size(path)
            self.stats['total_size'] += size

            # Print directory
            if is_root:
                logging.info(f"{ICONS['directory']} {path.name}/")
            else:
                branch = TREE_SYMBOLS['last_branch'] if is_last else TREE_SYMBOLS['branch']
                logging.info(
                    f"{prefix}{branch}{TREE_SYMBOLS['horizontal']} "
                    f"{ICONS['directory']} {path.name}/"
                )

            # Process contents
            items = self.sort_items(list(path.iterdir()))
            for i, item in enumerate(items):
                is_last_item = i == len(items) - 1
                new_prefix = prefix + (' ' if is_last else f"{TREE_SYMBOLS['vertical']} ")
                self.print_tree(item, new_prefix, is_last_item)
        else:
            self.stats['total_files'] += 1
            size = path.stat().st_size
            self.stats['total_size'] += size

            # Print file
            branch = TREE_SYMBOLS['last_branch'] if is_last else TREE_SYMBOLS['branch']
            logging.info(
                f"{prefix}{branch}{TREE_SYMBOLS['horizontal']} "
                f"{ICONS['file']} {path.name} ({self.format_size(size)})"
            )

    def print_header(self) -> None:
        """Print analysis header with environment information"""
        logging.info("=" * 50)
        logging.info("Project Structure Analysis")
        logging.info("=" * 50)
        logging.info(f"Script Version: {SCRIPT_VERSION}")
        logging.info(f"Author: {SCRIPT_AUTHOR}")
        logging.info(f"Description: {SCRIPT_DESCRIPTION}")
        logging.info(f"Start Time: {self.start_time}")
        logging.info(f"Root Directory: {self.root_dir}")
        logging.info(f"Python Version: {sys.version}")
        logging.info(f"Platform: {sys.platform}")
        logging.info("-" * 50)

    def print_statistics(self) -> None:
        """Print analysis statistics"""
        logging.info("-" * 50)
        logging.info("Statistics:")
        logging.info(f"Total Directories: {self.stats['total_dirs']}")
        logging.info(f"Total Files: {self.stats['total_files']}")
        logging.info(f"Total Size: {self.format_size(self.stats['total_size'])}")
        logging.info("-" * 50)

    def analyze(self) -> str:
        """
        Perform project structure analysis

        Returns:
            str: Path to the log file
        """
        self.start_time = datetime.now()
        log_file = self.setup_logging()

        self.print_header()
        # Print the tree starting from the root directory
        self.print_tree(self.root_dir, is_root=True)
        self.print_statistics()

        self.end_time = datetime.now()
        duration = self.end_time - self.start_time

        logging.info("=" * 50)
        logging.info(f"Analysis completed at: {self.end_time}")
        logging.info(f"Duration: {duration}")
        logging.info(f"Log file: {log_file}")
        logging.info("=" * 50)

        return log_file


def main():
    """Main entry point"""
    analyzer = ProjectAnalyzer(ROOT_DIR)
    log_file = analyzer.analyze()
    print(f"\nAnalysis completed. Results saved to: {log_file}")


if __name__ == '__main__':
    main()
