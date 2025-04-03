#!/usr/bin/env python
# main.py - Entry point for Speculorg.Terminal.Security.Service

import os
import sys

if __name__ == "__main__":
    # Set the default Django settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'security_service.settings')
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable?"
        ) from exc
    
    execute_from_command_line(sys.argv) 