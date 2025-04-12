#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script: check_5_network.py
Description:
    This script checks the network configuration in docker-compose.yml 
    for the Speculorg.Terminal project. It analyzes network structure, 
    IP addresses, and network relationships between services and modules.
    
    The script performs the following checks:
      1. Checking the presence and correctness of docker-compose version
      2. Checking the definition of required networks (speculorg_network, external_network)
      3. Checking IPAM settings and subnets for each network
      4. Checking network configuration of each service:
         - Connection to required networks
         - Presence of static IP addresses
         - Correctness of IP address format
         - Compliance with IP allocation scheme
      5. Checking dependencies between services
      6. Analysis of IP address conflicts
      
    The check results are displayed as a formatted tree with 
    corresponding status symbols and in a detailed text log.

Version: 0.2
Author: Speculorg Team
Date: 2025.04.14
History:
    0.1 - Initial version of the script
    0.2 - Improved version with fixed processing of Docker Compose V2 format, 
          improved tree output and more detailed validation

Visit for more information:
- https://specul.org/ - overview
- https://docs.specul.org/ - documentation
"""

import os
import sys
import re
import yaml
import argparse
import datetime
import platform
from pathlib import Path
from typing import Dict, List, Any, Tuple, Set, Optional
import logging

# ====================================================
# Configuration Parameters (Speculorg Standards)
# ====================================================
DEFAULT_WORKSPACE_ROOT = os.getcwd()  # Workspace root directory
DEFAULT_DEBUG_MODE = False             # Debug mode (can be enabled via --debug)
DEFAULT_SHOW_PROGRESS = True           # Show progress messages
DEFAULT_NO_COLOR = False               # Disable color output

# Status symbols (Unicode for better visual output)
STATUS_OK = "✅"
STATUS_WARN = "⚠"
STATUS_ERR = "❌"
STATUS_INFO = "ℹ"

# Tree symbols for output
DIR_SYMBOL = "📁"
FILE_SYMBOL = "📄"
GEAR_SYMBOL = "⚙️"
NETWORK_SYMBOL = "🌐"
IP_SYMBOL = "🔌"
SERVICE_SYMBOL = "🔧"
TREE_BRANCH = "├──"
TREE_LAST = "└──"
TREE_PIPE = "│   "
TREE_SPACE = "    "

# ASCII alternatives for environments with poor Unicode support
ASCII_STATUS_OK = "[OK]"
ASCII_STATUS_WARN = "[WARN]"
ASCII_STATUS_ERR = "[ERROR]"
ASCII_STATUS_INFO = "[INFO]"
ASCII_DIR_SYMBOL = "[DIR]"
ASCII_FILE_SYMBOL = "[FILE]"
ASCII_GEAR_SYMBOL = "[CFG]"
ASCII_NETWORK_SYMBOL = "[NET]"
ASCII_IP_SYMBOL = "[IP]"
ASCII_SERVICE_SYMBOL = "[SVC]"

# Terminal colors
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    ENDC = "\033[0m"

# ====================================================
# Validation Data Configuration
# ====================================================

# Required networks
REQUIRED_NETWORKS = [
    "speculorg_network",
    "external_network"
]

# Services by category
SERVICES_BY_CATEGORY = {
    "infrastructure": [
        "infrastructure-service",
        "infrastructure-consul-module",
        "infrastructure-vault-module",
        "infrastructure-database-module",
        "infrastructure-redis-module",
        "infrastructure-rabbitmq-module",
        "infrastructure-keycloak-module",
        "infrastructure-traefik-module",
        "infrastructure-opentelemetry-module",
        "infrastructure-prometheus-module",
        "infrastructure-grafana-module",
        "infrastructure-sentry-module",
        "infrastructure-elk-module",
        "infrastructure-docker-module",
        "infrastructure-celery-module"
    ],
    "management": [
        "management-service",
        "management-logs-module",
        "management-configurations-module",
        "management-users-module",
        "management-projects-module",
        "management-settings-module"
    ],
    "security": [
        "security-service",
        "security-audit-module",
        "security-authentication-module",
        "security-authorization-module"
    ]
}

# IP address allocation patterns
IP_ALLOCATION_PATTERNS = {
    "infrastructure-service": r"^172\.20\.1\.1$|^172\.21\.1\.1$",
    "management-service": r"^172\.20\.2\.1$|^172\.21\.2\.1$",
    "security-service": r"^172\.20\.3\.1$|^172\.21\.3\.1$",
    "infrastructure-.*-module": r"^172\.20\.1\.\d+$|^172\.21\.1\.\d+$",
    "management-.*-module": r"^172\.20\.2\.\d+$|^172\.21\.2\.\d+$",
    "security-.*-module": r"^172\.20\.3\.\d+$|^172\.21\.3\.\d+$"
}

# ====================================================
# Global Counters and Problem Items
# ====================================================
SUCCESS_COUNT = 0
WARNING_COUNT = 0
ERROR_COUNT = 0
PROBLEM_ITEMS = []  # List to store (component, aspect, status, message)

# ====================================================
# Logging and Utility Functions
# ====================================================
def get_timestamp():
    """Get current timestamp in YYYY.MM.DD_HH-MM format."""
    now = datetime.datetime.now()
    return now.strftime("%Y.%m.%d_%H-%M")

def init_log_file(workspace_root, log_dir=None):
    """Initialize log file and return its path and timestamp.
    
    Args:
        workspace_root: The root directory of the workspace
        log_dir: Optional custom log directory
        
    Returns:
        Tuple containing log filename and timestamp
    """
    timestamp = get_timestamp()
    logs_dir = log_dir if log_dir else os.path.join(workspace_root, "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    log_filename = os.path.join(logs_dir, f"{timestamp}_check_5_network.log")
    with open(log_filename, "w", encoding="utf-8") as log_file:
        log_file.write("====================================================\n")
        log_file.write("Speculorg - Network Configuration Check Report\n")
        log_file.write(f"Date: {timestamp}\n")
        log_file.write("====================================================\n\n")
    return log_filename, timestamp

def log_message(level, message, log_file, console_enabled=True, no_color=False):
    """Log a message to file and optionally to console.
    
    Args:
        level: Log level ("INFO", "WARNING", "ERROR", "DEBUG")
        message: Message to log
        log_file: Path to the log file
        console_enabled: Whether to print to console
        no_color: Whether to disable colors in console output
    """
    # Strip ANSI color codes for log file
    log_message = re.sub(r'\033\[\d+m', '', message)
    
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"[{level}] {log_message}\n")
    
    if console_enabled:
        if no_color:
            # Strip ANSI color codes for console if colors are disabled
            console_message = re.sub(r'\033\[\d+m', '', message)
            print(f"[{level}] {console_message}")
        else:
            print(f"[{level}] {message}")

def log_info(message, log_file, console_enabled=True, no_color=False):
    """Log an info message."""
    log_message("INFO", message, log_file, console_enabled, no_color)

def log_warning(message, log_file, console_enabled=True, no_color=False):
    """Log a warning message."""
    log_message("WARNING", message, log_file, console_enabled, no_color)
    
def log_error(message, log_file, console_enabled=True, no_color=False):
    """Log an error message."""
    log_message("ERROR", message, log_file, console_enabled, no_color)
    
def log_debug(message, log_file, debug_mode, console_enabled=True, no_color=False):
    """Log a debug message if debug mode is enabled."""
    if debug_mode:
        log_message("DEBUG", message, log_file, console_enabled, no_color)

def print_section_header(title, log_file, show_progress, no_color=False):
    """Print a section header to log file and console.
    
    Args:
        title: Header title
        log_file: Path to the log file
        show_progress: Whether to show output in console
        no_color: Whether to disable colors
    """
    if no_color:
        header = f"\n{'-' * 20} {title} {'-' * 20}\n"
    else:
        header = f"\n{Colors.BOLD}{Colors.CYAN}{'-' * 20} {title} {'-' * 20}{Colors.ENDC}\n"
    
    with open(log_file, "a", encoding="utf-8") as lf:
        # Strip ANSI color codes for log file
        clean_header = re.sub(r'\033\[\d+m', '', header)
        lf.write(clean_header)
        lf.write("\n")  # Add blank line after header
    
    if show_progress:
        print(header)
        print()  # Add blank line after header

def add_blank_line(log_file, show_progress):
    """Add a blank line to log file and console."""
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write("\n")
    if show_progress:
        print()

def format_status(status, message, no_color=False):
    """Format a status message with appropriate color and symbol.
    
    Args:
        status: Status string ("OK", "WARN", "ERROR", "INFO")
        message: Message to format
        no_color: Whether to disable colors
        
    Returns:
        Formatted status message
    """
    if no_color:
        if status == "OK":
            return f"{ASCII_STATUS_OK} {message}"
        elif status == "WARN":
            return f"{ASCII_STATUS_WARN} {message}"
        elif status == "ERROR":
            return f"{ASCII_STATUS_ERR} {message}"
        else:  # INFO
            return f"{ASCII_STATUS_INFO} {message}"
    else:
        if status == "OK":
            return f"{Colors.GREEN}{STATUS_OK} {message}{Colors.ENDC}"
        elif status == "WARN":
            return f"{Colors.YELLOW}{STATUS_WARN} {message}{Colors.ENDC}"
        elif status == "ERROR":
            return f"{Colors.RED}{STATUS_ERR} {message}{Colors.ENDC}"
        else:  # INFO
            return f"{Colors.BLUE}{STATUS_INFO} {message}{Colors.ENDC}"

# ====================================================
# Network Checker Class
# ====================================================
class NetworkChecker:
    """Class to check Docker network configuration in docker-compose.yml."""
    
    def __init__(self, workspace_root: str, docker_compose_path: str, 
                 log_file: str, show_progress: bool = True, 
                 debug_mode: bool = False, no_color: bool = False):
        """Initialize the NetworkChecker.
        
        Args:
            workspace_root: The root directory of the workspace
            docker_compose_path: Path to docker-compose.yml file relative to workspace_root
            log_file: Path to the log file
            show_progress: Whether to show progress in console
            debug_mode: Whether debug mode is enabled
            no_color: Whether to disable colored output
        """
        self.workspace_root = Path(workspace_root)
        self.docker_compose_path = self.workspace_root / docker_compose_path
        self.log_file = log_file
        self.show_progress = show_progress
        self.debug_mode = debug_mode
        self.no_color = no_color
        
        # Setup logger
        self.logger = logging.getLogger("network_checker")
        self.logger.setLevel(logging.DEBUG)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Add version attribute
        self.version = "0.2"
        
        # Add docker_compose_data attribute
        self.docker_compose_data = None
        
        # Add problems attribute
        self.problems = []
        
        # Counters
        self.success_count = 0
        self.warning_count = 0
        self.error_count = 0
        
        # Data structures for analysis
        self.service_networks = {}  # Map service name to IP address
        self.network_addresses = set()  # Set of unique IP addresses
        self.service_categories = {}  # Map service name to category
        
        # Tree output depth tracking
        self.depth = 0

    def _increment_success(self):
        """Increment success counter."""
        self.success_count += 1
        global SUCCESS_COUNT
        SUCCESS_COUNT += 1
        
    def _increment_warning(self):
        """Increment warning counter."""
        self.warning_count += 1
        global WARNING_COUNT
        WARNING_COUNT += 1
        
    def _increment_error(self):
        """Increment error counter."""
        self.error_count += 1
        global ERROR_COUNT
        ERROR_COUNT += 1
    
    def _add_problem_item(self, component, aspect, status, message):
        """Add a problem item to the global list and to the instance problems list."""
        global PROBLEM_ITEMS
        PROBLEM_ITEMS.append((component, aspect, status, message))
        
        # Also add to instance problems list as a dictionary for better access
        self.problems.append({
            "service": component,
            "section": aspect,
            "level": status,
            "message": message
        })
    
    def _get_tree_prefix(self, is_last=False):
        """Get tree branch prefix based on current depth and whether item is last."""
        if self.depth == 0:
            return ""
        
        prefix = ""
        for i in range(self.depth - 1):
            prefix += TREE_PIPE
        
        if is_last:
            prefix += TREE_LAST
        else:
            prefix += TREE_BRANCH
            
        return prefix
    
    def _print_tree_item(self, name, symbol, is_last=False, no_symbol=False):
        """Print a tree item with the appropriate symbol and indentation."""
        prefix = self._get_tree_prefix(is_last)
        
        if self.no_color:
            symbol_to_use = ""
            if not no_symbol:
                if symbol == DIR_SYMBOL:
                    symbol_to_use = ASCII_DIR_SYMBOL + " "
                elif symbol == FILE_SYMBOL:
                    symbol_to_use = ASCII_FILE_SYMBOL + " "
                elif symbol == GEAR_SYMBOL:
                    symbol_to_use = ASCII_GEAR_SYMBOL + " "
                elif symbol == NETWORK_SYMBOL:
                    symbol_to_use = ASCII_NETWORK_SYMBOL + " "
                elif symbol == IP_SYMBOL:
                    symbol_to_use = ASCII_IP_SYMBOL + " "
                elif symbol == SERVICE_SYMBOL:
                    symbol_to_use = ASCII_SERVICE_SYMBOL + " "
            
            message = f"{prefix}{symbol_to_use}{name}"
        else:
            symbol_to_use = ""
            if not no_symbol:
                symbol_to_use = symbol + " "
                
            message = f"{prefix}{symbol_to_use}{name}"
            
        log_info(message, self.log_file, self.show_progress, self.no_color)
        return message
    
    def _print_tree_status_item(self, message, status, is_last=False):
        """Print a tree item with status symbol and message."""
        prefix = self._get_tree_prefix(is_last)
        
        if status == "OK":
            if self.no_color:
                text = f"{prefix}{ASCII_STATUS_OK} {message}"
            else:
                text = f"{prefix}{Colors.GREEN}{STATUS_OK} {message}{Colors.ENDC}"
            log_info(text, self.log_file, self.show_progress, self.no_color)
        elif status == "WARN":
            if self.no_color:
                text = f"{prefix}{ASCII_STATUS_WARN} {message}"
            else:
                text = f"{prefix}{Colors.YELLOW}{STATUS_WARN} {message}{Colors.ENDC}"
            log_warning(text, self.log_file, self.show_progress, self.no_color)
        elif status == "ERROR":
            if self.no_color:
                text = f"{prefix}{ASCII_STATUS_ERR} {message}"
            else:
                text = f"{prefix}{Colors.RED}{STATUS_ERR} {message}{Colors.ENDC}"
            log_error(text, self.log_file, self.show_progress, self.no_color)
        else:  # INFO
            if self.no_color:
                text = f"{prefix}{ASCII_STATUS_INFO} {message}"
            else:
                text = f"{prefix}{Colors.BLUE}{STATUS_INFO} {message}{Colors.ENDC}"
            log_info(text, self.log_file, self.show_progress, self.no_color)
    
    def load_docker_compose(self) -> Dict:
        """Load and parse the docker-compose.yml file.
        
        Returns:
            Dict containing the parsed docker-compose.yml data
        """
        try:
            with open(self.docker_compose_path, 'r') as file:
                compose_data = yaml.safe_load(file)
                # Ensure compose_data is a dictionary
                if not isinstance(compose_data, dict):
                    log_error(f"Invalid docker-compose.yml format: Expected a dictionary, got {type(compose_data)}", 
                              self.log_file, self.show_progress, self.no_color)
                    sys.exit(1)
                self.docker_compose_data = compose_data
                return compose_data
        except FileNotFoundError:
            log_error(f"docker-compose.yml not found at path: {self.docker_compose_path}", 
                      self.log_file, self.show_progress, self.no_color)
            sys.exit(1)
        except yaml.YAMLError as e:
            log_error(f"Failed to parse docker-compose.yml: {e}", 
                      self.log_file, self.show_progress, self.no_color)
            sys.exit(1)
        except Exception as e:
            log_error(f"Unexpected error loading docker-compose.yml: {e}", 
                      self.log_file, self.show_progress, self.no_color)
            sys.exit(1)
    
    def check_version(self, compose_data: Dict) -> bool:
        """Check if the docker-compose version is specified and valid.
        
        Args:
            compose_data: Docker compose configuration dictionary
            
        Returns:
            True if version is valid or not required, False otherwise
        """
        self._print_tree_item("Docker Compose Version", FILE_SYMBOL)
        self.depth += 1
        
        if 'version' not in compose_data:
            # Docker Compose V2 doesn't require version
            message = "No explicit version in docker-compose.yml. Using Docker Compose V2 format."
            self._print_tree_status_item(message, "INFO", True)
            self._increment_success()
            self.depth -= 1
            return True
        
        version = compose_data['version']
        if isinstance(version, str) and re.match(r'^\d+\.\d+$', version):
            message = f"Docker Compose version: {version}"
            self._print_tree_status_item(message, "OK", True)
            self._increment_success()
            self.depth -= 1
            return True
        else:
            message = f"Docker Compose version format is unusual: {version}"
            self._print_tree_status_item(message, "WARN", True)
            self._increment_warning()
            self._add_problem_item("docker-compose.yml", "version", "WARN", message)
            self.depth -= 1
            return False
    
    def check_networks_defined(self, compose_data: Dict) -> bool:
        """Check if the required networks are defined.
        
        Args:
            compose_data: Docker compose configuration dictionary
            
        Returns:
            True if all required networks are defined, False otherwise
        """
        self._print_tree_item("Networks Definition", NETWORK_SYMBOL)
        self.depth += 1
        
        if 'networks' not in compose_data:
            message = "No networks section in docker-compose.yml"
            self._print_tree_status_item(message, "ERROR", True)
            self._increment_error()
            self._add_problem_item("docker-compose.yml", "networks", "ERROR", message)
            self.depth -= 1
            return False
        
        networks = compose_data['networks']
        all_networks_found = True
        network_count = len(networks)
        
        if len(networks) < len(REQUIRED_NETWORKS):
            message = f"Expected at least {len(REQUIRED_NETWORKS)} networks, found {network_count}"
            self._print_tree_status_item(message, "ERROR")
            self._increment_error()
            self._add_problem_item("docker-compose.yml", "networks", "ERROR", message)
            all_networks_found = False
        else:
            message = f"Found {network_count} defined networks"
            self._print_tree_status_item(message, "OK")
            self._increment_success()
            
        # Check for each required network
        for i, network_name in enumerate(REQUIRED_NETWORKS):
            is_last = i == len(REQUIRED_NETWORKS) - 1
            
            if network_name in networks:
                network_config = networks[network_name]
                self._print_tree_item(f"Network: {network_name}", NETWORK_SYMBOL)
                self.depth += 1
                
                # Check IPAM configuration
                if not network_config or not isinstance(network_config, dict):
                    message = f"Network configuration for {network_name} is empty or invalid"
                    self._print_tree_status_item(message, "ERROR", True)
                    self._increment_error()
                    self._add_problem_item(network_name, "config", "ERROR", message)
                    all_networks_found = False
                elif 'ipam' not in network_config:
                    message = f"No IPAM configuration for network {network_name}"
                    self._print_tree_status_item(message, "WARN")
                    self._increment_warning()
                    self._add_problem_item(network_name, "ipam", "WARN", message)
                else:
                    ipam_config = network_config['ipam']
                    if 'config' not in ipam_config or not ipam_config['config']:
                        message = f"Missing subnet configuration in IPAM for network {network_name}"
                        self._print_tree_status_item(message, "ERROR")
                        self._increment_error()
                        self._add_problem_item(network_name, "ipam.config", "ERROR", message)
                        all_networks_found = False
                    else:
                        subnet_configs = ipam_config['config']
                        for j, subnet_config in enumerate(subnet_configs):
                            is_last_subnet = j == len(subnet_configs) - 1
                            
                            if 'subnet' not in subnet_config:
                                message = f"Missing subnet in IPAM config"
                                self._print_tree_status_item(message, "ERROR", is_last_subnet and j == len(subnet_configs) - 1)
                                self._increment_error()
                                self._add_problem_item(network_name, "ipam.config.subnet", "ERROR", message)
                                all_networks_found = False
                            else:
                                subnet = subnet_config['subnet']
                                message = f"Subnet: {subnet}"
                                self._print_tree_status_item(message, "OK", is_last_subnet)
                                self._increment_success()
                
                # Check driver configuration
                if 'driver' in network_config:
                    driver = network_config['driver']
                    if driver not in ['bridge', 'overlay', 'host', 'macvlan', 'none']:
                        message = f"Unusual network driver: {driver}"
                        self._print_tree_status_item(message, "WARN", True)
                        self._increment_warning()
                        self._add_problem_item(network_name, "driver", "WARN", message)
                    else:
                        message = f"Network driver: {driver}"
                        self._print_tree_status_item(message, "OK", True)
                        self._increment_success()
                else:
                    message = "No driver specified, using default 'bridge'"
                    self._print_tree_status_item(message, "INFO", True)
                    self._increment_success()
                
                self.depth -= 1
            else:
                message = f"Required network '{network_name}' is not defined"
                self._print_tree_status_item(message, "ERROR", is_last)
                self._increment_error()
                self._add_problem_item("docker-compose.yml", f"networks.{network_name}", "ERROR", message)
                all_networks_found = False
        
        self.depth -= 1
        return all_networks_found
    
    def check_services_network_config(self, compose_data: Dict) -> bool:
        """Check network configuration for each service.
        
        Args:
            compose_data: Docker compose configuration dictionary
            
        Returns:
            True if all services have proper network config, False otherwise
        """
        self._print_tree_item("Services Network Configuration", SERVICE_SYMBOL)
        self.depth += 1
        
        if 'services' not in compose_data:
            message = "No services section in docker-compose.yml"
            self._print_tree_status_item(message, "ERROR", True)
            self._increment_error()
            self._add_problem_item("docker-compose.yml", "services", "ERROR", message)
            self.depth -= 1
            return False
        
        services = compose_data['services']
        all_configs_valid = True
        service_ips = {}  # For checking IP address conflicts
        
        # Pre-populate service categories
        for category, service_list in SERVICES_BY_CATEGORY.items():
            for service_name in service_list:
                self.service_categories[service_name] = category
        
        # Check each service
        for service_index, (service_name, service_config) in enumerate(services.items()):
            is_last_service = service_index == len(services) - 1
            
            # Get category
            category = None
            for cat, services_list in SERVICES_BY_CATEGORY.items():
                if service_name in services_list:
                    category = cat
                    break
            
            self._print_tree_item(f"Service: {service_name} ({category if category else 'unknown'})", SERVICE_SYMBOL, is_last_service)
            self.depth += 1
            
            # Check if service has network config
            if 'networks' not in service_config:
                message = "No networks configuration"
                self._print_tree_status_item(message, "ERROR", True)
                self._increment_error()
                self._add_problem_item(service_name, "networks", "ERROR", message)
                all_configs_valid = False
            else:
                networks = service_config['networks']
                
                # Get list of network names
                network_names = list(networks.keys())
                network_count = len(network_names)
                
                # Check if service has at least one network
                if network_count == 0:
                    message = "No networks assigned to service"
                    self._print_tree_status_item(message, "ERROR", True)
                    self._increment_error()
                    self._add_problem_item(service_name, "networks", "ERROR", message)
                    all_configs_valid = False
                else:
                    message = f"Networks assigned: {', '.join(network_names)}"
                    self._print_tree_status_item(message, "OK")
                    self._increment_success()
                    
                    # Check each network for IP address
                    for net_idx, (network_name, network_config) in enumerate(networks.items()):
                        is_last_network = net_idx == len(networks) - 1
                        
                        # Skip if network config is None or not a dict
                        if not network_config or not isinstance(network_config, dict):
                            continue
                        
                        # Check for static IP address
                        if 'ipv4_address' in network_config:
                            ip_address = network_config['ipv4_address']
                            service_ips[service_name] = ip_address
                            self.service_networks[service_name] = ip_address
                            self.network_addresses.add(ip_address)
                            
                            # Check IP address format
                            if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_address):
                                message = f"Invalid IP address format: {ip_address}"
                                self._print_tree_status_item(message, "ERROR", is_last_network)
                                self._increment_error()
                                self._add_problem_item(service_name, f"networks.{network_name}.ipv4_address", "ERROR", message)
                                all_configs_valid = False
                            else:
                                # Check IP address matches pattern for service category
                                valid_pattern = False
                                if category:
                                    # Check specific service pattern
                                    if service_name in IP_ALLOCATION_PATTERNS:
                                        pattern = IP_ALLOCATION_PATTERNS[service_name]
                                        if re.match(pattern, ip_address):
                                            valid_pattern = True
                                    
                                    # Check category pattern if specific pattern didn't match
                                    if not valid_pattern:
                                        for pattern_key, pattern in IP_ALLOCATION_PATTERNS.items():
                                            if pattern_key.endswith("-.*-module") and service_name.endswith("-module"):
                                                if re.match(pattern, ip_address):
                                                    valid_pattern = True
                                                    break
                                
                                if valid_pattern:
                                    message = f"IP address: {ip_address} (matches pattern)"
                                    self._print_tree_status_item(message, "OK", is_last_network)
                                    self._increment_success()
                                else:
                                    message = f"IP address: {ip_address} (does not match expected pattern)"
                                    self._print_tree_status_item(message, "WARN", is_last_network)
                                    self._increment_warning()
                                    self._add_problem_item(service_name, f"networks.{network_name}.ipv4_address", "WARN", message)
                        else:
                            message = f"No static IP address for network {network_name}"
                            self._print_tree_status_item(message, "WARN", is_last_network)
                            self._increment_warning()
                            self._add_problem_item(service_name, f"networks.{network_name}.ipv4_address", "WARN", message)
            
            self.depth -= 1
        
        self.depth -= 1
        return all_configs_valid
    
    def check_service_dependencies(self, compose_data: Dict) -> bool:
        """Check if services have proper dependencies defined.
        
        Args:
            compose_data: Docker compose configuration dictionary
            
        Returns:
            True if all primary services have dependencies defined, False otherwise
        """
        self._print_tree_item("Service Dependencies", GEAR_SYMBOL)
        self.depth += 1
        
        if 'services' not in compose_data:
            message = "No services section in docker-compose.yml"
            self._print_tree_status_item(message, "ERROR", True)
            self._increment_error()
            self._add_problem_item("docker-compose.yml", "services", "ERROR", message)
            self.depth -= 1
            return False
        
        services = compose_data['services']
        all_dependencies_valid = True
        primary_services = [
            "infrastructure-service",
            "management-service",
            "security-service"
        ]
        
        for i, service_name in enumerate(primary_services):
            is_last = i == len(primary_services) - 1
            
            if service_name not in services:
                message = f"Primary service {service_name} not found in docker-compose.yml"
                self._print_tree_status_item(message, "ERROR", is_last)
                self._increment_error()
                self._add_problem_item("docker-compose.yml", f"services.{service_name}", "ERROR", message)
                all_dependencies_valid = False
                continue
            
            service_config = services[service_name]
            self._print_tree_item(f"Primary Service: {service_name}", SERVICE_SYMBOL)
            self.depth += 1
            
            if 'depends_on' not in service_config:
                message = "No dependencies defined"
                self._print_tree_status_item(message, "ERROR", True)
                self._increment_error()
                self._add_problem_item(service_name, "depends_on", "ERROR", message)
                all_dependencies_valid = False
            else:
                dependencies = service_config['depends_on']
                
                if not dependencies:
                    message = "Empty dependencies list"
                    self._print_tree_status_item(message, "ERROR", True)
                    self._increment_error()
                    self._add_problem_item(service_name, "depends_on", "ERROR", message)
                    all_dependencies_valid = False
                else:
                    # Count dependencies for specific category
                    category = None
                    for cat, services_list in SERVICES_BY_CATEGORY.items():
                        if service_name in services_list:
                            category = cat
                            break
                    
                    if category:
                        expected_modules = [s for s in SERVICES_BY_CATEGORY[category] if s != service_name]
                        
                        # Check if all expected modules are in dependencies
                        missing_deps = [module for module in expected_modules if module not in dependencies]
                        
                        if missing_deps:
                            message = f"Missing expected dependencies: {', '.join(missing_deps)}"
                            self._print_tree_status_item(message, "WARN")
                            self._increment_warning()
                            self._add_problem_item(service_name, "depends_on", "WARN", message)
                        
                        message = f"Dependencies defined: {len(dependencies)}"
                        self._print_tree_status_item(message, "OK", True)
                        self._increment_success()
            
            self.depth -= 1
        
        self.depth -= 1
        return all_dependencies_valid
    
    def check_ip_address_conflicts(self, compose_data: Dict) -> bool:
        """Check for IP address conflicts among services.
        
        Args:
            compose_data: Docker compose configuration dictionary
            
        Returns:
            True if no IP address conflicts found, False otherwise
        """
        self._print_tree_item("IP Address Conflicts", IP_SYMBOL)
        self.depth += 1
        
        if not self.service_networks:
            message = "No service network data available"
            self._print_tree_status_item(message, "ERROR", True)
            self._increment_error()
            self._add_problem_item("docker-compose.yml", "ip_conflicts", "ERROR", message)
            self.depth -= 1
            return False
        
        # Find services with the same IP address
        ip_services_map = {}
        for service_name, ip_address in self.service_networks.items():
            if ip_address in ip_services_map:
                ip_services_map[ip_address].append(service_name)
            else:
                ip_services_map[ip_address] = [service_name]
        
        # Find conflicts
        conflicts = {ip: services for ip, services in ip_services_map.items() if len(services) > 1}
        
        if conflicts:
            message = f"Found {len(conflicts)} IP address conflicts"
            self._print_tree_status_item(message, "ERROR")
            self._increment_error()
            self._add_problem_item("docker-compose.yml", "ip_conflicts", "ERROR", message)
            
            for i, (ip, services) in enumerate(conflicts.items()):
                is_last = i == len(conflicts) - 1
                conflict_msg = f"IP {ip} used by multiple services: {', '.join(services)}"
                self._print_tree_status_item(conflict_msg, "ERROR", is_last)
                self._increment_error()
                self._add_problem_item("docker-compose.yml", f"ip_conflict_{ip}", "ERROR", conflict_msg)
            
            self.depth -= 1
            return False
        else:
            message = "No IP address conflicts found"
            self._print_tree_status_item(message, "OK", True)
            self._increment_success()
            self.depth -= 1
            return True
    
    def check_ip_allocation_scheme(self, compose_data: Dict) -> bool:
        """Check if IP addresses follow the expected allocation scheme.
        
        Args:
            compose_data: Docker compose configuration dictionary
            
        Returns:
            True if IP allocation follows the expected scheme, False otherwise
        """
        self._print_tree_item("IP Allocation Scheme", GEAR_SYMBOL)
        self.depth += 1
        
        if not self.service_networks:
            message = "No service network data available"
            self._print_tree_status_item(message, "ERROR", True)
            self._increment_error()
            self._add_problem_item("docker-compose.yml", "ip_allocation", "ERROR", message)
            self.depth -= 1
            return False
        
        all_allocations_valid = True
        
        # Count services by category subnet
        infraservices_internal_subnet = []
        management_internal_subnet = []
        security_internal_subnet = []
        infraservices_external_subnet = []
        management_external_subnet = []
        security_external_subnet = []
        other_subnet = []
        
        for service_name, ip_address in self.service_networks.items():
            if re.match(r"^172\.20\.1\.\d+$", ip_address):
                infraservices_internal_subnet.append(service_name)
            elif re.match(r"^172\.20\.2\.\d+$", ip_address):
                management_internal_subnet.append(service_name)
            elif re.match(r"^172\.20\.3\.\d+$", ip_address):
                security_internal_subnet.append(service_name)
            elif re.match(r"^172\.21\.1\.\d+$", ip_address):
                infraservices_external_subnet.append(service_name)
            elif re.match(r"^172\.21\.2\.\d+$", ip_address):
                management_external_subnet.append(service_name)
            elif re.match(r"^172\.21\.3\.\d+$", ip_address):
                security_external_subnet.append(service_name)
            else:
                other_subnet.append(service_name)
        
        # Internal network services
        message = f"Infrastructure internal subnet (172.20.1.0/24): {len(infraservices_internal_subnet)} services"
        self._print_tree_status_item(message, "OK")
        self._increment_success()
        
        message = f"Management internal subnet (172.20.2.0/24): {len(management_internal_subnet)} services"
        self._print_tree_status_item(message, "OK")
        self._increment_success()
        
        message = f"Security internal subnet (172.20.3.0/24): {len(security_internal_subnet)} services"
        self._print_tree_status_item(message, "OK")
        self._increment_success()
        
        # External network services
        message = f"Infrastructure external subnet (172.21.1.0/24): {len(infraservices_external_subnet)} services"
        self._print_tree_status_item(message, "OK")
        self._increment_success()
        
        message = f"Management external subnet (172.21.2.0/24): {len(management_external_subnet)} services"
        self._print_tree_status_item(message, "OK")
        self._increment_success()
        
        message = f"Security external subnet (172.21.3.0/24): {len(security_external_subnet)} services"
        self._print_tree_status_item(message, "OK")
        self._increment_success()
        
        # Services in unexpected subnets
        if other_subnet:
            message = f"Services in unexpected subnets: {len(other_subnet)}"
            self._print_tree_status_item(message, "WARN", True)
            self._increment_warning()
            self._add_problem_item("docker-compose.yml", "ip_allocation", "WARN", 
                                   f"Services in unexpected subnets: {', '.join(other_subnet)}")
            all_allocations_valid = False
        else:
            message = "All services follow IP allocation scheme"
            self._print_tree_status_item(message, "OK", True)
            self._increment_success()
        
        self.depth -= 1
        return all_allocations_valid
        
    def run_all_checks(self):
        """Run all network configuration checks."""
        # Load compose file
        compose_data = self.load_docker_compose()
        
        # Run checks
        version_ok = self.check_version(compose_data)
        networks_ok = self.check_networks_defined(compose_data)
        services_ok = self.check_services_network_config(compose_data)
        dependencies_ok = self.check_service_dependencies(compose_data)
        conflicts_ok = self.check_ip_address_conflicts(compose_data)
        allocation_ok = self.check_ip_allocation_scheme(compose_data)
        
        # Return overall status
        all_checks_ok = (version_ok and networks_ok and services_ok and 
                          dependencies_ok and conflicts_ok and allocation_ok)
        return all_checks_ok

    def generate_summary(self) -> None:
        """Generate and print a summary of check results."""
        clear_line = "\r" + " " * 100 + "\r" if not self.show_progress else ""
        print(f"{clear_line}{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.BLUE}Docker Network Configuration Check Report (version {self.version}){Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.ENDC}")
        
        # Print counts
        print(f"{Colors.BOLD}Total checks:{Colors.ENDC} {self.success_count + self.warning_count + self.error_count}")
        print(f"{Colors.BOLD}Successful:{Colors.ENDC} {Colors.GREEN}{self.success_count}{Colors.ENDC}")
        
        if self.warning_count > 0:
            print(f"{Colors.BOLD}Warnings:{Colors.ENDC} {Colors.YELLOW}{self.warning_count}{Colors.ENDC}")
        else:
            print(f"{Colors.BOLD}Warnings:{Colors.ENDC} {self.warning_count}")
            
        if self.error_count > 0:
            print(f"{Colors.BOLD}Errors:{Colors.ENDC} {Colors.RED}{self.error_count}{Colors.ENDC}")
        else:
            print(f"{Colors.BOLD}Errors:{Colors.ENDC} {self.error_count}")
        
        print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.ENDC}")
        
        # Report problems if any
        if self.problems:
            print(f"{Colors.BOLD}Problem Report:{Colors.ENDC}")
            
            # Group by service for better organization
            service_problems = {}
            for problem in self.problems:
                service = problem["service"]
                if service not in service_problems:
                    service_problems[service] = []
                service_problems[service].append(problem)
            
            for service, problems in sorted(service_problems.items()):
                print(f"\n{Colors.BOLD}{Colors.CYAN}{service}{Colors.ENDC}")
                
                # Group by section within service
                section_problems = {}
                for problem in problems:
                    section = problem["section"]
                    if section not in section_problems:
                        section_problems[section] = []
                    section_problems[section].append(problem)
                
                for section, probs in sorted(section_problems.items()):
                    print(f"  {Colors.BOLD}{section}{Colors.ENDC}")
                    for prob in probs:
                        level = prob["level"]
                        if level == "ERROR":
                            color = Colors.RED
                        elif level == "WARN":
                            color = Colors.YELLOW
                        else:
                            color = Colors.ENDC
                            
                        print(f"    {color}[{level}]{Colors.ENDC} {prob['message']}")
        
        # Print final status
        print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.ENDC}")
        if self.error_count > 0:
            print(f"{Colors.BOLD}{Colors.RED}Check completed with errors.{Colors.ENDC}")
        elif self.warning_count > 0:
            print(f"{Colors.BOLD}{Colors.YELLOW}Check completed with warnings.{Colors.ENDC}")
        else:
            print(f"{Colors.BOLD}{Colors.GREEN}All checks passed successfully.{Colors.ENDC}")
            
        print(f"{Colors.BOLD}Check log:{Colors.ENDC} {self.log_file}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.ENDC}")

    def log_environment_info(self) -> None:
        """Log information about the runtime environment."""
        self.logger.info("=" * 80)
        self.logger.info(f"Docker Network Configuration Check Script (version {self.version})")
        self.logger.info("=" * 80)
        self.logger.info(f"Script name: {os.path.basename(__file__)}")
        self.logger.info(f"Python version: {platform.python_version()}")
        self.logger.info(f"Platform: {platform.platform()}")
        self.logger.info(f"Start time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Docker-compose file: {self.docker_compose_path}")
        self.logger.info(f"Log file: {self.log_file}")
        self.logger.info("=" * 80)
        self.logger.info("")

    def log_results(self) -> None:
        """Log summary statistics and problems to the log file."""
        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info("FINAL CHECK RESULTS")
        self.logger.info("=" * 80)
        self.logger.info(f"Total checks: {self.success_count + self.warning_count + self.error_count}")
        self.logger.info(f"Successful: {self.success_count}")
        self.logger.info(f"Warnings: {self.warning_count}")
        self.logger.info(f"Errors: {self.error_count}")
        self.logger.info("=" * 80)
        
        # Log all problems
        if self.problems:
            self.logger.info("PROBLEM REPORT:")
            
            # Group by service for better organization
            service_problems = {}
            for problem in self.problems:
                service = problem["service"]
                if service not in service_problems:
                    service_problems[service] = []
                service_problems[service].append(problem)
            
            for service, problems in sorted(service_problems.items()):
                self.logger.info(f"")
                self.logger.info(f"Service: {service}")
                
                # Group by section within service
                section_problems = {}
                for problem in problems:
                    section = problem["section"]
                    if section not in section_problems:
                        section_problems[section] = []
                    section_problems[section].append(problem)
                
                for section, probs in sorted(section_problems.items()):
                    self.logger.info(f"  Section: {section}")
                    for prob in probs:
                        self.logger.info(f"    [{prob['level']}] {prob['message']}")
        
        # Log final status
        self.logger.info("=" * 80)
        if self.error_count > 0:
            self.logger.info("FINAL STATUS: ERROR - Check completed with errors.")
        elif self.warning_count > 0:
            self.logger.info("FINAL STATUS: WARNING - Check completed with warnings.")
        else:
            self.logger.info("FINAL STATUS: SUCCESS - All checks passed successfully.")
        self.logger.info("=" * 80)

    def check_network_config(self) -> bool:
        """Run all network configuration checks and generate reports."""
        try:
            # Initialize logger and output environment information
            self.log_environment_info()
            
            # Load docker-compose data
            if not self.load_docker_compose():
                return False
            
            # Check successful loading
            if not self.docker_compose_data:
                self.log_error("global", "parser", "Failed to load docker-compose.yml file")
                self.log_results()
                self.generate_summary()
                return False
            
            # Run all checks
            self.run_all_checks()
            
            # Generate reports
            self.log_results()
            self.generate_summary()
            
            # Return True if no errors
            return self.error_count == 0
            
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")
            self.logger.exception("Full exception information:")
            print(f"{Colors.RED}Unexpected error: {str(e)}{Colors.ENDC}")
            return False

def setup_logging(log_dir: str, enable_progress=True) -> Tuple[logging.Logger, str]:
    """Set up logging for the script.
    
    Args:
        log_dir: Directory to store log files
        enable_progress: Whether to show progress in the console
    
    Returns:
        Tuple of (logger, log_file_path)
    """
    # Ensure log directory exists
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create timestamp for log file
    timestamp = datetime.now().strftime("%Y.%m.%d_%H-%M")
    log_file = os.path.join(log_dir, f"{timestamp}_check_5_network.log")
    
    # Create logger
    logger = logging.getLogger("network_checker")
    logger.setLevel(logging.DEBUG)
    
    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    # Create console handler with higher level if progress is disabled
    if not enable_progress:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # Create formatter
    formatter = logging.Formatter('%(message)s')
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(file_handler)
    
    return logger, log_file

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Docker Network Configuration Check in docker-compose.yml file (version 0.2)"
    )
    parser.add_argument(
        "--docker-compose-file", 
        "-f", 
        default="docker/docker-compose.yml",
        help="Path to docker-compose.yml file (default: docker/docker-compose.yml)"
    )
    parser.add_argument(
        "--no-progress", 
        action="store_true",
        help="Disable progress indicators (for CI/CD and file output)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    args = parser.parse_args()

    # Create and run network checker
    checker = NetworkChecker(
        workspace_root=DEFAULT_WORKSPACE_ROOT,
        docker_compose_path=args.docker_compose_file,
        log_file="logs/check_network.log",
        show_progress=not args.no_progress,
        debug_mode=DEFAULT_DEBUG_MODE,
        no_color=DEFAULT_NO_COLOR
    )
    
    success = checker.check_network_config()
    return 0 if success else 1

def main():
    """Main function to parse arguments and run network checker."""
    parser = argparse.ArgumentParser(
        description="Docker Network Configuration Check in docker-compose.yml file (version 0.2)"
    )
    parser.add_argument(
        "--docker-compose-file", 
        "-f", 
        default="docker/docker-compose.yml",
        help="Path to docker-compose.yml file (default: docker/docker-compose.yml)"
    )
    parser.add_argument(
        "--no-progress", 
        action="store_true",
        help="Disable progress indicators (for CI/CD and file output)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    args = parser.parse_args()

    # Initialize log file
    log_filename, _ = init_log_file(DEFAULT_WORKSPACE_ROOT)

    # Create and run network checker
    checker = NetworkChecker(
        workspace_root=DEFAULT_WORKSPACE_ROOT,
        docker_compose_path=args.docker_compose_file,
        log_file=log_filename,
        show_progress=not args.no_progress,
        debug_mode=DEFAULT_DEBUG_MODE,
        no_color=DEFAULT_NO_COLOR
    )
    
    success = checker.check_network_config()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 