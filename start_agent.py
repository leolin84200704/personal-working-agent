#!/usr/bin/env python
"""
Start script for LIS Code Agent service.

Usage:
    python start_agent.py
"""
import sys
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_settings

settings = get_settings()

print(f"""
╔═══════════════════════════════════════════════════════════╗
║           LIS Code Agent v2.0 - Backend Service           ║
╚═══════════════════════════════════════════════════════════╝

Configuration:
  - API: http://{settings.api_host}:{settings.api_port}
  - Docs: http://{settings.api_host}:{settings.api_port}/docs
  - Storage: {settings.storage_path}
  - Repos: {settings.repos_base_path}

Starting...
""")

# Start the service
subprocess.run([
    sys.executable, "-m", "uvicorn",
    "src.api.main:app",
    "--host", settings.api_host,
    "--port", str(settings.api_port),
    "--reload" if settings.api_reload else "",
])
