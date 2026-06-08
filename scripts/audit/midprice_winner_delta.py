#!/usr/bin/env python3
"""
Mid-price top-vs-winner sidecar delta audit.

For each race where VELO top pick != actual winner, compute the sidecar score
deltas to understand whether sidecar signals (MDS, improvement, place_prob)
could have rescued the winner.

Inputs:
  - data/runner_snapshots_{date_und}_{date_und}_{sha8}_{epoch}.jsonl
  - data/results_{date_und}.json (actual race results from SL scraper)

Outputs:
  - data/midprice_winner_deltas.csv
  - data/reports/midprice_winner_delta_latest.json
  - data/reports/midprice_winner_delta_latest.md

Read-only: no scoring changes, no routing changes, no execution changes.

Usage:
    PYTHONPATH=. python scripts/audit/midprice_winner_delta.py
    PYTHONPATH=. python scripts/audit/midprice_winner_delta.py --date 2026-05-21
"""

import argparse
import csv
import glob
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CONTAMINATED_RUN_IDS = {"32cc27f9", "847964a6"}
FIX_DATE = "2026-05-21"

SIDECAR_FIELDS = [
    "velo_prime_prob", "sqpe_v17_prob", "market_deception_score",
    "improvement_score", "place_prob", "longshot_prob", "release_day_prob",
    "comment_intel_score", "mark_compression_score",
]

RESCUE_THRESHOLD = {
    "market_deception_score": 0.5,
    "improvement_score": 0.40,
    "place_prob": 0.80,
}


def _extract_sha8(run_id: str) -> str:
    parts = run_id.split("_")
    return parts[3] if len(parts) >= 4 else run_id[:8]


def _load_snapshot_races(date_str: str) -> dict[str, dict]:
    """Return {race_id: {'top': row, 'all': [rows]}} for clean snapshots on date."""
    date_und = date_str.replace("-", "_")
    patterns = [
        str(ROOT / "data" / f"runner_snapshots_{date_str}*.jsonl"),
        str(ROOT / "data" / f"runner_snapshots_{date_und}*.jsonl"),
    ]
    seen_paths: set = set()
    races: dict[str, list] = defaultdict(list)

    for pat in patterns:
        for path in glob.glob(pat):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            sha8 = Path(path).stem.split("_")[8] if len(Path(path).stem.split("_")) >= 9 else ""
            if sha8 in CONTAMINATED_RUN_IDS:
                continue
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                        races[row.get("race_id", "?")].append(row)
                    except Exception:
                        pass

    result = {}
    for race_id, rows in races.items():
        rows.sort(key=lambda r: r.get("rank", 99))
        top = next((r for r in rows if r.get("rank", 99) == 0), rows[0] if rows else None)
        if top:
            result[race_id] = {"top": top, "all": rows}
    return result


def _load_winners(date_str: str) -> dict[str, dict]:
    """Return {race_id: winner_row} from results JSON."""
    date_und = date_str.replace("-", "_")
    path = ROOT / "data" / f"results_{date_und}.json"
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text())
        result = {}
        for race in d.get("results", []):
            rid = race.get("race_id", "")
            runners = race.get("runners", [])
            winner = next((r for r in runners if str(r.get("position", "")) == "1"), None)
            if winner and rid:
                result[rid] = winner
        return result
    except Exception:
        return {}


def _find_runner_in_snapshots(horse_name: str, race_rows: list[dict]) -> dict | None:
    name_lower = horse_name.lower().replace(" ", "_")
    for row in race_rows:
        if row.get("horse", "").lower().replace(" ", "_") == name_lower:
            return row
        hid = row.get("horse_id", "")
        if hid.endswith(f"_{name_lower}"):
            return row
    return None


def _sidecar_rescue_check(winner_row: dict) -> tuple[bool, list[str]]:
    rescuers = []
    for field, threshold in RESCUE_THRESHOLD.items():
        val = winner_row.get(field, 0) or 0
        if float(val) >= threshold:
            rescuers.append(f"{field}={val:.3f}>={threshold}")
    return bool(rescuers), rescuers


def build_delta(dates: list[str]) -> list[dict]:
    rows = []
    for date_str in dates:
        snap_races = _load_snapshot_races(date_str)
        winners = _load_winners(date_str)

        for race_id, winner_data in winners.items():
            snap = snap_races.get(race_id)
            if not snap:
                continue

            top = snap["top"]
            top_name = top.get("horse", "")
            winner_name = winner_data.get("horse", "")
            winner_sp_dec = float(winner_data.get("sp_dec", 0) or 0)

            winner_snap = _find_runner_in_snapshots(winner_name, snap["all"])
            winner_visible = winner_snap is not None
            winner_rank = winner_snap.get("rank", -1) if winner_snap else -1

            is_top_pick_winner = top_name.lower().replace(" ", "_") == winner_name.lower().replace(" ", "_")
            midprice = 3.0 <= winner_sp_dec <= 8.5

            rescued, rescuers = _sidecar_rescue_check(winner_snap) if winner_snap else (False, [])

            router_reasons = top.get("router_reasons") or {}
            is_midprice_suppressed = (
                "MIDPRICE_SUPPRESS_TOP" in str(router_reasons) or
                top.get("assigned_product", "") == "MIDPRICE_SUPPRESS"
            )

            row = {
                "date": date_str,
                "race_id": race_id,
                "course": top.get("course", ""),
                "off_time": top.get("off_time", ""),
                "top_pick": top_name,
                "actual_winner": winner_name,
                "top_pick_is_winner": is_top_pick_winner,
                "winner_in_midprice_zone": midprice,
                "winner_visible_in_snapshots": winner_visible,
                "winner_rank_in_snapshots": winner_rank,
                "winner_sp_dec": winner_sp_dec,
                "top_vp": top.get("velo_prime_prob", ""),
                "winner_vp": winner_snap.get("velo_prime_prob", "") if winner_snap else "",
                "delta_vp": (
                    round(float(top.get("velo_prime_prob") or 0) - float(winner_snap.get("velo_prime_prob") or 0), 4)
                    if winner_snap else ""
                ),
                "top_mds": top.get("market_deception_score", ""),
                "winner_mds": winner_snap.get("market_deception_score", "") if winner_snap else "",
                "delta_mds": (
                    round(float(top.get("market_deception_score") or 0) - float(winner_snap.get("market_deception_score") or 0), 4)
                    if winner_snap else ""
                ),
                "top_improvement": top.get("improvement_score", ""),
                "winner_improvement": winner_snap.get("improvement_score", "") if winner_snap else "",
                "delta_improvement": (
                    round(float(top.get("improvement_score") or 0) - float(winner_snap.get("improvement_score") or 0), 4)
                    if winner_snap else ""
                ),
                "top_place_prob": top.get("place_prob", ""),
                "winner_place_prob": winner_snap.get("place_prob", "") if winner_snap else "",
                "delta_place_prob": (
                    round(float(top.get("place_prob") or 0) - float(winner_snap.get("place_prob") or 0), 4)
                    if winner_snap else ""
                ),
                "top_tier": top.get("decision_tier", ""),
                "winner_tier": winner_snap.get("decision_tier", "") if winner_snap else "",
                "shadow_action": top.get("assigned_product", ""),
                "top_pick_is_midprice_suppress": is_midprice_suppressed,
                "winner_rescuable_by_sidecar": rescued,
                "rescue_signals": "; ".join(rescuers),
            }
            rows.append(row)

    return rows


def write_outputs(rows: list[dict]) -> None:
    csv_path = ROOT / "data" / "midprice_winner_deltas.csv"
    reports_dir = ROOT / "data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "midprice_winner_delta_latest.json"
    md_path = reports_dir / "midprice_winner_delta_latest.md"

    if rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    total = len(rows)
    misses = [r for r in rows if not r["top_pick_is_winner"]]
    midprice_misses = [r for r in misses if r["winner_in_midprice_zone"]]
    rescued = [r for r in misses if r["winner_rescuable_by_sidecar"]]
    visible = [r for r in misses if r["winner_visible_in_snapshots"]]
    suppressed = [r for r in rows if r["top_pick_is_midprice_suppress"]]

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_races": total,
        "total_misses": len(misses),
        "midprice_zone_misses": len(midprice_misses),
        "winner_visible_in_snapshots": len(visible),
        "rescued_by_sidecar": len(rescued),
        "suppressed_top_picks": len(suppressed),
        "rescue_rate_pct": round(len(rescued) / len(misses) * 100, 1) if misses else 0,
        "midprice_miss_rate_pct": round(len(midprice_misses) / len(misses) * 100, 1) if misses else 0,
        "note": "READ-ONLY audit. No scoring changes. No routing changes. No execution changes.",
    }
    json_path.write_text(json.dumps(summary, indent=2))

    lines = [
        "# Mid-Price Top-vs-Winner Delta Audit",
        f"\n**Generated:** {summary['generated_at']}",
        f"\n## Summary",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total races | {total} |",
        f"| Total misses (top != winner) | {len(misses)} |",
        f"| Mid-price zone misses (SP 3.0–8.5) | {len(midprice_misses)} |",
        f"| Winner visible in snapshots | {len(visible)} |",
        f"| Rescuable by sidecar signal | {len(rescued)} |",
        f"| Rescue rate | {summary['rescue_rate_pct']}% |",
        f"| Mid-price miss rate | {summary['midprice_miss_rate_pct']}% |",
        f"\n## Rescue Signal Breakdown",
        f"\nRescue threshold: MDS>0.5, improvement>0.40, place_prob>0.80",
    ]

    rescue_by_signal: dict = {}
    for r in rescued:
        for sig in r["rescue_signals"].split(";"):
            sig = sig.strip()
            if sig:
                field = sig.split("=")[0]
                rescue_by_signal[field] = rescue_by_signal.get(field, 0) + 1
    for field, count in sorted(rescue_by_signal.items(), key=lambda x: -x[1]):
        lines.append(f"- {field}: {count} races")

    lines.append(f"\n## Operating Notes")
    lines.append(f"- READ-ONLY audit. No scoring changes, no routing changes, no execution changes.")
    lines.append(f"- Inputs: runner snapshot JSONL + results JSON from SL scraper")
    lines.append(f"- Only clean post-fix snapshots (excluding run_ids {sorted(CONTAMINATED_RUN_IDS)})")

    md_path.write_text("\n".join(lines))

    print(f"  Total races:          {total}")
    print(f"  Total misses:         {len(misses)}")
    print(f"  Midprice zone misses: {len(midprice_misses)}")
    print(f"  Winner visible:       {len(visible)}")
    print(f"  Rescuable by sidecar: {len(rescued)} ({summary['rescue_rate_pct']}%)")
    print(f"  CSV:  {csv_path}")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: all post-fix dates with snapshots)")
    args = parser.parse_args()

    if args.date:
        dates = [args.date]
    else:
        pattern = str(ROOT / "data" / "runner_snapshots_202*.jsonl")
        date_und_set: set = set()
        for p in glob.glob(pattern):
            parts = Path(p).stem.split("_")
            if len(parts) >= 5:
                date_und_set.add(f"{parts[2]}-{parts[3]}-{parts[4]}")
        dates = sorted(d for d in date_und_set if d >= FIX_DATE)

    print(f"Building mid-price delta for dates: {dates}")
    rows = build_delta(dates)
    write_outputs(rows)


if __name__ == "__main__":
    main()
