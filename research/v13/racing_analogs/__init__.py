"""
VÉLØ Racing Analogs — Sidecar Module
=====================================
Advisory analog-similarity layer for the VÉLØ racing engine.

Design principles:
- Read-only sidecar. Does not modify VÉLØ core.
- Shadow mode only until Stage 4 promotion.
- Uses locked 13-feature fingerprint spec (feature_version=fingerprint_v1).
- Never widens features beyond the locked set.

Layers:
  schema.py         — canonical state dataclasses
  canonical_mapper.py — maps source rows to canonical shape
  fingerprint_features.py — builds the 13-feature fingerprint input
  vector_encoder.py  — normalizes + encodes to fixed-length vector
  analog_index.py   — nearest-neighbor retrieval
  analog_summary.py  — aggregates analogs into advisory output
  shadow_runner.py   — batch runner + Supabase persistence

Author: hermes-prime
Started: 2026-04-08
Status: PHASE_A — skeleton only
"""

__version__ = "0.1.0"
__stage__ = "PHASE_A_SKELETON"  # bump to PHASE_B, PHASE_C, PHASE_D as promoted

from .schema import (
    CanonicalRaceState,
    FingerprintVector,
    AnalogMatch,
    AnalogSummary,
    AdvisoryOutput,
)

__all__ = [
    "CanonicalRaceState",
    "FingerprintVector",
    "AnalogMatch",
    "AnalogSummary",
    "AdvisoryOutput",
]
