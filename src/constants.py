"""
VÉLØ Canonical Contract
========================
Single source of truth for all enum values used across the system.

Nothing is allowed to write a value that is not defined here.
No synonyms. No dialects. No soft defaults.
"""

# ── Outcome ───────────────────────────────────────────────────────────────────
# Written to: sigma_audits.outcome, betting_ledger.result
# Canonical Railway values — any other string is contamination.

OUTCOME_WIN      = "WIN"
OUTCOME_PLACED   = "PLACED"
OUTCOME_MISS     = "MISS"
OUTCOME_NO_RESULT = "NO_RESULT"

VALID_OUTCOMES = {OUTCOME_WIN, OUTCOME_PLACED, OUTCOME_MISS, OUTCOME_NO_RESULT}

# DEAD — do not use. These are the legacy labels that were corrupting analytics.
# OUTCOME_HIT   = "HIT"   # KILLED
# OUTCOME_FRAME = "FRAME" # KILLED


# ── Tier ─────────────────────────────────────────────────────────────────────
# Written to: velo_verdicts.decision_tier, sigma_audits.decision_tier

TIER_A = "A"
TIER_B = "B"
TIER_C = "C"
TIER_D = "D"
TIER_X = "X"   # unclassified / excluded

VALID_TIERS = {TIER_A, TIER_B, TIER_C, TIER_D, TIER_X}


# ── Run status ────────────────────────────────────────────────────────────────
# Written to: pipeline_runs.status
# No more "partial" hiding write errors.

RUN_STATUS_PASS     = "PASS"
RUN_STATUS_DEGRADED = "DEGRADED"
RUN_STATUS_FAIL     = "FAIL"

VALID_RUN_STATUSES = {RUN_STATUS_PASS, RUN_STATUS_DEGRADED, RUN_STATUS_FAIL}


# ── Race ID format ────────────────────────────────────────────────────────────
# Canonical format: rac_XXXXXXXX (Racing API native format)
# Verified: 100% match rate between velo_verdicts and Racing API results.
RACE_ID_PREFIX = "rac_"


def validate_outcome(value: str) -> str:
    """Raise ValueError if outcome is not canonical. Return the value if valid."""
    if value not in VALID_OUTCOMES:
        raise ValueError(
            f"Non-canonical outcome '{value}'. Must be one of {VALID_OUTCOMES}. "
            f"Possible legacy contamination: HIT->WIN, FRAME->PLACED."
        )
    return value


def validate_tier(value: str) -> str:
    """Raise ValueError if tier is not canonical."""
    if value not in VALID_TIERS:
        raise ValueError(
            f"Non-canonical tier '{value}'. Must be one of {VALID_TIERS}."
        )
    return value


def validate_run_status(value: str) -> str:
    """Raise ValueError if run_status is not canonical."""
    if value not in VALID_RUN_STATUSES:
        raise ValueError(
            f"Non-canonical run_status '{value}'. Must be one of {VALID_RUN_STATUSES}."
        )
    return value
