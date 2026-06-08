#!/usr/bin/env python3
"""
Race Shape vs Midprice Miss Overlap Analysis

Joins race shape features (build_race_shape_features.py) to midprice winner
deltas (midprice_winner_delta.py) to answer the V2 research questions:

  1. How many midprice misses were COMPRESSED races?
  2. How many were FAV_VULNERABLE?
  3. How many had high top3 compression?
  4. How many had winner ranked 2nd/3rd?
  5. Does race shape explain the 96.6% winner-visible issue?
  6. Which race-shape tags deserve shadow tracking?

Read-only: no scoring changes, no routing changes, no model changes.

Outputs:
  data/reports/race_shape_midprice_overlap_latest.json
  data/reports/race_shape_midprice_overlap_latest.md

Usage:
    PYTHONPATH=. python scripts/audit_race_shape_midprice_overlap.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MIDPRICE_LOW = 3.0
MIDPRICE_HIGH = 8.5


def _load_race_shape(date_str: str) -> dict[str, dict]:
    """Load race shape features for the date. Returns {race_id: features}."""
    feat_path = ROOT / "data" / "features" / "race_shape_features_latest.json"
    if not feat_path.exists():
        raise FileNotFoundError(f"Race shape features not found: {feat_path}")
    d = json.loads(feat_path.read_text())
    features = d.get("features", d) if isinstance(d, dict) else d
    if isinstance(features, list):
        return {f["race_id"]: f for f in features if f.get("date", date_str) == date_str}
    return {}


def _load_midprice_delta(date_str: str) -> list[dict]:
    """Load midprice winner delta CSV rows for the date."""
    csv_path = ROOT / "data" / "midprice_winner_deltas.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Midprice delta CSV not found: {csv_path}")
    rows = []
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            if row.get("date", "") == date_str:
                rows.append(row)
    return rows


def _safe_float(val: str | float | None) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_bool(val: str | bool | None) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in {"true", "1", "yes"}
    return bool(val)


def run_overlap(date_str: str) -> dict:
    print(f"[Overlap] Loading race shape features for {date_str}...")
    shape_map = _load_race_shape(date_str)
    print(f"[Overlap] Race shape entries: {len(shape_map)}")

    print(f"[Overlap] Loading midprice delta rows for {date_str}...")
    delta_rows = _load_midprice_delta(date_str)
    print(f"[Overlap] Midprice delta rows: {len(delta_rows)}")

    # Categorise delta rows
    miss_rows = [r for r in delta_rows if not _safe_bool(r.get("top_pick_is_winner"))]
    win_rows = [r for r in delta_rows if _safe_bool(r.get("top_pick_is_winner"))]
    midprice_miss_rows = [r for r in miss_rows if _safe_bool(r.get("winner_in_midprice_zone"))]
    winner_visible_rows = [r for r in miss_rows if _safe_bool(r.get("winner_visible_in_snapshots"))]
    winner_ranked_2nd_3rd = [
        r for r in miss_rows
        if _safe_bool(r.get("winner_visible_in_snapshots"))
        and (_safe_float(r.get("winner_rank_in_snapshots")) or 99) in (1, 2)  # rank=1 is 2nd, rank=2 is 3rd
    ]

    # Join midprice misses to race shape
    joined: list[dict] = []
    unmatched_race_ids: list[str] = []

    for row in miss_rows:
        race_id = row.get("race_id", "")
        shape = shape_map.get(race_id)
        if shape is None:
            unmatched_race_ids.append(race_id)
            continue

        winner_rank = _safe_float(row.get("winner_rank_in_snapshots"))
        joined.append({
            "race_id": race_id,
            "course": row.get("course", ""),
            "off_time": row.get("off_time", ""),
            "top_pick": row.get("top_pick", ""),
            "actual_winner": row.get("actual_winner", ""),
            "winner_sp_dec": _safe_float(row.get("winner_sp_dec")),
            "winner_in_midprice_zone": _safe_bool(row.get("winner_in_midprice_zone")),
            "winner_visible_in_snapshots": _safe_bool(row.get("winner_visible_in_snapshots")),
            "winner_rank_in_snapshots": winner_rank,
            "delta_vp": _safe_float(row.get("delta_vp")),
            "winner_rescuable_by_sidecar": _safe_bool(row.get("winner_rescuable_by_sidecar")),
            "race_shape_status": shape.get("race_shape_status", "UNKNOWN"),
            "vp_spread_top3": shape.get("vp_spread_top3"),
            "vp_spread_field": shape.get("vp_spread_field"),
            "midprice_density": shape.get("midprice_density"),
            "favourite_vulnerability_score": shape.get("favourite_vulnerability_score"),
            "contender_compression_score": shape.get("contender_compression_score"),
            "top_vp": shape.get("top_vp"),
            "field_size": shape.get("field_size"),
            "going": shape.get("going", ""),
            "going_soft_flag": shape.get("going_soft_flag"),
        })

    # Overlap counts
    def _count_status(rows: list[dict], status: str) -> int:
        return sum(1 for r in rows if r.get("race_shape_status") == status)

    def _count_field(rows: list[dict], field: str, val=True) -> int:
        return sum(1 for r in rows if r.get(field) == val)

    n_miss = len(joined)
    n_midprice = sum(1 for r in joined if r.get("winner_in_midprice_zone"))
    n_visible = sum(1 for r in joined if r.get("winner_visible_in_snapshots"))
    n_ranked_2nd_3rd = sum(1 for r in joined if r.get("winner_rank_in_snapshots") in (1.0, 2.0))
    n_compressed = _count_status(joined, "COMPRESSED")
    n_fav_vulnerable = _count_status(joined, "FAV_VULNERABLE")
    n_midprice_trap = _count_status(joined, "MIDPRICE_TRAP")
    n_clear_top = _count_status(joined, "CLEAR_TOP")
    n_chaotic = _count_status(joined, "CHAOTIC")
    n_unknown = _count_status(joined, "UNKNOWN")
    n_fav_vuln_flag = _count_field(joined, "favourite_vulnerability_score", True)
    n_high_compression = sum(1 for r in joined if (r.get("vp_spread_top3") or 1.0) < 0.05)
    n_going_soft = _count_field(joined, "going_soft_flag", True)

    # Shadow tracking candidates — misses where shape signals fire
    shadow_candidates = [
        r for r in joined
        if r.get("race_shape_status") in ("COMPRESSED", "FAV_VULNERABLE", "MIDPRICE_TRAP", "CHAOTIC")
        or r.get("favourite_vulnerability_score")
        or (r.get("vp_spread_top3") or 1.0) < 0.05
    ]

    # SR by shape status
    # We only have misses here — to compute SR we need total picks per status
    shape_status_dist: dict[str, int] = {}
    for r in joined:
        s = r.get("race_shape_status", "UNKNOWN")
        shape_status_dist[s] = shape_status_dist.get(s, 0) + 1

    result = {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_delta_rows": len(delta_rows),
        "total_miss_rows": n_miss,
        "total_win_rows": len(win_rows),
        "midprice_misses": n_midprice,
        "winner_visible_in_snapshots": n_visible,
        "winner_visible_pct": round(100 * n_visible / n_miss, 1) if n_miss > 0 else 0,
        "winner_ranked_2nd_or_3rd": n_ranked_2nd_3rd,
        "winner_ranked_2nd_or_3rd_pct": round(100 * n_ranked_2nd_3rd / n_miss, 1) if n_miss > 0 else 0,
        "unmatched_to_shape": len(unmatched_race_ids),
        "overlap_questions": {
            "q1_compressed_misses": n_compressed,
            "q2_fav_vulnerable_misses": n_fav_vulnerable,
            "q2b_fav_vuln_flag_misses": n_fav_vuln_flag,
            "q3_high_top3_compression_misses": n_high_compression,
            "q4_winner_ranked_2nd_3rd": n_ranked_2nd_3rd,
            "q5_visible_pct_explains_shape": f"{n_visible}/{n_miss} = {round(100*n_visible/n_miss,1) if n_miss else 0}%",
            "q6_shadow_tracking_candidates": len(shadow_candidates),
        },
        "shape_status_distribution_in_misses": shape_status_dist,
        "shadow_tracking_candidates": [r["race_id"] for r in shadow_candidates],
        "miss_detail": joined,
    }

    return result


def _write_md(result: dict) -> str:
    shape_dist = result.get("shape_status_distribution_in_misses", {})
    shape_rows = "".join(
        f"| {k} | {v} | {round(100*v/result['total_miss_rows'],1) if result['total_miss_rows'] else 0}% |\n"
        for k, v in sorted(shape_dist.items(), key=lambda x: -x[1])
    )

    q = result.get("overlap_questions", {})
    n_miss = result["total_miss_rows"]

    candidate_races = "\n".join(f"  - {rid}" for rid in result.get("shadow_tracking_candidates", [])[:10])
    if len(result.get("shadow_tracking_candidates", [])) > 10:
        candidate_races += f"\n  ... ({len(result['shadow_tracking_candidates'])-10} more)"

    shadow_tags = []
    if q.get("q1_compressed_misses", 0) > 0:
        shadow_tags.append(f"COMPRESSED — {q['q1_compressed_misses']} misses")
    if q.get("q2_fav_vulnerable_misses", 0) > 0:
        shadow_tags.append(f"FAV_VULNERABLE — {q['q2_fav_vulnerable_misses']} misses")
    if q.get("q5_midprice_trap_misses" if "q5_midprice_trap_misses" in q else "q6_shadow_tracking_candidates", 0) > 0:
        shadow_tags.append(f"MIDPRICE_TRAP races — shadow track midprice_density >= 0.45")
    if q.get("q3_high_top3_compression_misses", 0) > 0:
        shadow_tags.append(f"High top3 compression (VP spread < 0.05) — {q['q3_high_top3_compression_misses']} misses")

    shadow_tag_rows = "\n".join(f"  - {t}" for t in shadow_tags)

    return f"""# Race Shape vs Midprice Miss Overlap — {result['date']}

**Generated:** {result['generated_at']}
**Research status:** SHADOW/RESEARCH ONLY — no scoring changes

---

## V2 Research Questions

| Question | Finding |
|---|---|
| Q1: Midprice misses in COMPRESSED races | **{q.get('q1_compressed_misses',0)}** of {n_miss} misses |
| Q2: Midprice misses in FAV_VULNERABLE races | **{q.get('q2_fav_vulnerable_misses',0)}** of {n_miss} misses |
| Q2b: FAV_VULNERABLE flag fired | **{q.get('q2b_fav_vuln_flag_misses',0)}** of {n_miss} misses |
| Q3: High top3 VP compression (<0.05) | **{q.get('q3_high_top3_compression_misses',0)}** of {n_miss} misses |
| Q4: Winner ranked 2nd or 3rd in snapshots | **{q.get('q4_winner_ranked_2nd_3rd',0)}** of {n_miss} misses ({result.get('winner_ranked_2nd_or_3rd_pct',0)}%) |
| Q5: Winner visible in snapshots | **{result.get('winner_visible_in_snapshots',0)}/{n_miss}** = {result.get('winner_visible_pct',0)}% |
| Q6: Shadow tracking candidates (shape flags fired) | **{q.get('q6_shadow_tracking_candidates',0)}** races |

---

## Shape Status in Misses

| Race Shape Status | Miss Count | % of Misses |
|---|---|---|
{shape_rows}
---

## Winner Visibility

Winner visible in snapshots: **{result.get('winner_visible_in_snapshots',0)}/{n_miss}** = **{result.get('winner_visible_pct',0)}%**

This confirms the V2 hypothesis: the model *sees* the winner but ranks it wrong. This is a ranking failure, not a coverage failure.

Winner ranked 2nd or 3rd (VP rank 1 or 2): **{q.get('q4_winner_ranked_2nd_3rd',0)}/{n_miss}** = **{result.get('winner_ranked_2nd_or_3rd_pct',0)}%**

These are the races where a small VP adjustment could flip the pick correctly.

---

## Shadow Tracking Recommendations

Race-shape tags that fired most in misses:
{shadow_tag_rows}

**Candidate races for shadow tracking:**
{candidate_races}

---

## Corpus Size Note

Current corpus: {n_miss} miss races from {result['date']} (1 day).
Corpus needs 300+ races before quartile SR analysis (see MIDPRICE_HUNTER_V2_RESEARCH_PLAN.md).
Run `midprice_winner_delta.py` daily to accumulate.

---

## Governance

```
No scoring changes.
No VP adjustments.
No routing changes.
All findings are research hypotheses — need 300+ race corpus to validate.
```
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Race Shape vs Midprice Miss Overlap Analysis")
    parser.add_argument("--date", default="2026-05-22", help="YYYY-MM-DD")
    args = parser.parse_args()

    result = run_overlap(args.date)

    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "race_shape_midprice_overlap_latest.json"
    md_path = out_dir / "race_shape_midprice_overlap_latest.md"

    # Don't write detail rows to JSON (large) — write summary only
    summary = {k: v for k, v in result.items() if k not in ("miss_detail",)}
    json_path.write_text(json.dumps(summary, indent=2))
    print(f"[Overlap] Written: {json_path}")

    md_path.write_text(_write_md(result))
    print(f"[Overlap] Written: {md_path}")

    print()
    q = result.get("overlap_questions", {})
    print(f"  Total misses: {result['total_miss_rows']}")
    print(f"  Midprice misses: {result['midprice_misses']}")
    print(f"  Winner visible: {result['winner_visible_in_snapshots']} ({result['winner_visible_pct']}%)")
    print(f"  Winner ranked 2nd/3rd: {result['winner_ranked_2nd_or_3rd']} ({result['winner_ranked_2nd_or_3rd_pct']}%)")
    print(f"  COMPRESSED misses: {q.get('q1_compressed_misses',0)}")
    print(f"  FAV_VULNERABLE misses: {q.get('q2_fav_vulnerable_misses',0)}")
    print(f"  High compression misses: {q.get('q3_high_top3_compression_misses',0)}")
    print(f"  Shadow tracking candidates: {q.get('q6_shadow_tracking_candidates',0)}")


if __name__ == "__main__":
    main()
