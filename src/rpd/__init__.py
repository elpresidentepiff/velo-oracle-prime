"""
VÉLØ RPD-C v2 — Runner Profile Designation (Chaos)

Exports the RPDv2Engine and supporting types.

Usage:
    from src.rpd.rpd_v2 import RPDv2Engine, RPDTag, TagValidity
    engine = RPDv2Engine()
    suggestion = engine.suggest_tag("Alondra", ["long_campaign", "declining_positions"])
"""

from .rpd_v2 import (
    RPDv2Engine,
    RPDTag,
    TagValidity,
    TagValidation,
    TagSuggestion,
    TagAuditResult,
    EVIDENCE_DEFINITIONS,
)

__all__ = [
    "RPDv2Engine",
    "RPDTag",
    "TagValidity",
    "TagValidation",
    "TagSuggestion",
    "TagAuditResult",
    "EVIDENCE_DEFINITIONS",
]
