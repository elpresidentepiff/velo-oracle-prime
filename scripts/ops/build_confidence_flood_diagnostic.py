"""VFU-23 — Confidence Flood Retrospective Diagnostic.

Retrospective-only diagnostic. Reads existing `data/sigma_results/sigma_results_*.json`
artifacts after Sigma has already closed for a day and reports whether that day's VP
distribution shows the CONFIDENCE_FLOOD_FALSE_GREEN pattern identified in VFU-22
(`data/reports/vfu_22_false_green_feature_autopsy.md`).

This module does not read or write anything pre-race. It never touches the live VP
Gatekeeper (`docs/current/VP_GATEKEEPER_PROMOTION_V1.md`), live scoring, Supabase, or
Telegram. `false_green_confirmed` requires the day's actual results and therefore cannot
exist before Sigma closes — it is not a pre-race signal and must never be wired into the
live gate.
"""

import argparse
import glob
import json
import statistics
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIGMA_RESULTS_DIR = REPO_ROOT / "data" / "sigma_results"

BASELINE_SR = 0.243

# VP Gatekeeper bands, reproduced read-only from docs/current/VP_GATEKEEPER_PROMOTION_V1.md.
# This diagnostic never writes back to that doctrine or its criteria.
GREEN_AVG_VP = 0.35
GREEN_MIN_N40 = 5
GREEN_MIN_N45 = 2
AMBER_AVG_VP_LOW = 0.25
AMBER_AVG_VP_HIGH = 0.35
AMBER_MIN_N40 = 1
AMBER_MAX_N40 = 4


def classify_gate(avg_vp, n_40, n_45):
    if avg_vp >= GREEN_AVG_VP and n_40 >= GREEN_MIN_N40 and n_45 >= GREEN_MIN_N45:
        return "GREEN"
    if AMBER_AVG_VP_LOW <= avg_vp < AMBER_AVG_VP_HIGH and AMBER_MIN_N40 <= n_40 <= AMBER_MAX_N40:
        return "AMBER"
    if avg_vp < AMBER_AVG_VP_LOW or n_40 == 0:
        return "RED"
    return "UNCLASSIFIED"


def classify_gap_band(gap):
    if gap is None:
        return "UNKNOWN"
    if gap < 0:
        return "INVERTED"
    if gap < 0.05:
        return "COMPRESSED"
    if gap < 0.08:
        return "WEAK"
    return "HEALTHY"


def load_sigma_result(path):
    with open(path) as f:
        return json.load(f)


def diagnose_date(payload, source_path):
    date = payload.get("date") or Path(source_path).stem.replace("sigma_results_", "").replace("_", "-")
    sigma_status = payload.get("sigma_status")
    rows = payload.get("rows") or []
    vps = [r.get("velo_prime_prob") for r in rows if isinstance(r.get("velo_prime_prob"), (int, float))]

    notes = []
    if not vps:
        notes.append("no rows with velo_prime_prob — cannot classify gate")
        return {
            "date": date,
            "sigma_status": sigma_status,
            "n_races": len(rows),
            "day_sr": payload.get("sr"),
            "avg_vp": None,
            "n_vp_ge_040": None,
            "n_vp_ge_045": None,
            "vp_gate_class": "UNCLASSIFIED",
            "avg_hit_prob": payload.get("avg_hit_prob"),
            "avg_miss_prob": payload.get("avg_miss_prob"),
            "vp_discrimination_gap": None,
            "gap_band": "UNKNOWN",
            "confidence_flood_flag": False,
            "false_green_confirmed": False,
            "notes": "; ".join(notes),
        }

    avg_vp = statistics.mean(vps)
    n_40 = sum(1 for v in vps if v >= 0.40)
    n_45 = sum(1 for v in vps if v >= 0.45)
    gate = classify_gate(avg_vp, n_40, n_45)

    avg_hit_prob = payload.get("avg_hit_prob")
    avg_miss_prob = payload.get("avg_miss_prob")
    gap = None
    if isinstance(avg_hit_prob, (int, float)) and isinstance(avg_miss_prob, (int, float)):
        gap = avg_hit_prob - avg_miss_prob
    gap_band = classify_gap_band(gap)

    day_sr = payload.get("sr")

    confidence_flood_flag = gate == "GREEN" and gap_band in ("INVERTED", "COMPRESSED")
    false_green_confirmed = gate == "GREEN" and isinstance(day_sr, (int, float)) and day_sr < BASELINE_SR

    if sigma_status and sigma_status != "PASS":
        notes.append(f"sigma_status={sigma_status} (lower-confidence capture)")
    if gap is None:
        notes.append("avg_hit_prob/avg_miss_prob missing — gap band UNKNOWN")

    return {
        "date": date,
        "sigma_status": sigma_status,
        "n_races": len(rows),
        "day_sr": day_sr,
        "avg_vp": round(avg_vp, 4),
        "n_vp_ge_040": n_40,
        "n_vp_ge_045": n_45,
        "vp_gate_class": gate,
        "avg_hit_prob": avg_hit_prob,
        "avg_miss_prob": avg_miss_prob,
        "vp_discrimination_gap": round(gap, 4) if gap is not None else None,
        "gap_band": gap_band,
        "confidence_flood_flag": confidence_flood_flag,
        "false_green_confirmed": false_green_confirmed,
        "notes": "; ".join(notes),
    }


def run_diagnostic(sigma_results_dir=None):
    directory = Path(sigma_results_dir) if sigma_results_dir else SIGMA_RESULTS_DIR
    paths = sorted(glob.glob(str(directory / "sigma_results_*.json")))
    results = []
    for path in paths:
        payload = load_sigma_result(path)
        results.append(diagnose_date(payload, path))
    return results


VFU_22_FALSE_GREEN_SET = {
    "2026-06-09",
    "2026-06-16",
    "2026-06-18",
    "2026-06-19",
    "2026-06-23",
    "2026-06-30",
}


def check_vfu22_reproduction(results):
    confirmed = {r["date"] for r in results if r["false_green_confirmed"]}
    matched = VFU_22_FALSE_GREEN_SET & confirmed
    missing = VFU_22_FALSE_GREEN_SET - confirmed
    extra = confirmed - VFU_22_FALSE_GREEN_SET
    return {
        "expected": sorted(VFU_22_FALSE_GREEN_SET),
        "confirmed": sorted(confirmed),
        "matched": sorted(matched),
        "missing": sorted(missing),
        "extra_beyond_vfu22_set": sorted(extra),
        "fully_reproduced": missing == set(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sigma-results-dir", default=None)
    parser.add_argument("--out", default=None, help="Write JSON results to this path")
    args = parser.parse_args()

    results = run_diagnostic(args.sigma_results_dir)
    reproduction = check_vfu22_reproduction(results)

    output = {"results": results, "vfu22_reproduction_check": reproduction}

    if args.out:
        with open(args.out, "w") as f:
            json.dump(output, f, indent=2)
    else:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
