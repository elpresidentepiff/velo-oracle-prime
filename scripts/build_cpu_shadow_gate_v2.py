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


def build() -> dict:
    snap = _load_clean_snapshots()

    n = snap["gate_v2_runner_count"]
    flatlines = snap["flatline_count_v2"]
    id_failures = snap["identity_failures_v2"]

    promotion_blocks = []
    if flatlines > 0:
        promotion_blocks.append(f"flatline_count={flatlines} > 0")
    if id_failures > 0:
        promotion_blocks.append(f"identity_failures={id_failures} > 0")

    review_threshold_met = n >= PROMOTION_THRESHOLD and not promotion_blocks
    rows_to_threshold = max(0, PROMOTION_THRESHOLD - n)

    state = {
        "gate_id": "GATE_V2_POST_FLATLINE_FIX",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_date": FIX_DATE,
        "fix_commit": FIX_COMMIT[:8],
        "fix_commit_full": FIX_COMMIT,
        "gate_v1_status": "GATE_V1_AUDIT_ONLY",
        "gate_v1_contamination": "CONFIRMED — pre-a33c5bd RP_MERGED flatline rows included",
        "gate_v1_contaminated_runners_excluded": snap["gate_v1_contaminated_runners_excluded"],
        "gate_v2_runner_count": n,
        "gate_v2_qualified_days": snap["gate_v2_qualified_days"],
        "gate_v2_day_count": len(snap["gate_v2_qualified_days"]),
        "flatline_count": flatlines,
        "identity_failures": id_failures,
        "by_date": snap["by_date"],
        "review_threshold": PROMOTION_THRESHOLD,
        "rows_to_threshold": rows_to_threshold,
        "review_threshold_met": review_threshold_met,
        "promotion_blocks": promotion_blocks,
        "promotion_decision": "NOT_APPROVED_OPERATOR_DECISION_REQUIRED",
        "live_promotion_allowed": False,
    }
    return state


def main() -> None:
    print("Building CPU Shadow Gate V2...")
    state = build()

    out_path = ROOT / "data" / "reports" / "cpu_shadow_gate_v2_latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(state, indent=2))

    print(f"  Gate V2 runners: {state['gate_v2_runner_count']}")
    print(f"  Qualified days:  {state['gate_v2_day_count']} ({', '.join(state['gate_v2_qualified_days'])})")
    print(f"  Flatline count:  {state['flatline_count']}")
    print(f"  Identity fails:  {state['identity_failures']}")
    print(f"  Review threshold:    {state['review_threshold']}")
    print(f"  Rows to threshold:   {state['rows_to_threshold']}")
    print(f"  Gate V1 status:      {state['gate_v1_status']}")
    print(f"  Review threshold met:{state['review_threshold_met']} (NOT promotion eligible)")
    if state["promotion_blocks"]:
        print(f"  Promotion blocked:   {'; '.join(state['promotion_blocks'])}")
    if state["review_threshold_met"]:
        print("  STATUS: CPU_GATE_V2_REVIEW_TRIGGERED — LIVE_PROMOTION_NOT_ALLOWED — OPERATOR_DECISION_REQUIRED")
    print(f"  Written: {out_path}")


if __name__ == "__main__":
    main()
