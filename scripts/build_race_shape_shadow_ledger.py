#!/usr/bin/env python3
"""
Race Shape Shadow Ledger V1

Builds an append-only shadow ledger joining race shape features to sigma outcomes.
Tracks per race:
  - race shape classification and key features
  - VELO top pick result (win/miss)
  - whether race shape would have warned
  - winner visibility and rank

Shadow ledger only — no scoring integration, no model changes, no routing.
Feeds Midprice Hunter V2 research corpus (MIDPRICE_HUNTER_V2_RESEARCH_PLAN.md).

Outputs:
  data/reports/race_shape_shadow_ledger_latest.json
  data/reports/race_shape_shadow_ledger_latest.md

Usage:
    PYTHONPATH=. python scripts/build_race_shape_shadow_ledger.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LEDGER_PATH = ROOT / "data" / "reports" / "race_shape_shadow_ledger_latest.json"
MIDPRICE_LOW = 3.0
MIDPRICE_HIGH = 8.5

# Shape statuses that constitute a "warning" for midprice analysis
SHAPE_WARN_STATUSES = {"COMPRESSED", "FAV_VULNERABLE", "MIDPRICE_TRAP", "CHAOTIC"}


def _load_race_shape(date_str: str) -> dict[str, dict]:
    feat_path = ROOT / "data" / "features" / "race_shape_features_latest.json"
    if not feat_path.exists():
        return {}
    d = json.loads(feat_path.read_text())
    features = d.get("features", d) if isinstance(d, dict) else d
    if isinstance(features, list):
        return {f["race_id"]: f for f in features if f.get("date", date_str) == date_str}
    return {}


def _load_midprice_delta(date_str: str) -> dict[str, dict]:
    csv_path = ROOT / "data" / "midprice_winner_deltas.csv"
    if not csv_path.exists():
        return {}
    result = {}
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            if row.get("date", "") == date_str:
                result[row["race_id"]] = row
    return result


def _safe_float(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in {"true", "1", "yes"}
    return bool(val)


def _load_sigma_outcomes(date_str: str) -> dict[str, str]:
    """Load top-pick outcomes from sigma_results."""
    sa_path = ROOT / "data" / "sigma_results" / f"sigma_results_{date_str.replace('-','_')}.json"
    if not sa_path.exists():
        return {}
    try:
        # Load verdicts and results to determine per-race outcomes
        date_und = date_str.replace("-", "_")
        vd_path = ROOT / "data" / f"velo_prime_verdicts_{date_und}.json"
        res_path = ROOT / "data" / f"results_{date_und}.json"
        if not vd_path.exists() or not res_path.exists():
            return {}
        verdicts = json.loads(vd_path.read_text())
        results_data = json.loads(res_path.read_text())
        results = results_data.get("results", []) if isinstance(results_data, dict) else results_data
        result_map = {r["race_id"]: r for r in results}

        outcomes: dict[str, str] = {}
        for v in verdicts:
            race_id = v["race_id"]
            top = v.get("top", {})
            top_pick = (top.get("horse") or "").strip().lower()
            res = result_map.get(race_id)
            if not res:
                outcomes[race_id] = "NO_RESULT"
                continue
            winner = next(
                (r for r in res.get("runners", []) if str(r.get("position", "")) == "1"),
                None
            )
            if not winner:
                outcomes[race_id] = "NO_WINNER"
                continue
            winner_name = (winner.get("horse") or "").strip().lower()
            outcomes[race_id] = "WIN" if winner_name == top_pick else "MISS"
        return outcomes
    except Exception:
        return {}


def build_ledger_rows(date_str: str) -> list[dict]:
    shape_map = _load_race_shape(date_str)
    delta_map = _load_midprice_delta(date_str)
    outcomes = _load_sigma_outcomes(date_str)

    all_race_ids = set(shape_map.keys()) | set(delta_map.keys())
    rows: list[dict] = []

    for race_id in sorted(all_race_ids):
        shape = shape_map.get(race_id, {})
        delta = delta_map.get(race_id, {})

        outcome = outcomes.get(race_id) or (
            "WIN" if _safe_bool(delta.get("top_pick_is_winner")) else
            "MISS" if delta else "UNKNOWN"
        )

        top_pick = delta.get("top_pick") or shape.get("top_pick_name", "")
        actual_winner = delta.get("actual_winner", "")
        winner_sp = _safe_float(delta.get("winner_sp_dec")) or shape.get("winner_sp")
        winner_in_midprice = (
            _safe_bool(delta.get("winner_in_midprice_zone"))
            if delta
            else (MIDPRICE_LOW <= winner_sp <= MIDPRICE_HIGH if winner_sp else None)
        )
        winner_rank = _safe_float(delta.get("winner_rank_in_snapshots"))
        winner_visible = _safe_bool(delta.get("winner_visible_in_snapshots")) if delta else None
        winner_ranked_2_or_3 = winner_rank in (1.0, 2.0) if winner_rank is not None else None

        race_shape_status = shape.get("race_shape_status", "UNKNOWN")
        shape_would_warn = race_shape_status in SHAPE_WARN_STATUSES or bool(shape.get("favourite_vulnerability_score"))

        row: dict = {
            "date": date_str,
            "race_id": race_id,
            "course": shape.get("course") or delta.get("course", ""),
            "off_time": shape.get("off_time") or delta.get("off_time", ""),
            "top_pick": top_pick,
            "actual_winner": actual_winner,
            "outcome": outcome,
            "race_shape_status": race_shape_status,
            "contender_compression_score": shape.get("contender_compression_score"),
            "favourite_vulnerability_score": shape.get("favourite_vulnerability_score"),
            "market_concentration_score": shape.get("market_concentration_score"),
            "midprice_density": shape.get("midprice_density"),
            "vp_spread_top3": shape.get("vp_spread_top3"),
            "vp_spread_field": shape.get("vp_spread_field"),
            "field_size": shape.get("field_size"),
            "going": shape.get("going", ""),
            "going_soft_flag": shape.get("going_soft_flag"),
            "winner_rank": winner_rank,
            "winner_visible": winner_visible,
            "winner_ranked_2_or_3": winner_ranked_2_or_3,
            "winner_in_midprice": winner_in_midprice,
            "winner_sp": winner_sp,
            "top_pick_vp": _safe_float(delta.get("top_vp")) or shape.get("top_vp"),
            "winner_vp": _safe_float(delta.get("winner_vp")),
            "delta_vp": _safe_float(delta.get("delta_vp")),
            "shape_would_warn": shape_would_warn,
        }
        rows.append(row)

    return rows


def _compute_summary(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {}

    wins = sum(1 for r in rows if r.get("outcome") == "WIN")
    misses = sum(1 for r in rows if r.get("outcome") == "MISS")
    shape_warned = sum(1 for r in rows if r.get("shape_would_warn"))
    warned_wins = sum(1 for r in rows if r.get("shape_would_warn") and r.get("outcome") == "WIN")
    warned_misses = sum(1 for r in rows if r.get("shape_would_warn") and r.get("outcome") == "MISS")
    miss_rows = [r for r in rows if r.get("outcome") == "MISS"]
    visible = sum(1 for r in miss_rows if r.get("winner_visible"))
    ranked_2_3 = sum(1 for r in miss_rows if r.get("winner_ranked_2_or_3"))
    midprice_wins = sum(1 for r in rows if r.get("winner_in_midprice") and r.get("outcome") == "MISS")

    shape_status_dist: dict[str, int] = {}
    for r in rows:
        s = r.get("race_shape_status", "UNKNOWN")
        shape_status_dist[s] = shape_status_dist.get(s, 0) + 1

    sr_warned = round(warned_wins / shape_warned, 4) if shape_warned > 0 else None
    sr_not_warned = round((wins - warned_wins) / (n - shape_warned), 4) if n > shape_warned else None

    return {
        "total_races": n,
        "wins": wins,
        "misses": misses,
        "sr": round(wins / n, 4) if n > 0 else None,
        "shape_warned_count": shape_warned,
        "warned_wins": warned_wins,
        "warned_misses": warned_misses,
        "sr_when_warned": sr_warned,
        "sr_when_not_warned": sr_not_warned,
        "winner_visible": visible,
        "winner_visible_pct": round(100 * visible / misses, 1) if misses > 0 else None,
        "winner_ranked_2_or_3": ranked_2_3,
        "winner_ranked_2_3_pct": round(100 * ranked_2_3 / misses, 1) if misses > 0 else None,
        "midprice_misses": midprice_wins,
        "shape_status_distribution": shape_status_dist,
    }


def _write_md(ledger: dict) -> str:
    s = ledger.get("summary", {})
    sd = s.get("shape_status_distribution", {})
    status_rows = "".join(
        f"| {k} | {v} |\n"
        for k, v in sorted(sd.items(), key=lambda x: -x[1])
    )

    rows = ledger.get("rows", [])
    race_rows = ""
    for r in rows:
        vp3 = r.get("vp_spread_top3")
        race_rows += (
            f"| {r['race_id']} | {r.get('race_shape_status','?')} | "
            f"{r.get('outcome','?')} | "
            f"{f'{vp3:.4f}' if vp3 is not None else 'N/A'} | "
            f"{r.get('midprice_density',0):.3f} | "
            f"{'WARN' if r.get('shape_would_warn') else '-'} | "
            f"{r.get('winner_rank','?')} | "
            f"{r.get('winner_sp','?')} |\n"
        )

    warn_note = ""
    if s.get("sr_when_warned") is not None and s.get("sr_when_not_warned") is not None:
        warn_note = (
            f"\nWhen shape warns: SR={s['sr_when_warned']:.1%} ({s['warned_wins']}/{s['shape_warned_count']})\n"
            f"When shape silent: SR={s['sr_when_not_warned']:.1%}\n"
        )

    return f"""# Race Shape Shadow Ledger — {ledger.get('date','?')}

**Generated:** {ledger.get('generated_at','?')}
**Total races:** {s.get('total_races',0)}
**Status:** SHADOW/RESEARCH ONLY — no scoring integration

---

## Summary

| Metric | Value |
|---|---|
| Total races | {s.get('total_races',0)} |
| Wins | {s.get('wins',0)} |
| Misses | {s.get('misses',0)} |
| SR | {s.get('sr',0):.1%} |
| Shape warned | {s.get('shape_warned_count',0)} |
| SR when warned | {f"{s['sr_when_warned']:.1%}" if s.get('sr_when_warned') is not None else 'N/A'} |
| SR when silent | {f"{s['sr_when_not_warned']:.1%}" if s.get('sr_when_not_warned') is not None else 'N/A'} |
| Winner visible (of misses) | {s.get('winner_visible',0)}/{s.get('misses',0)} = {s.get('winner_visible_pct','N/A')}% |
| Winner ranked 2nd/3rd | {s.get('winner_ranked_2_or_3',0)}/{s.get('misses',0)} = {s.get('winner_ranked_2_3_pct','N/A')}% |
| Midprice misses | {s.get('midprice_misses',0)} |
{warn_note}
---

## Shape Status Distribution

| Status | Count |
|---|---|
{status_rows}
---

## Per-Race Ledger

| Race ID | Shape Status | Outcome | VP Spread Top3 | Midprice Density | Warn | Winner Rank | Winner SP |
|---|---|---|---|---|---|---|---|
{race_rows}
---

## Governance

```
Shadow ledger only.
No scoring changes.
No VP adjustments.
No routing changes.
Feeds MIDPRICE_HUNTER_V2_RESEARCH_PLAN.md corpus (target: 300+ races).
```
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Race Shape Shadow Ledger V1")
    parser.add_argument("--date", default="2026-05-22", help="YYYY-MM-DD")
    args = parser.parse_args()

    print(f"[Ledger] Building race shape shadow ledger for {args.date}...")
    rows = build_ledger_rows(args.date)

    if not rows:
        print("[WARN] No rows computed — run build_race_shape_features.py and midprice_winner_delta.py first")
        sys.exit(1)

    summary = _compute_summary(rows)
    ledger = {
        "date": args.date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "rows": rows,
    }

    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "race_shape_shadow_ledger_latest.json"
    md_path = out_dir / "race_shape_shadow_ledger_latest.md"

    json_path.write_text(json.dumps(ledger, indent=2))
    print(f"[Ledger] Written: {json_path}")

    md_path.write_text(_write_md(ledger))
    print(f"[Ledger] Written: {md_path}")

    print()
    print(f"  races: {summary.get('total_races',0)}")
    print(f"  wins: {summary.get('wins',0)}  misses: {summary.get('misses',0)}")
    sr = summary.get('sr')
    print(f"  sr: {sr:.1%}" if sr is not None else "  sr: N/A")
    print(f"  shape_warned: {summary.get('shape_warned_count',0)}")
    sw = summary.get('sr_when_warned')
    print(f"  sr_when_warned: {sw:.1%}" if sw is not None else "  sr_when_warned: N/A")
    sn = summary.get('sr_when_not_warned')
    print(f"  sr_when_not_warned: {sn:.1%}" if sn is not None else "  sr_when_not_warned: N/A")
    print(f"  winner_visible: {summary.get('winner_visible',0)}/{summary.get('misses',0)} ({summary.get('winner_visible_pct','N/A')}%)")
    print(f"  winner_ranked_2_or_3: {summary.get('winner_ranked_2_or_3',0)}/{summary.get('misses',0)}")


if __name__ == "__main__":
    main()
