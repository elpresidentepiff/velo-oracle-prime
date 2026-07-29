#!/usr/bin/env python3
"""
VFU-22: Prospective Validation

Forward-tests the dual-lane signal quality (WIN_LANE VP>=0.40, EW_CANDIDATE)
in the prospective period (2026-06-15 onwards) and compares against the
VFU-18/19 historical baseline. Report-only.

Historical baseline (VFU-18):
  VP >= 0.40 fires: 447 rows
  WIN_LANE_CONFIRMED (win hit rate): 41.6%
  VP place conversion (win or placed): 58.2%
  EW_CANDIDATE place rate: from EW tracking

Usage:
    python scripts/ops/vfu_prospective_validation.py --cutoff 2026-06-15
    python scripts/ops/vfu_prospective_validation.py --cutoff 2026-06-15 --through 2026-07-27
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

OUTPUT_SUMMARY = DATA / "reports" / "vfu_22_prospective_validation_summary.json"
OUTPUT_BRIEF   = DATA / "reports" / "vfu_22_prospective_validation_summary.md"

VFU_VERSION = "VFU_22_PROSPECTIVE_VALIDATION_V1"

# VFU-18 historical baseline
HISTORICAL_BASELINE = {
    "vp_fires_n":         447,
    "win_lane_sr":        0.416,
    "vp_place_conversion": 0.582,
    "source": "VFU_18_PLACE_DATA_ENRICHMENT_V1",
}

SIGNAL_THRESHOLD     = 0.40   # WIN_LANE VP threshold
MIN_ROWS_FOR_VERDICT = 30     # minimum prospective rows before issuing verdict


def load_sigma_rows(cutoff: str, through: str) -> list[dict]:
    """Load all sigma rows between cutoff (inclusive) and through (inclusive)."""
    rows = []
    for path in sorted((DATA / "sigma_results").glob("sigma_results_2026_*.json")):
        date_tag = path.stem.replace("sigma_results_", "")
        # Convert tag to YYYY-MM-DD for comparison
        date_str = date_tag.replace("_", "-")
        if date_str < cutoff or date_str > through:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.extend(data.get("rows", []))
    return rows


def analyse(rows: list[dict]) -> dict:
    """Compute prospective validation metrics from sigma rows."""
    n = len(rows)
    if n == 0:
        return {"n": 0}

    wins   = sum(1 for r in rows if r.get("outcome") == "WIN")
    frames = sum(1 for r in rows if r.get("outcome") in ("WIN", "PLACED"))
    misses = sum(1 for r in rows if r.get("outcome") == "MISS")

    # WIN_LANE: VP >= threshold
    win_lane    = [r for r in rows if (r.get("velo_prime_prob") or 0.0) >= SIGNAL_THRESHOLD]
    wl_n        = len(win_lane)
    wl_wins     = sum(1 for r in win_lane if r.get("outcome") == "WIN")
    wl_frames   = sum(1 for r in win_lane if r.get("outcome") in ("WIN", "PLACED"))

    # EW_CANDIDATE — use ew_outcome field (set by sigma runner)
    ew_rows   = [r for r in rows if r.get("assigned_product") == "EW_CANDIDATE"]
    ew_n      = len(ew_rows)
    ew_placed = sum(1 for r in ew_rows if r.get("ew_outcome") in ("EW_PLACE", "EW_WIN"))

    # Signal verdict
    if wl_n < MIN_ROWS_FOR_VERDICT:
        signal_verdict = "INSUFFICIENT_DATA"
    else:
        wl_sr = wl_wins / wl_n
        baseline_sr = HISTORICAL_BASELINE["win_lane_sr"]
        if wl_sr >= baseline_sr * 0.80:
            signal_verdict = "SIGNAL_HOLDING"
        elif wl_sr >= baseline_sr * 0.60:
            signal_verdict = "SIGNAL_DEGRADED_MINOR"
        else:
            signal_verdict = "SIGNAL_DEGRADED_MAJOR"

    return {
        "n": n,
        "wins": wins,
        "frames": frames,
        "misses": misses,
        "sr": round(wins / n, 4),
        "frame_rate": round(frames / n, 4),
        "win_lane_n": wl_n,
        "win_lane_wins": wl_wins,
        "win_lane_frames": wl_frames,
        "win_lane_sr": round(wl_wins / wl_n, 4) if wl_n else None,
        "win_lane_frame_rate": round(wl_frames / wl_n, 4) if wl_n else None,
        "ew_candidate_n": ew_n,
        "ew_candidate_placed": ew_placed,
        "ew_candidate_place_rate": round(ew_placed / ew_n, 4) if ew_n else None,
        "vp_threshold_used": SIGNAL_THRESHOLD,
        "historical_baseline": HISTORICAL_BASELINE,
        "signal_verdict": signal_verdict,
    }


def build_brief(summary: dict) -> str:
    m = summary.get("metrics", {})
    bl = HISTORICAL_BASELINE
    lines = [
        "# VFU-22 — Prospective Validation — Operator Brief",
        "",
        "## Period",
        f"  {summary.get('cutoff')} to {summary.get('through')} — {m.get('n', 0)} races",
        "",
        "## Overall Signal",
        f"| Metric | Prospective | Historical (VFU-18) |",
        f"|---|---|---|",
        f"| WIN_LANE SR (VP>={SIGNAL_THRESHOLD}) | {m.get('win_lane_sr','n/a')} | {bl['win_lane_sr']} |",
        f"| WIN_LANE frame rate | {m.get('win_lane_frame_rate','n/a')} | {bl['vp_place_conversion']} |",
        f"| WIN_LANE n | {m.get('win_lane_n','n/a')} | {bl['vp_fires_n']} |",
        f"| EW_CANDIDATE place rate | {m.get('ew_candidate_place_rate','n/a')} | - |",
        "",
        f"**Signal Verdict: {m.get('signal_verdict', 'UNKNOWN')}**",
        "",
        "## Classifications",
        *[f"- {c}" for c in summary.get("classification_codes", [])],
    ]
    return "\n".join(lines)


def main(cutoff: str = "2026-06-15", through: str = "2026-07-27") -> dict:
    DATA.joinpath("reports").mkdir(parents=True, exist_ok=True)

    rows = load_sigma_rows(cutoff, through)
    metrics = analyse(rows)

    dates_loaded = sorted(set(
        path.stem.replace("sigma_results_", "").replace("_", "-")
        for path in sorted((DATA / "sigma_results").glob("sigma_results_2026_*.json"))
        if cutoff <= path.stem.replace("sigma_results_", "").replace("_", "-") <= through
    ))

    summary = {
        "vfu22_validation_version": VFU_VERSION,
        "cutoff":  cutoff,
        "through": through,
        "dates_loaded": dates_loaded,
        "dates_count": len(dates_loaded),
        "metrics": metrics,
        "classification_codes": [
            "VFU_22_PROSPECTIVE_VALIDATION_COMPLETE",
            "DUAL_LANE_SIGNAL_MEASURED_PROSPECTIVELY",
            f"SIGNAL_VERDICT_{metrics.get('signal_verdict', 'UNKNOWN')}",
            "NO_VP_THRESHOLD_CHANGE",
            "NO_LIVE_SCORING_CHANGE",
            "NO_SUPABASE_WRITES",
            "REPORT_ONLY",
        ],
    }

    OUTPUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    OUTPUT_BRIEF.write_text(build_brief(summary), encoding="utf-8")

    bl = HISTORICAL_BASELINE
    m = metrics
    print(f"VFU-22 Prospective Validation ({cutoff} to {through})")
    print(f"  Dates loaded: {len(dates_loaded)}  Races: {m.get('n',0)}")
    print(f"  Overall SR: {m.get('sr','n/a')}  Frame rate: {m.get('frame_rate','n/a')}")
    print(f"  WIN_LANE (VP>={SIGNAL_THRESHOLD}): n={m.get('win_lane_n','n/a')} SR={m.get('win_lane_sr','n/a')} frame_rate={m.get('win_lane_frame_rate','n/a')}")
    print(f"  Historical baseline: SR={bl['win_lane_sr']} place_conversion={bl['vp_place_conversion']}")
    print(f"  Signal verdict: {m.get('signal_verdict', 'UNKNOWN')}")
    print(f"  Summary: {OUTPUT_SUMMARY}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFU-22: Prospective dual-lane signal validation")
    parser.add_argument("--cutoff",  default="2026-06-15", help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--through", default="2026-07-27", help="End date YYYY-MM-DD (inclusive)")
    args = parser.parse_args()
    main(args.cutoff, args.through)
