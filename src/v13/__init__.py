"""
VÉLØ V13 — Constitutional Doctrine Layer

Exposes the six immutable laws and the doctrine compliance validator.
Critics, episodes, and governance are NOT imported here — they require
separate adaptation to the Supabase/velo_verdicts environment.

Import only doctrine here. Wire critics and governance separately.
"""

from .doctrine import (
    DOCTRINE_EPISTEMIC_TIME,
    DOCTRINE_CRITIC_AUTHORITY,
    DOCTRINE_FEATURE_FIREWALL,
    DOCTRINE_NO_SILENT_MODIFICATION,
    DOCTRINE_REPLAY_INTEGRITY,
    DOCTRINE_TRUTH_BEFORE_OPTIMIZATION,
    DOCTRINE_REGISTRY,
    get_doctrine,
    validate_doctrine_compliance,
    enforce_read_only,
)

__version__ = "13.0.0"

__all__ = [
    "DOCTRINE_EPISTEMIC_TIME",
    "DOCTRINE_CRITIC_AUTHORITY",
    "DOCTRINE_FEATURE_FIREWALL",
    "DOCTRINE_NO_SILENT_MODIFICATION",
    "DOCTRINE_REPLAY_INTEGRITY",
    "DOCTRINE_TRUTH_BEFORE_OPTIMIZATION",
    "DOCTRINE_REGISTRY",
    "get_doctrine",
    "validate_doctrine_compliance",
    "enforce_read_only",
]
