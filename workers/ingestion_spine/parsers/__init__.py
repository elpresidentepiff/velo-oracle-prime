"""
VÉLØ Phase 1: Parsers Package

Exports all parser classes from the ingestion_spine package.
The three main parser classes (RacecardsParser, RunnersParser, FormParser)
live in the sibling parsers.py module at the ingestion_spine package level.
We import them here so that `from .parsers import RacecardsParser` works
when called from ingestion_spine.main.
"""

# Import the three parser classes from the sibling parsers.py module.
# When running as the ingestion_spine package (PYTHONPATH=/app, WORKDIR=/app/ingestion_spine),
# this resolves to ingestion_spine.parsers_base which is the renamed flat file.
# We use a direct import from the parent package to avoid circular imports.
import importlib
import importlib.util
import sys
import os

# Resolve the sibling parsers.py by loading it as a module directly
_parsers_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "parsers.py")
_spec = importlib.util.spec_from_file_location("_ingestion_parsers_base", _parsers_path)
_mod = importlib.util.module_from_spec(_spec)

# We need the parent package context for relative imports in parsers.py
# parsers.py does: from .models import RaceData, RunnerData, FormLineData
# So we need to set the package to ingestion_spine
import ingestion_spine.models  # ensure parent package is loaded
_mod.__package__ = "ingestion_spine"
_spec.loader.exec_module(_mod)

RacecardsParser = _mod.RacecardsParser
RunnersParser = _mod.RunnersParser
FormParser = _mod.FormParser

from .quality import calculate_race_quality, calculate_runner_confidence

__all__ = [
    "RacecardsParser",
    "RunnersParser",
    "FormParser",
    "calculate_runner_confidence",
    "calculate_race_quality",
]
