"""
VÉLØ Source Truth Enforcer
===========================
Implements Layer 1 (Input Layer) of VELO_AGENT_HARNESS_DOCTRINE_V1.

Translates racecard_loader source labels ('cache', 'rp_merged', and blocked
legacy API aliases)
into canonical harness source truth labels, enforces blocking rules, and
emits structured warnings.

Hard constraints:
  - READ_ONLY: no file writes, no DB writes, no scoring changes
  - No live-state mutation of any kind
  - SOURCE_UNKNOWN_BLOCK always raises SourceTruthBlockError

Source truth labels (canonical):
  RP_MERGED_CLEAN     — full RP PDF set, all features present
  RP_MERGED_DEGRADED  — partial RP PDFs, feature degradation active
  LOCAL_JSON_FALLBACK — verified local standard cache
  RACING_API_BLOCKED  — legacy Racing API path; execution must be blocked
  SOURCE_UNKNOWN_BLOCK — unknown origin; execution must be blocked
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Canonical labels ──────────────────────────────────────────────────────────

class SourceLabel:
    RP_MERGED_CLEAN = "RP_MERGED_CLEAN"
    RP_MERGED_DEGRADED = "RP_MERGED_DEGRADED"
    LOCAL_JSON_FALLBACK = "LOCAL_JSON_FALLBACK"
    RACING_API_BLOCKED = "RACING_API_BLOCKED"
    SOURCE_UNKNOWN_BLOCK = "SOURCE_UNKNOWN_BLOCK"

    ALL = frozenset({
        RP_MERGED_CLEAN,
        RP_MERGED_DEGRADED,
        LOCAL_JSON_FALLBACK,
        RACING_API_BLOCKED,
        SOURCE_UNKNOWN_BLOCK,
    })

    # Labels that allow execution to proceed
    ALLOWED = frozenset({RP_MERGED_CLEAN, RP_MERGED_DEGRADED, LOCAL_JSON_FALLBACK})

    # Labels that must block execution
    BLOCKED = frozenset({SOURCE_UNKNOWN_BLOCK, RACING_API_BLOCKED})

    # Labels that require a degradation warning
    DEGRADED = frozenset({RP_MERGED_DEGRADED})


# ── Exceptions ────────────────────────────────────────────────────────────────

class SourceTruthBlockError(RuntimeError):
    """Raised when source truth is SOURCE_UNKNOWN_BLOCK — execution must stop."""


class SourceTruthDegradedWarning(UserWarning):
    """Issued when source truth is RP_MERGED_DEGRADED — execution continues with warnings."""


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class SourceTruthResult:
    """The outcome of a source truth enforcement check."""
    canonical_label: str
    loader_label: str
    execution_allowed: bool
    warnings: list[str] = field(default_factory=list)
    degraded: bool = False
    blocked: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "canonical_label": self.canonical_label,
            "loader_label": self.loader_label,
            "execution_allowed": self.execution_allowed,
            "degraded": self.degraded,
            "blocked": self.blocked,
            "warnings": self.warnings,
        }


# ── Loader label → canonical label mapping ───────────────────────────────────

_LOADER_TO_CANONICAL: dict[str, str] = {
    "cache": SourceLabel.LOCAL_JSON_FALLBACK,
    "rp_merged": SourceLabel.RP_MERGED_CLEAN,
    "api": SourceLabel.RACING_API_BLOCKED,
    "api_clean": SourceLabel.RACING_API_BLOCKED,
    "racing_api": SourceLabel.RACING_API_BLOCKED,
    "racing api": SourceLabel.RACING_API_BLOCKED,
    "theracingapi": SourceLabel.RACING_API_BLOCKED,
}


# ── Main enforcement function ─────────────────────────────────────────────────

def enforce_source_truth(
    loader_label: str,
    races: list[dict[str, Any]] | None = None,
    *,
    raise_on_block: bool = True,
) -> SourceTruthResult:
    """
    Translate a racecard_loader source label into a canonical harness label
    and enforce blocking/warning rules.

    Args:
        loader_label:   The raw label returned by racecard_loader.load_racecards()
                        ('cache', 'rp_merged', legacy API alias, or unknown).
        races:          The loaded races list (reserved for source validation).
        raise_on_block: If True (default), raise SourceTruthBlockError when
                        the label is SOURCE_UNKNOWN_BLOCK.

    Returns:
        SourceTruthResult with canonical label, execution_allowed, and warnings.

    Raises:
        SourceTruthBlockError: When source is unknown and raise_on_block=True.
    """
    warnings: list[str] = []
    canonical = _LOADER_TO_CANONICAL.get(loader_label.lower() if loader_label else "")

    if canonical is None:
        canonical = SourceLabel.SOURCE_UNKNOWN_BLOCK
        warnings.append(
            f"SOURCE_UNKNOWN_BLOCK: loader returned unrecognised label '{loader_label}'. "
            "Execution is blocked until source is declared."
        )
    elif canonical == SourceLabel.RACING_API_BLOCKED:
        warnings.append(
            "RACING_API_BLOCKED: Racing API is decommissioned for live VELO. "
            "Use Racing Post HTML/RP scraper artifacts only."
        )

    # RP merged truth is built from the validated Racing Post HTML injection.
    # Legacy PDF-only fields are optional and must not downgrade an HTML-clean day.

    execution_allowed = canonical in SourceLabel.ALLOWED
    degraded = canonical in SourceLabel.DEGRADED
    blocked = canonical in SourceLabel.BLOCKED

    if degraded:
        import warnings as _w
        _w.warn(
            f"VÉLØ source truth is {canonical}. Scoring will proceed with degraded features.",
            SourceTruthDegradedWarning,
            stacklevel=2,
        )

    result = SourceTruthResult(
        canonical_label=canonical,
        loader_label=loader_label,
        execution_allowed=execution_allowed,
        warnings=warnings,
        degraded=degraded,
        blocked=blocked,
    )

    if blocked and raise_on_block:
        raise SourceTruthBlockError(
            f"VÉLØ source truth enforcement: {canonical}. "
            f"Execution is blocked. Reason: {'; '.join(warnings)}"
        )

    return result


def assert_source_known(loader_label: str, races: list[dict[str, Any]] | None = None) -> SourceTruthResult:
    """
    Convenience wrapper: enforce source truth and raise immediately on BLOCK.
    Use this at the top of the scoring pipeline.
    """
    return enforce_source_truth(loader_label, races, raise_on_block=True)
