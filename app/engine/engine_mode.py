"""
VÉLØ Engine Mode Configuration
================================
Controls which signal engines are active and how the decision policy operates.

Modes:
  PROD          — Full pipeline. All engines required. Current live behaviour.
  SQPE_DIRECT   — SQPE only. No stub dependencies. Raw truth baseline.
  SQPE_MARKET   — SQPE + real market overlay. Stubs still bypassed.

Set via environment variable:  ENGINE_MODE=sqpe_direct

The mode is read once at startup and is immutable for the lifetime of the process.
"""

import logging
import os
from enum import Enum

logger = logging.getLogger(__name__)


class EngineMode(str, Enum):
    PROD = "prod"
    SQPE_DIRECT = "sqpe_direct"
    SQPE_MARKET = "sqpe_market"


def get_engine_mode() -> EngineMode:
    raw = os.getenv("ENGINE_MODE", "prod").lower().strip()
    try:
        mode = EngineMode(raw)
    except ValueError:
        logger.warning(f"[engine_mode] Unknown ENGINE_MODE='{raw}', defaulting to PROD")
        mode = EngineMode.PROD
    logger.info(f"[engine_mode] Active mode: {mode.value.upper()}")
    return mode


# Singleton — resolved once at import time
ACTIVE_MODE: EngineMode = get_engine_mode()


def is_prod() -> bool:
    return ACTIVE_MODE == EngineMode.PROD


def is_sqpe_direct() -> bool:
    return ACTIVE_MODE == EngineMode.SQPE_DIRECT


def is_sqpe_market() -> bool:
    return ACTIVE_MODE == EngineMode.SQPE_MARKET


def stubs_allowed() -> bool:
    """Return True only in PROD. Experimental modes must not rely on stubs."""
    return ACTIVE_MODE == EngineMode.PROD
