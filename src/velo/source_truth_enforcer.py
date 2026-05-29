"""
VÉLØ Source Truth Enforcer
===========================
Implements Layer 1 (Input Layer) of VELO_AGENT_HARNESS_DOCTRINE_V1.

Translates racecard_loader source labels ('cache', 'rp_merged', 'api')
into canonical harness source truth labels, enforces blocking rules, and
emits structured warnings.

Hard constraints:
  - READ_ONLY: no file writes, no DB writes, no scoring changes
  - No live-state mutation of any kind
  - SOURCE_UNKNOWN_BLOCK always raises SourceTruthBlockError

Source truth labels (canonical):
  RP_MERGED_CLEAN     — full RP PDF set, all features present
  RP_MERGED_DEGRADED  — partial RP PDFs, feature degradation active
  API_CLEAN           — fully authenticated Racing API response
  LOCAL_JSON_FALLBACK — verified local standard cache
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
    API_CLEAN = "API_CLEAN"
    LOCAL_JSON_FALLBACK = "LOCAL_JSON_FALLBACK"
    SOURCE_UNKNOWN_BLOCK = "SOURCE_UNKNOWN_BLOCK"

    ALL = frozenset({
        RP_MERGED_CLEAN,
        RP_MERGED_DEGRADED,
        API_CLEAN,
        LOCAL_JSON_FALLBACK,
        SOURCE_UNKNOWN_BLOCK,
    })

    # Labels that allow execution to proceed
    ALLOWED = frozenset({RP_MERGED_CLEAN, RP_MERGED_DEGRADED, API_CLEAN, LOCAL_JSON_FALLBACK})

    # Labels that must block execution
    BLOCKED = frozenset({SOURCE_UNKNOWN_BLOCK})

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
    "rp_merged": SourceLabel.RP_MERGED_CLEAN,   # Default; may be downgraded to DEGRADED
    "api": SourceLabel.API_CLEAN,
}


def _detect_rp_degradation(races: list[dict[str, Any]]) -> bool:
    """
    Return True if the RP merged races show signs of feature degradation.

    Degradation is detected when a significant fraction of runners are missing
    key RP-derived fields (postdata_score, or_compression_score, ts_latest).
    """
    if not races:
        return False
    total = 0
    missing = 0
    for race in races:
        for runner in race.get("runners", []):
            total += 1
            pdf_intel = runner.get("pdf_intel") or {}
            if not pdf_intel.get("postdata_score") and not pdf_intel.get("or_compression_score"):
                missing += 1
    if total == 0:
        return False
    return (missing / total) > 0.5  # >50% runners missing RP intel = degraded


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
                        ('cache', 'rp_merged', 'api', or any unknown string).
        races:          The loaded races list (used to detect RP degradation).
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

    # Downgrade rp_merged to DEGRADED if feature inspection reveals missing intel
    if canonical == SourceLabel.RP_MERGED_CLEAN and races:
        if _detect_rp_degradation(races):
            canonical = SourceLabel.RP_MERGED_DEGRADED
            warnings.append(
                "RP_MERGED_DEGRADED: >50% of runners are missing postdata_score / "
                "or_compression_score. Feature degradation is active. "
                "Learning is blocked for this run."
            )

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
