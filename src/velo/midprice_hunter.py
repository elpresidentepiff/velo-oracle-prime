"""
VÉLØ Mid-Price Hunter — SP 3.0–8.5 top-pick shadow suppressor.

Issue #78 Track A. Phase 1 forensic audit (PR #79) identified:
  - 706 mid-price misses = 54.3% of all misses across 40 race days
  - MDS is 2.7× higher in wins than mid-price misses (0.173 vs 0.064)
  - VP≥0.30 + MDS≥0.30 → SR=55%, MP-miss-rate=18%
  - VP≥0.30 + MDS<0.30 → SR=24%, MP-miss-rate=35%

This module runs AFTER score_race_velo_prime() returns. It reads only
the top pick's already-computed sidecar scores — it does NOT modify
velo_prime_prob, decision_tier, assigned_product, or execution_allowed.

Output: per-race shadow verdict written to data/midprice_shadow_ledger.csv.

Hard constraints (permanent — never override):
  live_scoring_changed = False  always
  execution_allowed = False     always
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ── Shadow action labels ───────────────────────────────────────────────────

MIDPRICE_SUPPRESS_TOP = "MIDPRICE_SUPPRESS_TOP"
MIDPRICE_NO_EDGE = "MIDPRICE_NO_EDGE"
MIDPRICE_SPLIT_RACE = "MIDPRICE_SPLIT_RACE"
MIDPRICE_CLEAN = "MIDPRICE_CLEAN"

# ── Thresholds (from Phase 1 forensic audit — do not change without audit) ─

_VP_GATE = 0.30  # Minimum VP for SUPPRESS_TOP rule
_MDS_GATE = 0.30  # MDS below this = deception signal absent
_MDS_LOW = 0.05  # Near-zero MDS = near-blind
_IMPROVE_LOW = 0.10  # Improvement absent
_VP_NO_EDGE_MAX = 0.30  # Upper VP bound for NO_EDGE rule
_VP_NO_EDGE_MIN = 0.20  # Lower VP bound for NO_EDGE rule
_VP_SPLIT_MIN = 0.40  # High-conviction zone for SPLIT_RACE
_MDS_SPLIT_MAX = 0.20  # Weak MDS in high-conviction zone
_IMPROVE_SPLIT_MAX = 0.20  # Weak improvement in high-conviction zone

# ── Ledger path ────────────────────────────────────────────────────────────

_DEFAULT_LEDGER = Path("data/midprice_shadow_ledger.csv")

_LEDGER_FIELDS = [
    "created_at",
    "race_date",
    "race_id",
    "course",
    "off_time",
    "tier",
    "top_pick",
    "top_vp",
    "top_mds",
    "top_improvement",
    "top_place_prob",
    "shadow_action",
    "evidence",
    "live_scoring_changed",
    "execution_allowed",
]


def evaluate_race(
    race_id: str,
    race_date: str,
    course: str,
    off_time: str,
    tier: str,
    top_pick: str,
    top_vp: float | None,
    top_mds: float | None,
    top_improvement: float | None,
    top_place_prob: float | None,
) -> dict[str, Any]:
    """
    Evaluate mid-price displacement risk for one race using top-pick signals.

    Returns a shadow verdict dict. Never modifies live scoring state.
    live_scoring_changed and execution_allowed are always False.
    """
    vp = top_vp or 0.0
    mds = top_mds or 0.0
    imp = top_improvement or 0.0

    shadow_action, evidence = _apply_rules(tier, vp, mds, imp)

    return {
        "created_at": datetime.now(tz=UTC).isoformat(),
        "race_date": race_date,
        "race_id": race_id,
        "course": course,
        "off_time": off_time,
        "tier": tier,
        "top_pick": top_pick,
        "top_vp": top_vp,
        "top_mds": top_mds,
        "top_improvement": top_improvement,
        "top_place_prob": top_place_prob,
        "shadow_action": shadow_action,
        "evidence": "|".join(evidence),
        "live_scoring_changed": False,
        "execution_allowed": False,
    }


def _apply_rules(
    tier: str,
    vp: float,
    mds: float,
    imp: float,
) -> tuple[str, list[str]]:
    """
    Return (shadow_action, evidence_tags) for the given signal state.

    Rule priority: SPLIT_RACE > SUPPRESS_TOP > NO_EDGE > CLEAN.
    All rule thresholds derived from Phase 1 forensic audit (PR #79).
    """
    evidence: list[str] = []

    # Rule 3: MIDPRICE_SPLIT_RACE
    # Tier A + high VP + both MDS and improvement absent
    # n=45, wins=11 SR=24%, MP-miss-rate=13% — rarest but highest-damage zone
    if tier == "A" and vp >= _VP_SPLIT_MIN and mds < _MDS_SPLIT_MAX and imp < _IMPROVE_SPLIT_MAX:
        evidence.append("TIER_A")
        evidence.append(f"VP_HIGH:{vp:.3f}")
        evidence.append(f"MDS_WEAK:{mds:.4f}")
        evidence.append(f"IMP_WEAK:{imp:.4f}")
        return MIDPRICE_SPLIT_RACE, evidence

    # Rule 1: MIDPRICE_SUPPRESS_TOP
    # VP≥0.30 + MDS<0.30 — primary rule from Phase 1
    # n=345, SR=24%, MP-miss-rate=35% (vs 18% when MDS≥0.30)
    if vp >= _VP_GATE and mds < _MDS_GATE:
        evidence.append(f"VP_ABOVE_GATE:{vp:.3f}")
        evidence.append(f"MDS_BELOW_GATE:{mds:.4f}")
        if mds < _MDS_LOW:
            evidence.append("MDS_NEAR_ZERO")
        return MIDPRICE_SUPPRESS_TOP, evidence

    # Rule 2: MIDPRICE_NO_EDGE
    # Borderline VP + near-zero MDS + low improvement
    # n=343, SR=18%, MP-miss-rate=50%
    if _VP_NO_EDGE_MIN <= vp < _VP_NO_EDGE_MAX and mds < _MDS_LOW and imp < _IMPROVE_LOW:
        evidence.append(f"VP_BORDERLINE:{vp:.3f}")
        evidence.append(f"MDS_NEAR_ZERO:{mds:.4f}")
        evidence.append(f"IMP_ABSENT:{imp:.4f}")
        return MIDPRICE_NO_EDGE, evidence

    return MIDPRICE_CLEAN, [f"VP:{vp:.3f}", f"MDS:{mds:.4f}"]


def append_to_ledger(
    verdict: dict[str, Any],
    ledger_path: Path | str | None = None,
) -> None:
    """
    Append a shadow verdict row to the mid-price shadow ledger CSV.
    Creates the file with headers on first write.
    """
    path = Path(ledger_path or _DEFAULT_LEDGER)
    path.parent.mkdir(parents=True, exist_ok=True)

    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_LEDGER_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(verdict)


def evaluate_and_log(
    race_id: str,
    race_date: str,
    course: str,
    off_time: str,
    tier: str,
    top_pick: str,
    top_vp: float | None,
    top_mds: float | None,
    top_improvement: float | None,
    top_place_prob: float | None,
    ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    """
    Evaluate and immediately append to the shadow ledger.
    Convenience wrapper for call sites in run_prime_today.py.
    """
    verdict = evaluate_race(
        race_id=race_id,
        race_date=race_date,
        course=course,
        off_time=off_time,
        tier=tier,
        top_pick=top_pick,
        top_vp=top_vp,
        top_mds=top_mds,
        top_improvement=top_improvement,
        top_place_prob=top_place_prob,
    )
    append_to_ledger(verdict, ledger_path=ledger_path)
    return verdict
