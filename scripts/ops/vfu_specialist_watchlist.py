#!/usr/bin/env python3
"""
VFU-23: Specialist Watchlist Validation

Checks the 16 VFU-17 place specialist horses against prospective sigma results
(2026-06-15 onwards) to verify whether their place-specialist pattern persists.

Historical baseline (VFU-17):
  All 16 horses: place_rate 0.667-1.0, win_rate 0.0, 2-3 appearances each

Usage:
    python scripts/ops/vfu_specialist_watchlist.py --cutoff 2026-06-15
    python scripts/ops/vfu_specialist_watchlist.py --cutoff 2026-06-15 --through 2026-07-27
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

SPECIALIST_SOURCE = DATA / "reports" / "vfu_17_place_specialist_candidates.json"
OUTPUT_SUMMARY    = DATA / "reports" / "vfu_23_specialist_watchlist_summary.json"
OUTPUT_BRIEF      = DATA / "reports" / "vfu_23_specialist_watchlist_summary.md"

VFU_VERSION = "VFU_23_SPECIALIST_WATCHLIST_V1"

HISTORICAL_PLACE_RATE_THRESHOLD = 0.667   # minimum to be a specialist


def normalize_name(name: str) -> str:
    return (name or "").lower().strip().replace("'", "").replace("-", " ").replace("  ", " ")


def load_specialists() -> list[dict]:
    if not SPECIALIST_SOURCE.exists():
        return []
    raw = json.loads(SPECIALIST_SOURCE.read_text(encoding="utf-8"))
    # Accept either a list of dicts or a dict of {name: {...}}
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return [{"horse_name": k, **v} for k, v in raw.items()]
    return []


def load_sigma_rows(cutoff: str, through: str) -> list[dict]:
    rows = []
    for path in sorted((DATA / "sigma_results").glob("sigma_results_2026_*.json")):
        date_str = path.stem.replace("sigma_results_", "").replace("_", "-")
        if date_str < cutoff or date_str > through:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in data.get("rows", []):
            rows.append({**row, "_date": date_str})
    return rows


def evaluate_specialist(specialist_name: str, sigma_rows: list[dict]) -> dict:
    """Find all prospective sigma rows where this horse was the VELO pick."""
    norm = normalize_name(specialist_name)
    appearances = [r for r in sigma_rows if normalize_name(r.get("predicted", "")) == norm]

    n = len(appearances)
    if n == 0:
        return {
            "horse_name": specialist_name,
            "prospective_n": 0,
            "prospective_wins": 0,
            "prospective_frames": 0,
            "prospective_sr": None,
            "prospective_frame_rate": None,
            "verdict": "NO_PROSPECTIVE_APPEARANCES",
        }

    wins   = sum(1 for r in appearances if r.get("outcome") == "WIN")
    frames = sum(1 for r in appearances if r.get("outcome") in ("WIN", "PLACED"))
    sr     = round(wins / n, 4)
    fr_raw = frames / n
    fr     = round(fr_raw, 4)

    if n < 2:
        verdict = "INSUFFICIENT_DATA"
    elif fr_raw >= HISTORICAL_PLACE_RATE_THRESHOLD:
        verdict = "SPECIALIST_CONFIRMED"
    else:
        verdict = "SPECIALIST_DEGRADED"

    return {
        "horse_name": specialist_name,
        "prospective_n": n,
        "prospective_wins": wins,
        "prospective_frames": frames,
        "prospective_sr": sr,
        "prospective_frame_rate": fr,
        "verdict": verdict,
        "appearances": [
            {"date": r.get("_date"), "course": r.get("course"), "outcome": r.get("outcome"),
             "vp": r.get("velo_prime_prob")}
            for r in appearances
        ],
    }


def build_brief(summary: dict) -> str:
    results = summary.get("results", [])
    confirmed  = [r for r in results if r["verdict"] == "SPECIALIST_CONFIRMED"]
    degraded   = [r for r in results if r["verdict"] == "SPECIALIST_DEGRADED"]
    no_data    = [r for r in results if r["verdict"] == "INSUFFICIENT_DATA"]
    no_appear  = [r for r in results if r["verdict"] == "NO_PROSPECTIVE_APPEARANCES"]

    lines = [
        "# VFU-23 — Specialist Watchlist Validation — Operator Brief",
        "",
        f"## Period: {summary.get('cutoff')} to {summary.get('through')}",
        f"  Prospective races: {summary.get('total_prospective_rows', 0)}",
        f"  Specialist appearances found: {summary.get('total_specialist_appearances', 0)}",
        "",
        "## Verdicts",
        f"| Verdict | Count |",
        f"|---|---|",
        f"| SPECIALIST_CONFIRMED | {len(confirmed)} |",
        f"| SPECIALIST_DEGRADED  | {len(degraded)} |",
        f"| INSUFFICIENT_DATA    | {len(no_data)} |",
        f"| NO_PROSPECTIVE_APPEARANCES | {len(no_appear)} |",
        "",
    ]

    if confirmed:
        lines += ["## Confirmed Specialists", "| Horse | n | Wins | Frames | Frame Rate |",
                  "|---|---|---|---|---|"]
        for r in confirmed:
            lines.append(f"| {r['horse_name']} | {r['prospective_n']} | {r['prospective_wins']} "
                         f"| {r['prospective_frames']} | {r['prospective_frame_rate']} |")
        lines.append("")

    if degraded:
        lines += ["## Degraded Specialists", "| Horse | n | Wins | Frames | Frame Rate |",
                  "|---|---|---|---|---|"]
        for r in degraded:
            lines.append(f"| {r['horse_name']} | {r['prospective_n']} | {r['prospective_wins']} "
                         f"| {r['prospective_frames']} | {r['prospective_frame_rate']} |")
        lines.append("")

    lines += [
        "## Classifications",
        *[f"- {c}" for c in summary.get("classification_codes", [])],
    ]
    return "\n".join(lines)


def main(cutoff: str = "2026-06-15", through: str = "2026-07-27") -> dict:
    DATA.joinpath("reports").mkdir(parents=True, exist_ok=True)

    specialists = load_specialists()
    if not specialists:
        print("WARNING: No specialist candidates found — check VFU-17 output file exists")
        specialist_names = []
    else:
        specialist_names = [s.get("horse_name") or s.get("name") or "" for s in specialists]

    sigma_rows = load_sigma_rows(cutoff, through)

    results = [evaluate_specialist(name, sigma_rows) for name in specialist_names if name]

    confirmed = sum(1 for r in results if r["verdict"] == "SPECIALIST_CONFIRMED")
    degraded  = sum(1 for r in results if r["verdict"] == "SPECIALIST_DEGRADED")
    total_appearances = sum(r["prospective_n"] for r in results)

    summary = {
        "vfu23_validation_version": VFU_VERSION,
        "cutoff":  cutoff,
        "through": through,
        "specialists_checked": len(results),
        "total_prospective_rows": len(sigma_rows),
        "total_specialist_appearances": total_appearances,
        "confirmed": confirmed,
        "degraded":  degraded,
        "results":   results,
        "classification_codes": [
            "VFU_23_SPECIALIST_WATCHLIST_COMPLETE",
            "PLACE_SPECIALIST_PATTERN_CHECKED_PROSPECTIVELY",
            f"CONFIRMED_{confirmed}_OF_{len(results)}_SPECIALISTS",
            "NO_VP_THRESHOLD_CHANGE",
            "NO_LIVE_SCORING_CHANGE",
            "NO_SUPABASE_WRITES",
            "REPORT_ONLY",
        ],
    }

    OUTPUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    OUTPUT_BRIEF.write_text(build_brief(summary), encoding="utf-8")

    print(f"VFU-23 Specialist Watchlist ({cutoff} to {through})")
    print(f"  Specialists checked: {len(results)}")
    print(f"  Total prospective appearances: {total_appearances}")
    print(f"  Confirmed: {confirmed}  Degraded: {degraded}")
    print(f"  Summary: {OUTPUT_SUMMARY}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFU-23: Specialist watchlist prospective validation")
    parser.add_argument("--cutoff",  default="2026-06-15", help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--through", default="2026-07-27", help="End date YYYY-MM-DD (inclusive)")
    args = parser.parse_args()
    main(args.cutoff, args.through)
