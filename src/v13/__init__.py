"""
VÉLØ V13 - Living Intelligence System

Constitutional Layer:
- Episodic memory with epistemic time separation (decisionTime vs createdAt)
- Read-only critics (Leakage, Cognitive Bias, Feature Extractor, Decision)
- Doctrine guards (no auto-apply, no silent mutation, no learning without audit)

Author: VÉLØ Team
Date: 2026-01-19
Status: LOCKED
Checkpoint: V13_COGNITIVE_LOOP_COMPLETE
"""

from . import critics
from . import episodes
from .doctrine import (
    DOCTRINE_CRITIC_AUTHORITY,
    DOCTRINE_EPISTEMIC_TIME,
    DOCTRINE_FEATURE_FIREWALL,
    DOCTRINE_NO_SILENT_MODIFICATION,
)

__version__ = "13.0.0"

__all__ = [
    "critics",
    "episodes",
    "DOCTRINE_CRITIC_AUTHORITY",
    "DOCTRINE_EPISTEMIC_TIME",
    "DOCTRINE_FEATURE_FIREWALL",
    "DOCTRINE_NO_SILENT_MODIFICATION",
]
