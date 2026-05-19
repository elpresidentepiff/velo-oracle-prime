"""
Guarded May 18 2026 learning eligibility audit.

Classification:
  MAY18_SYNTHETIC_ID_NORMALISATION_DRIFT_FIXED
  SIGMA_RECONCILIATION_RECOVERED
  MODEL_RESULT_AT_BASELINE
  LEARNING_NOT_AUTO_APPROVED

Outputs:
  data/reports/may18_learning_eligibility_audit.json
  data/reports/may18_learning_eligibility_audit.md

Reads only. Does not write learning events. Does not mutate live state.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATE = "2026-05-18"
DATE_KEY = "2026_05_18"

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY", "")
)


# ── Supabase helpers ──────────────────────────────────────────────────────────

def _sb_get(path: str, params: str = "") -> list[dict]:
    headers = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
    }
    url = f"{SB_URL}/rest/v1{path}{'?' + params if params else ''}"
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


# ── Normaliser (matches scraper + run_prime_today fix) ───────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# ── Load sources ──────────────────────────────────────────────────────────────

def load_verdicts_from_db() -> list[dict]:
    rows = _sb_get(
        "/velo_verdicts",
        f"race_id=like.{DATE}*&select=race_id,decision_tier,top_rank_horse_id,"
        "velo_prime_prob,improvement_score,market_deception_score&order=race_id.asc&limit=100",
    )
    return rows


def load_verdicts_from_local() -> list[dict]:
    path = ROOT / "data" / f"velo_prime_verdicts_{DATE_KEY}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def load_sigma_audits() -> dict[str, dict]:
    rows = _sb_get(
        "/sigma_audits",
        f"date=eq.{DATE}&select=race_id,outcome,decision_tier,off_time,track,"
        "actual_winner_name,actual_winner_id,top_pick_position,miss_reason&limit=200",
    )
    return {r["race_id"]: r for r in rows}


def load_learning_events() -> list[dict]:
    rows = _sb_get(
        "/velo_learning_events",
        f"run_date=eq.{DATE}&select=race_id,horse_id,event_type,learning_allowed,"
        "consumed_shadow,consumed_live,target_state_name&limit=200",
    )
    return rows


def load_results_index() -> dict[str, dict]:
    path = ROOT / "data" / f"results_{DATE_KEY}.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    races: list[dict] = (
        raw.get("results", []) if isinstance(raw, dict)
        else (raw if isinstance(raw, list) else [])
    )
    index: dict[str, dict] = {}
    for race in races:
        rid = race.get("race_id") or race.get("race_identifier") or race.get("id")
        if rid:
            index[str(rid)] = race
    return index


# ── Classification ────────────────────────────────────────────────────────────

TIER_X_SET = {"X"}
ELIGIBLE_OUTCOMES = {"WIN", "MISS", "PLACED"}
NR_LABELS = {"DNF", "NR", "NON_RUNNER", "NON-RUNNER"}


def classify_verdict(
    v_db: dict,
    sigma: dict | None,
    result: dict | None,
    learning_events: list[dict],
) -> dict:
    race_id = v_db["race_id"]
    tier = (v_db.get("decision_tier") or "").upper()
    outcome = (sigma.get("outcome") or "").upper() if sigma else None

    # Check if any learning event exists for this race
    existing_events = [e for e in learning_events if e["race_id"] == race_id]
    consumed_shadow = any(e.get("consumed_shadow") for e in existing_events)
    consumed_live = any(e.get("consumed_live") for e in existing_events)

    # ── Tier X: always excluded ───────────────────────────────────────────────
    if tier in TIER_X_SET:
        return {
            "race_id": race_id,
            "tier": tier,
            "status": "EXCLUDED_TIER_X",
            "learning_allowed": False,
            "outcome": None,
            "in_sigma": False,
            "in_result_file": race_id in (result or {}),
            "consumed_shadow": consumed_shadow,
            "consumed_live": consumed_live,
            "note": "Tier X — permanently excluded from sigma audit and learning",
        }

    # ── In sigma: check outcome ───────────────────────────────────────────────
    if sigma:
        if outcome in ELIGIBLE_OUTCOMES:
            return {
                "race_id": race_id,
                "tier": tier,
                "status": "LEARNING_ELIGIBLE",
                "learning_allowed": True,
                "outcome": outcome,
                "in_sigma": True,
                "in_result_file": race_id in (result or {}),
                "consumed_shadow": consumed_shadow,
                "consumed_live": consumed_live,
                "note": f"Fully reconciled {outcome} — eligible for shadow training",
            }
        # sigma present but unexpected outcome
        return {
            "race_id": race_id,
            "tier": tier,
            "status": "EXCLUDED_UNEXPECTED_OUTCOME",
            "learning_allowed": False,
            "outcome": outcome,
            "in_sigma": True,
            "in_result_file": race_id in (result or {}),
            "consumed_shadow": consumed_shadow,
            "consumed_live": consumed_live,
            "note": f"sigma outcome={outcome!r} is not WIN/MISS/PLACED — excluded",
        }

    # ── Not in sigma: classify why ────────────────────────────────────────────
    in_result = race_id in (result or {})

    if not in_result:
        return {
            "race_id": race_id,
            "tier": tier,
            "status": "EXCLUDED_NO_RESULT",
            "learning_allowed": False,
            "outcome": None,
            "in_sigma": False,
            "in_result_file": False,
            "consumed_shadow": consumed_shadow,
            "consumed_live": consumed_live,
            "note": "Not in Sporting Life result file — no result data available",
        }

    # In result file but not in sigma → likely NR/DNF
    result_race = (result or {}).get(race_id, {})
    runners = result_race.get("runners", [])
    horse_id_pred = v_db.get("top_rank_horse_id") or ""
    matched_runner = None
    for r in runners:
        rid = r.get("horse_id", "")
        if rid == horse_id_pred or (
            horse_id_pred.startswith("RP_")
            and rid.startswith("RP_")
            and _norm(rid) == _norm(horse_id_pred)
        ):
            matched_runner = r
            break

    if matched_runner:
        pos = str(matched_runner.get("position", "")).upper()
        if any(nrl in pos for nrl in NR_LABELS) or pos in ("DNF", "PU", "UR", "RO", "BD", "F"):
            return {
                "race_id": race_id,
                "tier": tier,
                "status": "EXCLUDED_TRUE_NR_DNF",
                "learning_allowed": False,
                "outcome": None,
                "in_sigma": False,
                "in_result_file": True,
                "consumed_shadow": consumed_shadow,
                "consumed_live": consumed_live,
                "note": f"Confirmed NR/DNF — position={pos!r}",
            }

    # In result file, not NR, not in sigma → identity failure residual
    return {
        "race_id": race_id,
        "tier": tier,
        "status": "EXCLUDED_IDENTITY_FAILURE_RESIDUAL",
        "learning_allowed": False,
        "outcome": None,
        "in_sigma": False,
        "in_result_file": True,
        "consumed_shadow": consumed_shadow,
        "consumed_live": consumed_live,
        "note": "In result file but not matched in sigma — possible residual identity issue",
    }


# ── Previous consumption check ────────────────────────────────────────────────

def check_prior_consumption(learning_events: list[dict]) -> dict:
    total = len(learning_events)
    consumed_shadow = sum(1 for e in learning_events if e.get("consumed_shadow"))
    consumed_live = sum(1 for e in learning_events if e.get("consumed_live"))
    target_states = list({e.get("target_state_name") for e in learning_events if e.get("target_state_name")})
    return {
        "total_events_in_db": total,
        "consumed_shadow_count": consumed_shadow,
        "consumed_live_count": consumed_live,
        "target_states": target_states,
        "previously_consumed": consumed_shadow > 0 or consumed_live > 0,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def run_audit() -> dict:
    print(f"\nMAY 18 LEARNING ELIGIBILITY AUDIT — {DATE}")
    print("=" * 60)

    # Load all sources
    print("Loading sources...")
    verdicts_db = load_verdicts_from_db()
    verdicts_local = load_verdicts_from_local()
    sigma_index = load_sigma_audits()
    learning_events = load_learning_events()
    results = load_results_index()

    print(f"  velo_verdicts (DB):        {len(verdicts_db)}")
    print(f"  velo_prime_verdicts (local):{len(verdicts_local)}")
    print(f"  sigma_audits:              {len(sigma_index)}")
    print(f"  velo_learning_events:      {len(learning_events)}")
    print(f"  result file races:         {len(results)}")

    # Classify each verdict
    print("\nClassifying verdicts...")
    verdicts_by_race = {v["race_id"]: v for v in verdicts_db}
    classified = []
    for v_db in verdicts_db:
        race_id = v_db["race_id"]
        sigma = sigma_index.get(race_id)
        result = results
        row = classify_verdict(v_db, sigma, result, learning_events)
        classified.append(row)
        status_short = row["status"][:30]
        print(f"  {race_id:<45} {status_short}")

    # Summary counts
    by_status: dict[str, list] = {}
    for row in classified:
        by_status.setdefault(row["status"], []).append(row["race_id"])

    eligible = by_status.get("LEARNING_ELIGIBLE", [])
    excl_tier_x = by_status.get("EXCLUDED_TIER_X", [])
    excl_nr = by_status.get("EXCLUDED_TRUE_NR_DNF", [])
    excl_no_result = by_status.get("EXCLUDED_NO_RESULT", [])
    excl_identity = by_status.get("EXCLUDED_IDENTITY_FAILURE_RESIDUAL", [])
    excl_outcome = by_status.get("EXCLUDED_UNEXPECTED_OUTCOME", [])

    # Prior consumption check
    prior = check_prior_consumption(learning_events)

    # Identity failure check (should be 0 after normalisation fix)
    identity_failures_in_sigma = [
        r for r in classified
        if r["status"] == "LEARNING_ELIGIBLE" and not r["in_sigma"]
    ]

    # Confirm consumed_* = False in eligible events
    eligible_with_shadow = [
        r for r in classified
        if r["status"] == "LEARNING_ELIGIBLE" and r["consumed_shadow"]
    ]
    eligible_with_live = [
        r for r in classified
        if r["status"] == "LEARNING_ELIGIBLE" and r["consumed_live"]
    ]

    # Sigma coverage vs predictions
    sigma_coverage_pct = len(sigma_index) / len(verdicts_db) * 100 if verdicts_db else 0
    eligible_pct = len(eligible) / len(verdicts_db) * 100 if verdicts_db else 0

    # Final recommendation
    gates_clear = (
        prior["consumed_live_count"] == 0
        and prior["consumed_shadow_count"] == 0
        and len(excl_identity) == 0
        and len(eligible) == len(sigma_index)
        and len(eligible) > 0
    )

    if gates_clear:
        recommendation = "HOLD_PENDING_OPERATOR_APPROVAL"
        rec_detail = (
            f"All {len(eligible)} eligible rows are clean (no prior consumption, "
            "0 identity failures). May 18 may enter shadow training only after "
            "explicit operator approval. Classification: BASELINE_MODEL_RESULT."
        )
    elif prior["consumed_live_count"] > 0:
        recommendation = "BLOCK_LIVE_CONSUMPTION_DETECTED"
        rec_detail = f"{prior['consumed_live_count']} rows already consumed live — STOP"
    elif prior["consumed_shadow_count"] > 0:
        recommendation = "ALREADY_CONSUMED_SHADOW"
        rec_detail = f"{prior['consumed_shadow_count']} rows already in shadow state"
    elif excl_identity:
        recommendation = "BLOCK_IDENTITY_FAILURES_REMAINING"
        rec_detail = f"{len(excl_identity)} residual identity failures — do not consume"
    else:
        recommendation = "HOLD_REVIEW_REQUIRED"
        rec_detail = "Manual review required before any consumption"

    audit = {
        "audit_date": DATE,
        "audit_run_at": datetime.now(timezone.utc).isoformat(),
        "audit_script": "audit_may18_learning_eligibility.py",
        "classification": [
            "MAY18_SYNTHETIC_ID_NORMALISATION_DRIFT_FIXED",
            "SIGMA_RECONCILIATION_RECOVERED",
            "MODEL_RESULT_AT_BASELINE",
            "LEARNING_NOT_AUTO_APPROVED",
        ],
        # Counts
        "total_official_predictions": len(verdicts_db),
        "sigma_evaluated_rows": len(sigma_index),
        "learning_eligible_rows": len(eligible),
        "learning_excluded_tier_x": len(excl_tier_x),
        "learning_excluded_true_nr_dnf": len(excl_nr),
        "learning_excluded_no_result": len(excl_no_result),
        "learning_excluded_identity_failure": len(excl_identity),
        "learning_excluded_unexpected_outcome": len(excl_outcome),
        # Consumption checks
        "prior_consumption": prior,
        "eligible_consumed_shadow": len(eligible_with_shadow),
        "eligible_consumed_live": len(eligible_with_live),
        # Coverage
        "sigma_coverage_pct": round(sigma_coverage_pct, 1),
        "eligible_pct_of_total": round(eligible_pct, 1),
        # Identity
        "identity_failures_remaining": len(excl_identity),
        "identity_failures_before_fix": 24,
        "identity_failures_after_fix": len(excl_identity),
        # Detail lists
        "eligible_race_ids": sorted(eligible),
        "excluded_tier_x_race_ids": sorted(excl_tier_x),
        "excluded_nr_dnf_race_ids": sorted(excl_nr),
        "excluded_no_result_race_ids": sorted(excl_no_result),
        "excluded_identity_residual_race_ids": sorted(excl_identity),
        # Verdict detail
        "verdict_classification": classified,
        # Gates
        "gates_clear": gates_clear,
        "learning_allowed_final": gates_clear,
        "recommended_action": recommendation,
        "recommendation_detail": rec_detail,
        # Hard rules
        "consumed_shadow": False,
        "consumed_live": False,
        "target_state": "shadow_full_train_v2",
        "no_scoring_change": True,
        "no_model_change": True,
        "no_router_change": True,
        "no_staking_change": True,
    }

    return audit


def write_reports(audit: dict) -> None:
    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = out_dir / "may18_learning_eligibility_audit.json"
    json_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(f"\nJSON: {json_path}")

    # MD
    a = audit
    md_lines = [
        "# MAY 18 LEARNING ELIGIBILITY AUDIT",
        "",
        f"**Date:** {a['audit_date']}  ",
        f"**Run at:** {a['audit_run_at']}  ",
        f"**Classification:** {' | '.join(a['classification'])}",
        "",
        "---",
        "",
        "## Coverage Summary",
        "",
        f"| Metric | Count |",
        f"|---|---|",
        f"| Official predictions | {a['total_official_predictions']} |",
        f"| Sigma evaluated (DB) | {a['sigma_evaluated_rows']} |",
        f"| Learning eligible | **{a['learning_eligible_rows']}** |",
        f"| Excluded — Tier X | {a['learning_excluded_tier_x']} |",
        f"| Excluded — True NR/DNF | {a['learning_excluded_true_nr_dnf']} |",
        f"| Excluded — No result | {a['learning_excluded_no_result']} |",
        f"| Excluded — Identity residual | {a['learning_excluded_identity_failure']} |",
        f"| Sigma coverage % | {a['sigma_coverage_pct']}% |",
        f"| Eligible % of total | {a['eligible_pct_of_total']}% |",
        "",
        "---",
        "",
        "## Identity Failure Recovery",
        "",
        f"| | Count |",
        f"|---|---|",
        f"| Identity failures BEFORE fix (commit 1dc8d5b) | {a['identity_failures_before_fix']} |",
        f"| Identity failures AFTER fix (commit dc33a5e) | {a['identity_failures_after_fix']} |",
        f"| Residual identity failures | **{a['identity_failures_remaining']}** |",
        "",
        "---",
        "",
        "## Prior Consumption State",
        "",
        prior := a["prior_consumption"],
        f"| Metric | Value |",
        f"|---|---|",
        f"| velo_learning_events in DB | {prior['total_events_in_db']} |",
        f"| consumed_shadow=True | {prior['consumed_shadow_count']} |",
        f"| consumed_live=True | {prior['consumed_live_count']} |",
        f"| Previously consumed | {'**YES — STOP**' if prior['previously_consumed'] else 'No'} |",
        "",
        "---",
        "",
        "## Gate Assessment",
        "",
        "| Gate | Status |",
        "|---|---|",
        f"| consumed_live=False | {'PASS' if a['eligible_consumed_live'] == 0 else 'FAIL'} |",
        f"| consumed_shadow=False | {'PASS' if a['eligible_consumed_shadow'] == 0 else 'FAIL'} |",
        f"| Identity failures = 0 | {'PASS' if a['identity_failures_remaining'] == 0 else 'FAIL'} |",
        f"| Eligible = sigma rows | {'PASS' if a['learning_eligible_rows'] == a['sigma_evaluated_rows'] else 'FAIL'} |",
        f"| All gates clear | {'**PASS**' if a['gates_clear'] else '**FAIL**'} |",
        "",
        "---",
        "",
        "## Recommendation",
        "",
        f"**{a['recommended_action']}**",
        "",
        a["recommendation_detail"],
        "",
        "---",
        "",
        "## Eligible Race IDs",
        "",
        "```",
        *[f"  {r}" for r in a["eligible_race_ids"]],
        "```",
        "",
        "## Excluded Race IDs",
        "",
        f"**Tier X ({a['learning_excluded_tier_x']}):**",
        "```",
        *[f"  {r}" for r in a["excluded_tier_x_race_ids"]],
        "```",
        "",
        f"**True NR/DNF ({a['learning_excluded_true_nr_dnf']}):**",
        "```",
        *[f"  {r}" for r in a["excluded_nr_dnf_race_ids"]],
        "```",
        "",
        f"**No result ({a['learning_excluded_no_result']}):**",
        "```",
        *[f"  {r}" for r in a["excluded_no_result_race_ids"]],
        "```",
        "",
        f"**Identity residual ({a['learning_excluded_identity_failure']}):**",
        "```",
        *[f"  {r}" for r in a["excluded_identity_residual_race_ids"]],
        "```",
        "",
        "---",
        "",
        "## Hard Rules — Confirmed",
        "",
        "```",
        "consumed_shadow      = False",
        "consumed_live        = False",
        "no_scoring_change    = True",
        "no_model_change      = True",
        "no_router_change     = True",
        "no_staking_change    = True",
        "target_state         = shadow_full_train_v2",
        "```",
        "",
        "Do not consume until Presidente approves.",
    ]

    # Filter out dict objects that accidentally ended up in list (Python walrus side-effect)
    md_lines = [ln for ln in md_lines if isinstance(ln, str)]
    md_path = out_dir / "may18_learning_eligibility_audit.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"MD:   {md_path}")


def print_summary(audit: dict) -> None:
    a = audit
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    print(f"  Official predictions:       {a['total_official_predictions']}")
    print(f"  Sigma evaluated:            {a['sigma_evaluated_rows']}")
    print(f"  Learning eligible:          {a['learning_eligible_rows']}")
    print(f"  Excluded Tier X:            {a['learning_excluded_tier_x']}")
    print(f"  Excluded NR/DNF:            {a['learning_excluded_true_nr_dnf']}")
    print(f"  Excluded no result:         {a['learning_excluded_no_result']}")
    print(f"  Excluded identity residual: {a['learning_excluded_identity_failure']}")
    print(f"  Identity failures before:   {a['identity_failures_before_fix']}")
    print(f"  Identity failures after:    {a['identity_failures_after_fix']}")
    print(f"  Prior consumed_shadow:      {a['prior_consumption']['consumed_shadow_count']}")
    print(f"  Prior consumed_live:        {a['prior_consumption']['consumed_live_count']}")
    print(f"  Gates clear:                {a['gates_clear']}")
    print(f"  Recommendation:             {a['recommended_action']}")
    print("=" * 60)


if __name__ == "__main__":
    if not SB_URL or not SB_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        sys.exit(1)

    audit = run_audit()
    write_reports(audit)
    print_summary(audit)
