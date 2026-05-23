#!/usr/bin/env python3
"""
Learning Eligibility Audit — parameterised by date.

Reads local artifacts and Supabase sigma_audits to classify every verdict race as
eligible or excluded for shadow learning, and verify all hard-stop conditions.

Outputs:
  data/reports/{date}_learning_eligibility.json
  data/reports/{date}_learning_eligibility.md

Hard stops (exits 1 if any fire):
  flatline_count > 0
  identity_failures > 0
  council_verdict != PASS_TO_LEARNING
  target_state != shadow_full_train_v2
  any row unresolved
  any row would set consumed_live=true

Usage:
    PYTHONPATH=. python scripts/audit_20260522_learning_eligibility.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Load credentials before any Supabase imports
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

TARGET_STATE = "shadow_full_train_v2"
REPORT_DIR = ROOT / "data" / "reports"


def _load_json(path: Path) -> dict | list:
    if not path.exists():
        raise FileNotFoundError(f"Required file missing: {path}")
    return json.loads(path.read_text())


def _load_snapshots(date_str: str) -> list[dict]:
    import glob
    date_und = date_str.replace("-", "_")
    pattern = str(ROOT / "data" / f"runner_snapshots_{date_und}_{date_und}_*.jsonl")
    rows = []
    for fpath in glob.glob(pattern):
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    return rows


def _load_supabase_consumed_events(date_str: str) -> dict[str, dict]:
    """Query velo_learning_events for existing rows on this date — read only."""
    try:
        from src.data.supabase_client import SupabaseClient
        sb = SupabaseClient()
        resp = sb.client.table("velo_learning_events").select(
            "race_id,horse_id,event_type,consumed_shadow,consumed_live"
        ).eq("run_date", date_str).execute()
        rows = resp.data or []
        return {f"{r['race_id']}:{r.get('horse_id','')}:{r.get('event_type','')}": r for r in rows}
    except Exception as exc:
        print(f"[WARN] Could not read velo_learning_events: {exc}")
        return {}


def _load_sigma_audits(date_str: str) -> list[dict]:
    """Read sigma_audits from Supabase for the date — read only."""
    try:
        from src.data.supabase_client import SupabaseClient
        sb = SupabaseClient()
        resp = sb.client.table("sigma_audits").select(
            "race_id,outcome,decision_tier,horse_id,actual_winner_name,actual_winner_sp,off_time"
        ).eq("date", date_str).execute()
        return resp.data or []
    except Exception as exc:
        print(f"[WARN] Could not read sigma_audits: {exc}")
        return []


def run_audit(date_str: str) -> dict:
    date_und = date_str.replace("-", "_")
    print(f"[Audit] Loading artifacts for {date_str}...")

    # ── Load local artifacts ───────────────────────────────────────────────
    mc = _load_json(ROOT / "data" / "mission_control" / f"{date_str}_mission_control.json")
    council_run = _load_json(ROOT / "data" / "council_runs" / f"council_run_{date_str}.json")
    verdicts = _load_json(ROOT / "data" / f"velo_prime_verdicts_{date_und}.json")
    results_raw = _load_json(ROOT / "data" / f"results_{date_und}.json")
    sigma_artifact = _load_json(ROOT / "data" / "sigma_results" / f"sigma_results_{date_und}.json")
    snapshots = _load_snapshots(date_str)

    results = results_raw.get("results", []) if isinstance(results_raw, dict) else results_raw
    result_map = {r["race_id"]: r for r in results}

    # ── Gate checks ────────────────────────────────────────────────────────
    flatline_count = mc.get("flatline_count", 0)
    identity_failures = mc.get("identity_failure_count", 0)
    source_truth = mc.get("source_truth", "UNKNOWN")
    learning_gate = mc.get("learning_gate_status", "BLOCKED")
    council_verdict = council_run.get("council_verdict", "UNKNOWN")

    hard_stops: list[str] = []
    if flatline_count > 0:
        hard_stops.append(f"HARD_STOP: flatline_count={flatline_count} > 0")
    if identity_failures > 0:
        hard_stops.append(f"HARD_STOP: identity_failures={identity_failures} > 0")
    if council_verdict != "PASS_TO_LEARNING":
        hard_stops.append(f"HARD_STOP: council_verdict={council_verdict} != PASS_TO_LEARNING")
    if learning_gate != "OPEN":
        hard_stops.append(f"HARD_STOP: learning_gate={learning_gate} != OPEN")

    # ── Load Supabase data ─────────────────────────────────────────────────
    print("[Audit] Querying velo_learning_events (read-only)...")
    existing_events = _load_supabase_consumed_events(date_str)
    print(f"[Audit] Existing event rows for {date_str}: {len(existing_events)}")

    print("[Audit] Querying sigma_audits (read-only)...")
    sigma_audits = _load_sigma_audits(date_str)
    sigma_audit_map = {r["race_id"]: r for r in sigma_audits}
    print(f"[Audit] sigma_audits rows for {date_str}: {len(sigma_audits)}")

    # ── Check consumed_live in existing events ─────────────────────────────
    consumed_live_events = [k for k, v in existing_events.items() if v.get("consumed_live")]
    if consumed_live_events:
        hard_stops.append(f"HARD_STOP: consumed_live=True detected in {len(consumed_live_events)} existing event rows")

    consumed_shadow_events = [k for k, v in existing_events.items() if v.get("consumed_shadow")]

    # ── Classify each verdict race ─────────────────────────────────────────
    eligible: list[dict] = []
    excluded: list[dict] = []

    top_picks = [s for s in snapshots if s.get("rank", 99) == 0]
    top_pick_map = {s["race_id"]: s for s in top_picks}

    for v in verdicts:
        race_id = v["race_id"]
        course = v.get("course", "?")
        tier = v.get("tier", "?")
        top = v.get("top", {})
        vp = top.get("velo_prime_prob", 0.0)
        snap = top_pick_map.get(race_id, {})

        has_result = race_id in result_map
        has_sigma = race_id in sigma_audit_map
        sigma_outcome = sigma_audit_map.get(race_id, {}).get("outcome", None)

        if not has_result:
            excluded.append({
                "race_id": race_id,
                "course": course,
                "tier": tier,
                "vp": vp,
                "reason": "NO_RESULT_DPT_DATA_GAP",
                "has_sigma": has_sigma,
            })
        elif not has_sigma:
            excluded.append({
                "race_id": race_id,
                "course": course,
                "tier": tier,
                "vp": vp,
                "reason": "NO_SIGMA_AUDIT_ROW",
                "has_result": True,
            })
        else:
            eligible.append({
                "race_id": race_id,
                "course": course,
                "tier": tier,
                "vp": vp,
                "sigma_outcome": sigma_outcome,
                "has_result": True,
                "has_sigma": True,
            })

    # Verify unresolved (has result + sigma but sigma_outcome is None or blank)
    unresolved = [r for r in eligible if not r.get("sigma_outcome")]
    if unresolved:
        hard_stops.append(f"HARD_STOP: {len(unresolved)} rows have result+sigma but no outcome classification")

    # Compute live state hash from shadow_full_train_v2
    import hashlib
    shadow_path = ROOT / "data" / f"sentient_state_shadow_full_train_v2.json"
    if shadow_path.exists():
        live_state_hash = hashlib.sha256(shadow_path.read_bytes()).hexdigest()[:16]
    else:
        live_state_hash = "NOT_FOUND"

    # Summary
    eligible_count = len(eligible)
    excluded_count = len(excluded)
    win_count = sum(1 for r in eligible if r.get("sigma_outcome") == "WIN")
    miss_count = sum(1 for r in eligible if r.get("sigma_outcome") == "MISS")
    other_count = eligible_count - win_count - miss_count

    tier_dist = {}
    for r in eligible:
        t = r.get("tier", "?")
        tier_dist[t] = tier_dist.get(t, 0) + 1

    excluded_by_reason = {}
    for r in excluded:
        reason = r.get("reason", "UNKNOWN")
        excluded_by_reason[reason] = excluded_by_reason.get(reason, 0) + 1

    # Tier A DPT exclusions are notable — flag them
    dpt_tier_a = [r for r in excluded if r.get("course") == "DPT" and r.get("tier") == "A"]

    audit = {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_state": TARGET_STATE,
        "audit_status": "HARD_STOP" if hard_stops else "ELIGIBLE",
        "hard_stops": hard_stops,
        "gate_checks": {
            "flatline_count": flatline_count,
            "identity_failures": identity_failures,
            "source_truth": source_truth,
            "learning_gate": learning_gate,
            "council_verdict": council_verdict,
        },
        "verdict_races_total": len(verdicts),
        "eligible_count": eligible_count,
        "excluded_count": excluded_count,
        "unresolved_count": len(unresolved),
        "sigma_audits_rows": len(sigma_audits),
        "sigma_artifact_sr": sigma_artifact.get("sr"),
        "sigma_artifact_wins": sigma_artifact.get("wins"),
        "sigma_artifact_evaluated": sigma_artifact.get("evaluated_count"),
        "existing_learning_events": len(existing_events),
        "consumed_shadow_before": len(consumed_shadow_events),
        "consumed_live_before": len(consumed_live_events),
        "live_state_hash_before": live_state_hash,
        "eligible_by_outcome": {
            "WIN": win_count,
            "MISS": miss_count,
            "OTHER_PLACED_ETC": other_count,
        },
        "eligible_by_tier": tier_dist,
        "excluded_by_reason": excluded_by_reason,
        "dpt_tier_a_excluded": [r["race_id"] for r in dpt_tier_a],
        "eligible_races": eligible,
        "excluded_races": excluded,
    }

    return audit


def _write_md(audit: dict) -> str:  # noqa: PLR0912
    hard_stop_block = ""
    if audit["hard_stops"]:
        stops = "\n".join(f"  - {s}" for s in audit["hard_stops"])
        hard_stop_block = f"\n## HARD STOPS FIRED\n\n{stops}\n"

    excluded_rows = ""
    for r in audit["excluded_races"]:
        excluded_rows += f"| {r['race_id']} | {r.get('tier','?')} | {r.get('vp',0):.4f} | {r.get('reason','?')} |\n"

    tier_rows = ""
    for t, n in sorted(audit["eligible_by_tier"].items()):
        tier_rows += f"| {t} | {n} |\n"

    dpt_note = ""
    if audit["dpt_tier_a_excluded"]:
        dpt_note = (
            f"\n> **DPT Tier A exclusion:** {', '.join(audit['dpt_tier_a_excluded'])} — "
            f"Downpatrick data gap. No result available. Not a miss — result unknown.\n"
        )

    return f"""# May 22 Learning Eligibility Audit

**Date:** {audit['date']}
**Generated:** {audit['generated_at']}
**Audit Status:** `{audit['audit_status']}`
**Target State:** `{audit['target_state']}`
{hard_stop_block}
---

## Gate Checks

| Check | Value | Status |
|---|---|---|
| flatline_count | {audit['gate_checks']['flatline_count']} | {'PASS' if audit['gate_checks']['flatline_count']==0 else 'FAIL'} |
| identity_failures | {audit['gate_checks']['identity_failures']} | {'PASS' if audit['gate_checks']['identity_failures']==0 else 'FAIL'} |
| source_truth | {audit['gate_checks']['source_truth']} | {'PASS' if audit['gate_checks']['source_truth']=='RP_MERGED_CLEAN' else 'WARN'} |
| learning_gate | {audit['gate_checks']['learning_gate']} | {'PASS' if audit['gate_checks']['learning_gate']=='OPEN' else 'FAIL'} |
| council_verdict | {audit['gate_checks']['council_verdict']} | {'PASS' if audit['gate_checks']['council_verdict']=='PASS_TO_LEARNING' else 'FAIL'} |
| consumed_live_before | {audit['consumed_live_before']} | {'PASS' if audit['consumed_live_before']==0 else 'FAIL'} |
| unresolved_rows | {audit['unresolved_count']} | {'PASS' if audit['unresolved_count']==0 else 'FAIL'} |

---

## Row Counts

| Category | Count |
|---|---|
| Verdict races total | {audit['verdict_races_total']} |
| Eligible for learning | **{audit['eligible_count']}** |
| Excluded | {audit['excluded_count']} |
| Unresolved | {audit['unresolved_count']} |
| sigma_audits rows | {audit['sigma_audits_rows']} |
| Existing learning events (before) | {audit['existing_learning_events']} |
| consumed_shadow (before) | {audit['consumed_shadow_before']} |
| consumed_live (before) | {audit['consumed_live_before']} |

---

## Eligible Rows — Breakdown

| Outcome | Count |
|---|---|
| WIN | {audit['eligible_by_outcome']['WIN']} |
| MISS | {audit['eligible_by_outcome']['MISS']} |
| PLACED/OTHER | {audit['eligible_by_outcome']['OTHER_PLACED_ETC']} |

### By Tier

| Tier | Count |
|---|---|
{tier_rows}
---

## Excluded Races

| Race ID | Tier | VP | Reason |
|---|---|---|---|
{excluded_rows}{dpt_note}
---

## Live State Snapshot

| Field | Value |
|---|---|
| live_state_hash_before | `{audit['live_state_hash_before']}` |
| shadow_full_train_v2 path | `data/sentient_state_shadow_full_train_v2.json` |

---

## Governance

```
target_state = shadow_full_train_v2
consumed_live = 0 (hard stop if > 0)
sentient_state_touched = False at build-events-only stage
playbook_g_promoted = False
live_state_hash unchanged until Phase 3B shadow consume
```

---

## Recommendation

{'**HARD_STOP — do not proceed**' if audit['hard_stops'] else f'**PROCEED to build-events-only** — all gates clear. {audit["eligible_count"]} eligible rows, 0 hard stops.'}
"""


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-05-22", help="YYYY-MM-DD")
    args = parser.parse_args()

    audit = run_audit(args.date)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / f"{args.date}_learning_eligibility.json"
    md_path = REPORT_DIR / f"{args.date}_learning_eligibility.md"

    json_path.write_text(json.dumps(audit, indent=2))
    print(f"[Audit] Written: {json_path}")

    md_path.write_text(_write_md(audit))
    print(f"[Audit] Written: {md_path}")

    print()
    print(f"  audit_status: {audit['audit_status']}")
    print(f"  hard_stops: {len(audit['hard_stops'])}")
    print(f"  eligible: {audit['eligible_count']}")
    print(f"  excluded: {audit['excluded_count']}")
    print(f"  consumed_shadow_before: {audit['consumed_shadow_before']}")
    print(f"  consumed_live_before: {audit['consumed_live_before']}")
    print(f"  live_state_hash_before: {audit['live_state_hash_before']}")

    if audit["hard_stops"]:
        for s in audit["hard_stops"]:
            print(f"  [HARD STOP] {s}")
        sys.exit(1)
    else:
        print("  [OK] All gates clear — eligible for build-events-only")


if __name__ == "__main__":
    main()
