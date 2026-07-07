"""VFU-26 — Confidence Flood Evidence Expansion.

Evidence expansion only. Answers one question: does the VFU-22/VFU-23/VFU-24/VFU-25
CONFIDENCE_FLOOD_FALSE_GREEN finding survive more evidence? No cure is implemented, no
VP Gatekeeper criteria are changed, no live scoring path is touched.

Discovers all local `sigma_results_*.json` artifacts (this repo's `data/sigma_results/`
directory only, plus any additional directories explicitly passed in), deduplicates by
date, and recomputes the full VFU-22 through VFU-24 diagnostic picture against the
expanded corpus. Compares the expanded result against the VFU-22/23/24 baseline
(31 dates, 6 confirmed false-green) and reports whether the pattern held, weakened, or
mixed.
"""

import argparse
import glob
import json
import statistics
from pathlib import Path

from scripts.ops.build_confidence_flood_diagnostic import (
    classify_gap_band,
    classify_gate,
)
from scripts.ops.build_confidence_flood_root_cause_split import (
    _quartiles,
    classify_subtypes,
    threshold_pressure_band,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SIGMA_RESULTS_DIR = REPO_ROOT / "data" / "sigma_results"

BASELINE_SR = 0.243

# The VFU-22/VFU-23/VFU-24 baseline this expansion is checked against.
BASELINE_SIGMA_DATES_SCANNED = 31
BASELINE_FALSE_GREEN_SET = {
    "2026-06-09",
    "2026-06-16",
    "2026-06-18",
    "2026-06-19",
    "2026-06-23",
    "2026-06-30",
}
BASELINE_GREEN_DAYS = 16
BASELINE_FALSE_GREEN_RATE = 6 / 16  # 0.375
BASELINE_GAP_COLLAPSE = 4
BASELINE_HEALTHY_GAP = 2
BASELINE_THRESHOLD_FLOOD = 4  # of the 6 false-green days
BASELINE_MARKET_ENVIRONMENT = 2
BASELINE_SAMPLE_CAPTURE_QUALITY = 0
BASELINE_UNRESOLVED = 0


def discover_sigma_result_paths(extra_dirs=None):
    """Discover all sigma_results_*.json files in this repo's data/sigma_results/,
    plus any additional local directories passed explicitly. Deduplicates by date,
    preferring the first directory in which a date is found."""
    dirs = [SIGMA_RESULTS_DIR] + [Path(d) for d in (extra_dirs or [])]
    by_date = {}
    for directory in dirs:
        if not directory.exists():
            continue
        for path in sorted(glob.glob(str(directory / "sigma_results_*.json"))):
            date_key = Path(path).stem.replace("sigma_results_", "")
            if date_key not in by_date:
                by_date[date_key] = path
    return sorted(by_date.values())


def load_and_diagnose(path):
    with open(path) as f:
        payload = json.load(f)

    date = payload.get("date") or Path(path).stem.replace("sigma_results_", "").replace("_", "-")
    sigma_status = payload.get("sigma_status")
    rows = payload.get("rows") or []
    vps = [r.get("velo_prime_prob") for r in rows if isinstance(r.get("velo_prime_prob"), (int, float))]

    winner_sps = [
        r.get("winner_sp")
        for r in rows
        if r.get("outcome") == "WIN" and isinstance(r.get("winner_sp"), (int, float)) and r.get("winner_sp") > 0
    ]
    winner_sp_median = statistics.median(winner_sps) if winner_sps else None

    if not vps:
        return {
            "date": date,
            "sigma_status": sigma_status,
            "n_races": len(rows),
            "day_sr": payload.get("sr"),
            "avg_vp": None,
            "n_vp_ge_040": None,
            "n_vp_ge_045": None,
            "n_vp_ge_040_share": None,
            "n_vp_ge_045_share": None,
            "vp_gate_class": "UNCLASSIFIED",
            "avg_hit_prob": payload.get("avg_hit_prob"),
            "avg_miss_prob": payload.get("avg_miss_prob"),
            "vp_discrimination_gap": None,
            "gap_band": "UNKNOWN",
            "false_green_confirmed": False,
            "winner_sp_median": winner_sp_median,
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
    false_green_confirmed = gate == "GREEN" and isinstance(day_sr, (int, float)) and day_sr < BASELINE_SR
    n_races = len(rows)

    return {
        "date": date,
        "sigma_status": sigma_status,
        "n_races": n_races,
        "day_sr": day_sr,
        "avg_vp": round(avg_vp, 4),
        "n_vp_ge_040": n_40,
        "n_vp_ge_045": n_45,
        "n_vp_ge_040_share": round(n_40 / n_races, 4) if n_races else None,
        "n_vp_ge_045_share": round(n_45 / n_races, 4) if n_races else None,
        "vp_gate_class": gate,
        "avg_hit_prob": avg_hit_prob,
        "avg_miss_prob": avg_miss_prob,
        "vp_discrimination_gap": round(gap, 4) if gap is not None else None,
        "gap_band": gap_band,
        "false_green_confirmed": false_green_confirmed,
        "winner_sp_median": winner_sp_median,
    }


def assign_cohort(row, false_green_dates):
    if row["date"] in false_green_dates:
        return "FALSE_GREEN_DAYS"
    if row["vp_gate_class"] == "GREEN":
        return "TRUE_GREEN_DAYS"
    return "NON_GREEN_DAYS"


def build_guard_flags(row, true_green_rows):
    """Reimplements the VFU-24/25 guard logic on top of the expanded corpus so the
    Gap-Collapse Guard, Threshold-Flood Guard, and Combined overlay can be evaluated
    against every GREEN day in the expanded set, not just the known 6."""
    gap_collapse_triggered = row["gap_band"] in ("INVERTED", "COMPRESSED")

    tg_40 = [r["n_vp_ge_040_share"] for r in true_green_rows if r["n_vp_ge_040_share"] is not None]
    tg_45 = [r["n_vp_ge_045_share"] for r in true_green_rows if r["n_vp_ge_045_share"] is not None]
    q40 = _quartiles(tg_40)
    q45 = _quartiles(tg_45)
    band_40 = threshold_pressure_band(row["n_vp_ge_040_share"], q40)
    band_45 = threshold_pressure_band(row["n_vp_ge_045_share"], q45)
    threshold_flood_triggered = band_40 == "ABOVE_TRUE_GREEN_P75" or band_45 == "ABOVE_TRUE_GREEN_P75"

    return {
        "gap_collapse_guard": gap_collapse_triggered,
        "threshold_flood_guard": threshold_flood_triggered,
        "combined_overlay": gap_collapse_triggered or threshold_flood_triggered,
    }


def market_outlier_band(row, true_green_rows):
    tg_sp = [r["winner_sp_median"] for r in true_green_rows if r.get("winner_sp_median") is not None]
    q = _quartiles(tg_sp)
    if row.get("winner_sp_median") is None or q is None:
        return "INSUFFICIENT_EVIDENCE"
    if row["winner_sp_median"] < q["min"] or row["winner_sp_median"] > q["max"]:
        return "OUTLIER"
    return "WITHIN_RANGE"


def sample_capture_quality_status(row):
    if row.get("sigma_status") and row["sigma_status"] != "PASS":
        return "FLAGGED"
    if row.get("avg_hit_prob") is None or row.get("avg_miss_prob") is None:
        return "FLAGGED"
    if row.get("day_sr") is None or not row.get("n_races"):
        return "FLAGGED"
    return "CLEAN"


def compute_guard_coverage(diagnosed_rows, false_green_dates):
    """For each guard, count TP/FP/FN/TN against ground truth = false_green_confirmed,
    restricted to GREEN-gated days only (guards never fire on non-GREEN days by design)."""
    green_rows = [r for r in diagnosed_rows if r["vp_gate_class"] == "GREEN"]
    true_green_rows = [r for r in green_rows if r["date"] not in false_green_dates]

    guard_stats = {}
    for guard_key, guard_label, target_subtype in (
        ("gap_collapse_guard", "Gap-Collapse Guard", "GAP_COLLAPSE_FALSE_GREEN"),
        ("threshold_flood_guard", "Threshold-Flood Guard", "HEALTHY_GAP_FALSE_GREEN + THRESHOLD_FLOOD_FALSE_GREEN"),
        ("combined_overlay", "Combined Green-Day Risk Overlay", "Both"),
    ):
        tp = fp = fn = tn = 0
        for row in green_rows:
            flags = row["guard_flags"]
            actual_positive = row["false_green_confirmed"]
            predicted_positive = flags[guard_key]
            if predicted_positive and actual_positive:
                tp += 1
            elif predicted_positive and not actual_positive:
                fp += 1
            elif not predicted_positive and actual_positive:
                fn += 1
            else:
                tn += 1
        total_positive = tp + fn
        total_negative = fp + tn
        guard_stats[guard_label] = {
            "target_subtype": target_subtype,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
            "coverage_rate": round(tp / total_positive, 4) if total_positive else None,
            "false_positive_rate": round(fp / total_negative, 4) if total_negative else None,
            "false_negative_rate": round(fn / total_positive, 4) if total_positive else None,
        }
    return guard_stats


def run_evidence_expansion(extra_dirs=None):
    paths = discover_sigma_result_paths(extra_dirs)
    diagnosed = [load_and_diagnose(p) for p in paths]

    confirmed_false_green = {r["date"] for r in diagnosed if r["false_green_confirmed"]}
    new_dates = sorted(confirmed_false_green - BASELINE_FALSE_GREEN_SET)
    removed_dates = sorted(BASELINE_FALSE_GREEN_SET - confirmed_false_green)
    unchanged_dates = sorted(BASELINE_FALSE_GREEN_SET & confirmed_false_green)

    green_rows = [r for r in diagnosed if r["vp_gate_class"] == "GREEN"]
    true_green_rows = [r for r in green_rows if r["date"] not in confirmed_false_green]
    false_green_rows = [r for r in green_rows if r["date"] in confirmed_false_green]

    # Attach subtype + guard flags + market outlier + capture quality to every GREEN day.
    for row in green_rows:
        primary, secondary, notes = classify_subtypes(row, true_green_rows)
        row["primary_subtype"] = primary if row["date"] in confirmed_false_green else None
        row["secondary_subtypes"] = secondary if row["date"] in confirmed_false_green else []
        row["evidence_notes"] = notes if row["date"] in confirmed_false_green else ""
        row["guard_flags"] = build_guard_flags(row, true_green_rows)
        row["market_outlier_status"] = market_outlier_band(row, true_green_rows)
        row["capture_quality_status"] = sample_capture_quality_status(row)

    for row in diagnosed:
        if row["vp_gate_class"] != "GREEN":
            row["primary_subtype"] = None
            row["secondary_subtypes"] = []
            row["evidence_notes"] = ""
            row["guard_flags"] = {"gap_collapse_guard": False, "threshold_flood_guard": False, "combined_overlay": False}
            row["market_outlier_status"] = "N/A_NOT_GREEN"
            row["capture_quality_status"] = sample_capture_quality_status(row)

    subtype_counts = {
        "gap_collapse_false_green": sum(1 for r in false_green_rows if r["primary_subtype"] == "GAP_COLLAPSE_FALSE_GREEN"),
        "healthy_gap_false_green": sum(1 for r in false_green_rows if r["primary_subtype"] == "HEALTHY_GAP_FALSE_GREEN"),
        "threshold_flood_false_green": sum(
            1 for r in false_green_rows if "THRESHOLD_FLOOD_FALSE_GREEN" in r["secondary_subtypes"]
        ),
        "market_environment_false_green": sum(
            1 for r in false_green_rows if "MARKET_ENVIRONMENT_FALSE_GREEN" in r["secondary_subtypes"]
        ),
        "sample_capture_quality_false_green": sum(
            1 for r in false_green_rows if "SAMPLE_CAPTURE_QUALITY_FALSE_GREEN" in r["secondary_subtypes"]
        ),
        "unresolved_false_green": sum(
            1 for r in false_green_rows if "UNRESOLVED_FALSE_GREEN" in r["secondary_subtypes"]
        ),
    }

    guard_coverage = compute_guard_coverage(diagnosed, confirmed_false_green)

    market_outlier_rows = [
        {
            "date": r["date"],
            "false_green_confirmed": r["false_green_confirmed"],
            "winner_sp_median": r["winner_sp_median"],
            "market_outlier_band": r["market_outlier_status"],
            "primary_subtype": r["primary_subtype"],
            "caught_by_gap_guard": r["guard_flags"]["gap_collapse_guard"],
            "caught_by_threshold_guard": r["guard_flags"]["threshold_flood_guard"],
            "caught_by_combined_overlay": r["guard_flags"]["combined_overlay"],
        }
        for r in green_rows
    ]

    expansion_succeeded = len(diagnosed) > BASELINE_SIGMA_DATES_SCANNED

    summary = {
        "sigma_dates_scanned": {
            "baseline": BASELINE_SIGMA_DATES_SCANNED,
            "expanded": len(diagnosed),
            "delta": len(diagnosed) - BASELINE_SIGMA_DATES_SCANNED,
        },
        "green_days": {
            "baseline": BASELINE_GREEN_DAYS,
            "expanded": len(green_rows),
            "delta": len(green_rows) - BASELINE_GREEN_DAYS,
        },
        "false_green_days": {
            "baseline": len(BASELINE_FALSE_GREEN_SET),
            "expanded": len(confirmed_false_green),
            "delta": len(confirmed_false_green) - len(BASELINE_FALSE_GREEN_SET),
        },
        "false_green_rate": {
            "baseline": round(BASELINE_FALSE_GREEN_RATE, 4),
            "expanded": round(len(confirmed_false_green) / len(green_rows), 4) if green_rows else None,
        },
        "true_green_days": {
            "baseline": BASELINE_GREEN_DAYS - len(BASELINE_FALSE_GREEN_SET),
            "expanded": len(true_green_rows),
        },
        "gap_collapse_false_green": {"baseline": BASELINE_GAP_COLLAPSE, "expanded": subtype_counts["gap_collapse_false_green"]},
        "healthy_gap_false_green": {"baseline": BASELINE_HEALTHY_GAP, "expanded": subtype_counts["healthy_gap_false_green"]},
        "threshold_flood_false_green": {"baseline": BASELINE_THRESHOLD_FLOOD, "expanded": subtype_counts["threshold_flood_false_green"]},
        "market_environment_false_green": {"baseline": BASELINE_MARKET_ENVIRONMENT, "expanded": subtype_counts["market_environment_false_green"]},
        "sample_capture_quality_false_green": {"baseline": BASELINE_SAMPLE_CAPTURE_QUALITY, "expanded": subtype_counts["sample_capture_quality_false_green"]},
        "unresolved_false_green": {"baseline": BASELINE_UNRESOLVED, "expanded": subtype_counts["unresolved_false_green"]},
    }

    return {
        "expansion_succeeded": expansion_succeeded,
        "sigma_dates_scanned": len(diagnosed),
        "reproduction_check": {
            "baseline_false_green_set": sorted(BASELINE_FALSE_GREEN_SET),
            "new_false_green_dates": new_dates,
            "removed_false_green_dates": removed_dates,
            "unchanged_false_green_dates": unchanged_dates,
            "baseline_fully_reproduced": removed_dates == [],
        },
        "evidence_expansion_summary": summary,
        "guard_coverage": guard_coverage,
        "market_outlier_table": market_outlier_rows,
        "per_date_diagnostics": diagnosed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extra-dir", action="append", default=None, help="Additional local sigma_results directory to scan (repeatable)")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    output = run_evidence_expansion(args.extra_dir)

    if args.out:
        with open(args.out, "w") as f:
            json.dump(output, f, indent=2)
    else:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
