#!/usr/bin/env python3
"""Say whether the lanes that depend on the passport bank had the inputs they need today.

Prime does not read the passport bank, so it scores whatever happens here. New Build A/B/C,
Champion Intent and the Passport proxy do. Until 2026-11-15 the only signal was a warning line in
a log: on 2026-11-12 the cloud run printed "59/224 runners have a passport (26.3%)" and then
scored, persisted and settled those lanes exactly as on a healthy day.

A day is DEGRADED when the Supabase hydrate did not complete, or when GB/IRE passport coverage is
below the coverage threshold. The verdict is written to one file, stamped onto every scorecard
row of the dependent lanes, and persisted with the day's report artifacts so the evening rebuild
keeps it. It does not stop the day: by standing operator ruling a degraded day still scores.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
HYDRATE_STEP = "Durable state: hydrate passport bank and form history from Supabase"

# Lanes whose inputs come from the passport bank or the form history behind it.
DEPENDENT_MODELS = frozenset(
    {
        "NEW_BUILD_LANE_A_MODEL",
        "NEW_BUILD_LANE_B_MODEL",
        "NEW_BUILD_LANE_C_MODEL",
        "CHAMPION_INTENT_SHADOW",
        "PASSPORT_STRENGTH_SCORE_PROXY",
    }
)


def health_path(date: str, root: Path = ROOT) -> Path:
    return root / "data" / "reports" / f"new_build_input_health_{date.replace('-', '_')}.json"


def hydrate_outcome(results: list[dict]) -> str:
    """OK, FAILED or NOT_RUN, from the morning runner's own step results."""
    for step in results:
        if step.get("step") == HYDRATE_STEP:
            return "OK" if step.get("ok") else "FAILED"
    return "NOT_RUN"


def assess(date: str, *, hydrate: str, coverage: dict) -> dict:
    """The day's verdict. ``coverage`` is the stats dict from check_passport_coverage."""
    threshold = float(coverage.get("threshold") or 0.0)
    split = bool(coverage.get("region_split_available"))
    measured = float(coverage.get("gbire_coverage" if split else "coverage") or 0.0)
    reasons: list[str] = []
    if hydrate != "OK":
        reasons.append(f"SUPABASE_HYDRATE_{hydrate}: the passport bank is the git copy, not Supabase")
    if coverage.get("error"):
        reasons.append(f"PASSPORT_FEED_{coverage['error']}")
    elif measured < threshold:
        reasons.append(
            f"PASSPORT_COVERAGE_BELOW_THRESHOLD: {measured:.1%} of {'GB/IRE' if split else 'all'} runners "
            f"have a passport, threshold {threshold:.0%}"
        )
    return {
        "date": date,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": DEGRADED if reasons else HEALTHY,
        "reasons": reasons,
        "hydrate": hydrate,
        "passport_coverage": round(measured, 4),
        "coverage_basis": "GB/IRE" if split else "ALL_COURSES",
        "threshold": threshold,
        "runners": coverage.get("gbire_total" if split else "total"),
        "runners_with_passport": coverage.get("gbire_found" if split else "found"),
        "dependent_models": sorted(DEPENDENT_MODELS),
    }


def write(verdict: dict, root: Path = ROOT) -> Path:
    path = health_path(verdict["date"], root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    return path


def load(date: str, root: Path = ROOT) -> dict | None:
    path = health_path(date, root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def row_note(model_name: str | None, verdict: dict | None) -> str:
    """Text to put in front of a scorecard row's notes, or '' when the row is unaffected.

    A day with no verdict at all is reported as unverified for the dependent lanes: missing
    evidence is not a pass.
    """
    if model_name not in DEPENDENT_MODELS:
        return ""
    if verdict is None:
        return "INPUT_HEALTH_UNVERIFIED: no passport-input verdict was recorded for this day."
    if verdict.get("status") != DEGRADED:
        return ""
    return "INPUT_DEGRADED: " + "; ".join(verdict.get("reasons") or ["unspecified"]) + "."
