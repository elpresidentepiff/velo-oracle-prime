"""
VÉLØ Phase 1: Parsers Package

_parsers_base.py contains RacecardsParser, RunnersParser, FormParser.
Import it directly as ingestion_spine._parsers_base — no importlib hacks.

Container layout (PYTHONPATH=/app):
  /app/ingestion_spine/_parsers_base.py  →  ingestion_spine._parsers_base
  /app/ingestion_spine/parsers/          →  ingestion_spine.parsers  (this package)
"""

from .._parsers_base import FormParser, RacecardsParser, RunnersParser
from .quality import calculate_race_quality, calculate_runner_confidence

__all__ = [
    "RacecardsParser",
    "RunnersParser",
    "FormParser",
    "calculate_runner_confidence",
    "calculate_race_quality",
]
