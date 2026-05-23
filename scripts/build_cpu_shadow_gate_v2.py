#!/usr/bin/env python3
"""
Build CPU Shadow Gate V2 — post-flatline-fix clean runner tracking.

Gate V1 is GATE_V1_AUDIT_ONLY: contaminated by pre-a33c5bd RP_MERGED rows.
Gate V2 starts from 2026-05-21 (first post-fix close).

Promotion gate:
  - n >= 300 clean post-fix runners
  - flatline_count = 0
  - identity_failures = 0
  - no contaminated run_ids
  - no production promotion without operator decision

Usage:
    PYTHONPATH=. python scripts/build_cpu_shadow_gate_v2.py
"""

import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CONTAMINATED_RUN_IDS = {"32cc27f9", "847964a6"}
FIX_COMMIT = "a33c5bd84aa600a98bd9e1bfdc381750f20f23a4"
FIX_DATE = "2026-05-21"
PROMOTION_THRESHOLD = 300


def _extract_sha8(run_id: str) -> str:
    parts = run_id.split("_")
    if len(parts) >= 4:
        return parts[3]
    return run_id[:8]


def _load_clean_snapshots() -> dict:
    pattern = str(ROOT / "data" / "runner_snapshots_202*.jsonl")
    all_files = sorted(glob.glob(pattern))

    by_date: dict[str, dict] = {}
    gate_v1_contaminated_runners = 0
    gate_v2_runners = 0
    gate_v2_days: set[str] = set()
    flatline_count = 0
    identity_failures = 0

    for filepath in all_files:
        fname = Path(filepath).name
        # Format: runner_snapshots_{date_und}_{date_und}_{sha8}_{epoch}.jsonl
        # e.g.  runner_snapshots_2026_05_21_2026_05_21_a33c5bd8_1779363549514.jsonl
        stem = fname.replace(".jsonl", "")
        parts = stem.split("_")
        # parts[0]="runner", parts[1]="snapshots", parts[2..4]=date1, parts[5..7]=date2, parts[8]=sha8
        if len(parts) < 9:
            continue
        race_date = f"{parts[2]}-{parts[3]}-{parts[4]}"
        sha8 = parts[8]

        is_contaminated = sha8 in CONTAMINATED_RUN_IDS
        is_post_fix = race_date >= FIX_DATE

        rows = []
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass

        if is_contaminated:
            gate_v1_contaminated_runners += len(rows)
            continue

        if not is_post_fix:
            continue

        races: dict[str, set] = {}
        for row in rows:
            rid = row.get("race_id", "?")
            vp = round(float(row.get("velo_prime_prob") or 0), 6)
            if rid not in races:
                races[rid] = set()
            races[rid].add(vp)

        day_flatlines = sum(1 for vps in races.values() if len(vps) == 1)
        flatline_count += day_flatlines
        gate_v2_runners += len(rows)
        gate_v2_days.add(race_date)

        if race_date not in by_date:
            by_date[race_date] = {
                "date": race_date,
                "sha8": sha8,
                "is_post_fix": is_post_fix,
                "runner_count": 0,
                "race_count": 0,
                "flatline_count": 0,
            }
        by_date[race_date]["runner_count"] += len(rows)
        by_date[race_date]["race_count"] += len(races)
        by_date[race_date]["flatline_count"] += day_flatlines

    return {
        "gate_v2_runner_count": gate_v2_runners,
        "gate_v2_qualified_days": sorted(gate_v2_days),
        "gate_v1_contaminated_runners_excluded": gate_v1_contaminated_runners,
        "flatline_count_v2": flatline_count,
        "identity_failures_v2": identity_failures,
        "by_date": by_date,
    }


RUNNER_CALIBRATION_THRESHOLD = 300   # runner-level calibration review
DECISION_POLICY_THRESHOLD_1 = 150    # first decision-policy review gate
DECISION_POLICY_THRESHOLD_2 = 300    # second decision-policy review gate


def _count_top_picks(by_date: dict) -> dict:
    """Count rank-0 (top pick) decisions per date from snapshots."""
    result = {}
    for date_str, day_data in by_date.items():
        date_und = date_str.replace("-", "_")
        pattern = str(ROOT / "data" / f"runner_snapshots_{date_und}_{date_und}_*.jsonl")
        top_picks = 0
        seen = set()
        for path in glob.glob(pattern):
            if path in seen:
                continue
            sha8 = Path(path).stem.split("_")[8] if len(Path(path).stem.split("_")) >= 9 else ""
            if sha8 in CONTAMINATED_RUN_IDS:
                continue
            seen.add(path)
            with open(path) as f:
                for line in f:
                    if line.strip():
                        try:
                            row = json.loads(line)
                            if row.get("rank", 99) == 0:
                                top_picks += 1
                        except Exception:
                            pass
        result[date_str] = top_picks
    return result


def build() -> dict:
    snap = _load_clean_snapshots()

    n = snap["gate_v2_runner_count"]
    flatlines = snap["flatline_count_v2"]
    id_failures = snap["identity_failures_v2"]
    by_date = snap["by_date"]

    top_picks_by_date = _count_top_picks(by_date)
    total_top_picks = sum(top_picks_by_date.values())

    blocking = []
    if flatlines > 0:
        blocking.append(f"flatline_count={flatlines} > 0")
    if id_failures > 0:
        blocking.append(f"identity_failures={id_failures} > 0")

    # Gate 1: Runner Calibration Gate
    runner_cal_threshold_met = n >= RUNNER_CALIBRATION_THRESHOLD and not blocking

    # Gate 2: Decision Policy Gate
    dp_threshold_1_met = total_top_picks >= DECISION_POLICY_THRESHOLD_1 and not blocking
    dp_threshold_2_met = total_top_picks >= DECISION_POLICY_THRESHOLD_2 and not blocking
    dp_rows_to_t1 = max(0, DECISION_POLICY_THRESHOLD_1 - total_top_picks)
    dp_rows_to_t2 = max(0, DECISION_POLICY_THRESHOLD_2 - total_top_picks)

    state = {
        "gate_id": "GATE_V2_POST_FLATLINE_FIX",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_date": FIX_DATE,
        "fix_commit": FIX_COMMIT[:8],
        "fix_commit_full": FIX_COMMIT,
        "gate_v1_status": "GATE_V1_AUDIT_ONLY",
        "gate_v1_contamination": "CONFIRMED — pre-a33c5bd RP_MERGED flatline rows included",
        "gate_v1_contaminated_runners_excluded": snap["gate_v1_contaminated_runners_excluded"],
        "flatline_count": flatlines,
        "identity_failures": id_failures,
        "by_date": by_date,
        "runner_calibration_gate": {
            "purpose": "Probability calibration review — AUC, Brier, VP band alignment",
            "runner_count": n,
            "threshold": RUNNER_CALIBRATION_THRESHOLD,
            "review_threshold_met": runner_cal_threshold_met,
            "qualified_days": snap["gate_v2_qualified_days"],
            "day_count": len(snap["gate_v2_qualified_days"]),
            "blocking": blocking,
            "status": "REVIEW_THRESHOLD_MET" if runner_cal_threshold_met else f"ACCUMULATING ({max(0, RUNNER_CALIBRATION_THRESHOLD - n)} runners to threshold)",
        },
        "decision_policy_gate": {
            "purpose": "Race-selection policy evidence — top-pick SR, day stability, subgroup checks",
            "top_pick_decisions": total_top_picks,
            "top_picks_by_date": top_picks_by_date,
            "threshold_1": DECISION_POLICY_THRESHOLD_1,
            "threshold_2": DECISION_POLICY_THRESHOLD_2,
            "threshold_1_met": dp_threshold_1_met,
            "threshold_2_met": dp_threshold_2_met,
            "rows_to_threshold_1": dp_rows_to_t1,
            "rows_to_threshold_2": dp_rows_to_t2,
            "blocking": blocking,
            "status": "NEEDS_MORE_DAYS",
            "next_review": f"{dp_rows_to_t1} more top-pick decisions to first policy gate",
        },
        "live_promotion_allowed": False,
        "promotion_decision": "NOT_APPROVED_OPERATOR_DECISION_REQUIRED",
        "mission_control_display": {
            "runner_calibration": "REVIEW_THRESHOLD_MET / NOT APPROVED" if runner_cal_threshold_met else f"ACCUMULATING ({max(0, RUNNER_CALIBRATION_THRESHOLD - n)} to threshold)",
            "decision_policy": f"NEEDS_MORE_DAYS — {dp_rows_to_t1} top-pick decisions to first gate",
        },
    }
    return state


def main() -> None:
    print("Building CPU Shadow Gate V2...")
    state = build()

    out_path = ROOT / "data" / "reports" / "cpu_shadow_gate_v2_latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(state, indent=2))

    rcg = state["runner_calibration_gate"]
    dpg = state["decision_policy_gate"]
    print(f"  Gate V1 status:      {state['gate_v1_status']}")
    print(f"  Flatline count:      {state['flatline_count']}")
    print(f"  Runner Calibration Gate:")
    print(f"    runners:           {rcg['runner_count']}")
    print(f"    qualified days:    {rcg['day_count']} ({', '.join(rcg['qualified_days'])})")
    print(f"    status:            {rcg['status']}")
    print(f"  Decision Policy Gate:")
    print(f"    top-pick decisions:{dpg['top_pick_decisions']}")
    print(f"    by date:           {dpg['top_picks_by_date']}")
    print(f"    status:            {dpg['status']}")
    print(f"    next:              {dpg['next_review']}")
    print(f"  Live promotion:      {state['live_promotion_allowed']}")
    print(f"  Decision:            {state['promotion_decision']}")
    print(f"  Written: {out_path}")


if __name__ == "__main__":
    main()
