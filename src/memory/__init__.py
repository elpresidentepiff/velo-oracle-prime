"""
VÉLØ PRIME — Persistent Memory Package
========================================
Cross-session intelligence infrastructure.

Modules:
  schema          — SQLite database schema and initialization
  memory_engine   — Core VeloMemoryEngine class
  github_sync     — Git-based persistence and sync
  rpd_validator   — RPD-C tag validation engine
  integrate       — CLI integration pipeline
"""

from .schema import init_database, get_schema_version, SCHEMA_VERSION
from .memory_engine import VeloMemoryEngine
from .github_sync import GitHubSync
from .rpd_validator import RPDValidator

__all__ = [
    "init_database",
    "get_schema_version",
    "SCHEMA_VERSION",
    "VeloMemoryEngine",
    "GitHubSync",
    "RPDValidator",
]
