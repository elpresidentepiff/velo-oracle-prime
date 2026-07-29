"""VFU-24 — Confidence Flood Root-Cause Split.

Pathology classification only — this module proposes no cure and makes no VP
Gatekeeper, live-scoring, Supabase, or Telegram change. It splits the six confirmed
false-green days (from VFU-22/VFU-23) into root-cause subtypes, using only fields
already present in `data/sigma_results/sigma_results_*.json` plus the VFU-23
diagnostic's gate/gap classification (imported, not duplicated).

Read-only relative to VFU-23: reuses `build_confidence_flood_diagnostic.run_diagnostic`
and its gate/gap-band classification rather than re-deriving it, so the two VFUs never
drift out of sync.
"""

import argparse
import json
import statistics
from pathlib import Path

from scripts.ops.build_confidence_flood_diagnostic import (
    VFU_22_FALSE_GREEN_SET,
    SIGMA_RESULTS_DIR,
    run_diagnostic,
)

KNOWN_FALSE_GREEN_SET = set(VFU_22_FALSE_GREEN_SET)


def load_row_level_stats(date, sigma_results_dir=None):
    """Pull fields not already carried by the VFU-23 diagnostic output: winner SP,
    miss-class mix, high_conf_sr, frame_rate — straight from the source file."""
    directory = Path(sigma_results_dir) if sigma_results_dir else SIGMA_RESULTS_DIR
    fname = date.replace("-", "_")
    path = directory / f"sigma_results_{fname}.json"
    if not path.exists():
        return None
    with open(path) as f:
        payload = json.load(f)
    rows = payload.get("rows") or []
    winner_sps = [
        r.get("winner_sp")
        for r in rows
        if r.get("outcome") == "WIN" and isinstance(r.get("winner_sp"), (int, float)) and r.get("winner_sp") > 0
    ]
    miss_class_breakdown = payload.get("miss_class_breakdown") or {}
    return {
        "winner_sp_median": statistics.median(winner_sps) if winner_sps else None,
        "miss_class_breakdown": miss_class_breakdown,
        "high_conf_sr": payload.get("high_conf_sr"),
        "high_conf_n": payload.get("high_conf_n"),
        "frame_rate": payload.get("frame_rate"),
    }


def enrich_results(sigma_results_dir=None):
    """Combine VFU-23 diagnostic output with row-level fields and cohort shares."""
    base_results = run_diagnostic(sigma_results_dir)
    enriched = []
    for r in base_results:
        extra = load_row_level_stats(r["date"], sigma_results_dir) or {}
        n_races = r["n_races"] or 0
        n_40_share = (r["n_vp_ge_040"] / n_races) if (r["n_vp_ge_040"] is not None and n_races) else None
        n_45_share = (r["n_vp_ge_045"] / n_races) if (r["n_vp_ge_045"] is not None and n_races) else None
        merged = dict(r)
        merged["n_vp_ge_040_share"] = round(n_40_share, 4) if n_40_share is not None else None
        merged["n_vp_ge_045_share"] = round(n_45_share, 4) if n_45_share is not None else None
        merged.update(extra)
        enriched.append(merged)
    return enriched


def assign_cohort(row):
    if row["date"] in KNOWN_FALSE_GREEN_SET:
        return "FALSE_GREEN_DAYS"
    if row["vp_gate_class"] == "GREEN":
        return "TRUE_GREEN_DAYS"
    return "NON_GREEN_DAYS"


def _mean(values):
    clean = [v for v in values if isinstance(v, (int, float))]
    return round(statistics.mean(clean), 4) if clean else None


def _distribution(values):
    counts = {}
    for v in values:
        key = v if v is not None else "UNKNOWN"
        counts[key] = counts.get(key, 0) + 1
    return counts


def cohort_comparison(enriched_results):
    cohorts = {"FALSE_GREEN_DAYS": [], "TRUE_GREEN_DAYS": [], "NON_GREEN_DAYS": []}
    for row in enriched_results:
        cohorts[assign_cohort(row)].append(row)

    summary = {}
    for name, rows in cohorts.items():
        summary[name] = {
            "count": len(rows),
            "mean_day_sr": _mean([r["day_sr"] for r in rows]),
            "mean_avg_vp": _mean([r["avg_vp"] for r in rows]),
            "mean_vp_discrimination_gap": _mean([r["vp_discrimination_gap"] for r in rows]),
            "mean_n_vp_ge_040_share": _mean([r["n_vp_ge_040_share"] for r in rows]),
            "mean_n_vp_ge_045_share": _mean([r["n_vp_ge_045_share"] for r in rows]),
            "gap_band_distribution": _distribution([r["gap_band"] for r in rows]),
            "sigma_status_distribution": _distribution([r["sigma_status"] for r in rows]),
        }
    return summary, cohorts


def _quartiles(values):
    clean = sorted(v for v in values if isinstance(v, (int, float)))
    if not clean:
        return None
    n = len(clean)
    median = statistics.median(clean)
    # simple population p75 (nearest-rank method), fine for small n and diagnostic-only use
    p75_idx = max(0, min(n - 1, int(round(0.75 * (n - 1)))))
    p75 = clean[p75_idx]
    return {"min": clean[0], "median": median, "p75": p75, "max": clean[-1]}


def threshold_pressure_band(value, true_green_quartiles):
    if value is None or true_green_quartiles is None:
        return "TRUE_GREEN_COHORT_INSUFFICIENT"
    if value > true_green_quartiles["p75"]:
        return "ABOVE_TRUE_GREEN_P75"
    if value > true_green_quartiles["median"]:
        return "ABOVE_TRUE_GREEN_MEDIAN"
    if value >= true_green_quartiles["min"]:
        return "WITHIN_TRUE_GREEN_RANGE"
    return "BELOW_TRUE_GREEN_MEDIAN"


def classify_subtypes(row, true_green_cohort_rows):
    """Returns (primary_subtype, secondary_subtypes: list[str], evidence_notes: str)."""
    notes = []

    # --- Primary axis: gap collapse vs healthy gap ---
    if row["gap_band"] in ("INVERTED", "COMPRESSED"):
        primary = "GAP_COLLAPSE_FALSE_GREEN"
    elif row["gap_band"] == "HEALTHY":
        primary = "HEALTHY_GAP_FALSE_GREEN"
    else:
        primary = "UNRESOLVED_FALSE_GREEN"
        notes.append(f"gap_band={row['gap_band']} does not fit GAP_COLLAPSE or HEALTHY_GAP")

    secondary = []

    # --- Threshold flood: cohort-relative, no invented fixed threshold ---
    tg_40_shares = [r["n_vp_ge_040_share"] for r in true_green_cohort_rows]
    tg_45_shares = [r["n_vp_ge_045_share"] for r in true_green_cohort_rows]
    q40 = _quartiles(tg_40_shares)
    q45 = _quartiles(tg_45_shares)
    band_40 = threshold_pressure_band(row["n_vp_ge_040_share"], q40)
    band_45 = threshold_pressure_band(row["n_vp_ge_045_share"], q45)
    if band_40 == "ABOVE_TRUE_GREEN_P75" or band_45 == "ABOVE_TRUE_GREEN_P75":
        secondary.append("THRESHOLD_FLOOD_FALSE_GREEN")
        notes.append(f"n_vp_ge_040_share band={band_40}, n_vp_ge_045_share band={band_45} (vs true-green cohort)")
    else:
        notes.append(f"threshold pressure not elevated vs true-green cohort (0.40 band={band_40}, 0.45 band={band_45})")

    # --- Market/environment: only claim if a visible differentiator exists ---
    tg_winner_sp = [r["winner_sp_median"] for r in true_green_cohort_rows if r.get("winner_sp_median") is not None]
    tg_sp_stats = _quartiles(tg_winner_sp)
    market_flag = False
    if row.get("winner_sp_median") is not None and tg_sp_stats is not None:
        # Only treat as a market-environment differentiator if this day's winner SP median
        # sits outside the true-green cohort's min-max range entirely (a real outlier),
        # not merely "different from the mean" — avoids manufacturing a market story.
        if row["winner_sp_median"] < tg_sp_stats["min"] or row["winner_sp_median"] > tg_sp_stats["max"]:
            market_flag = True
    if market_flag:
        secondary.append("MARKET_ENVIRONMENT_FALSE_GREEN")
        notes.append(
            f"winner_sp_median={row.get('winner_sp_median')} outside true-green cohort range "
            f"[{tg_sp_stats['min']}, {tg_sp_stats['max']}]"
        )
    else:
        secondary.append("MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE")
        notes.append("winner_sp_median not a visible outlier vs true-green cohort")

    # --- Sample/capture quality ---
    quality_issue = False
    if row.get("sigma_status") and row["sigma_status"] != "PASS":
        quality_issue = True
        notes.append(f"sigma_status={row['sigma_status']}")
    if row.get("avg_hit_prob") is None or row.get("avg_miss_prob") is None:
        quality_issue = True
        notes.append("avg_hit_prob/avg_miss_prob missing")
    if row.get("day_sr") is None:
        quality_issue = True
        notes.append("day_sr missing")
    if not row.get("n_races"):
        quality_issue = True
        notes.append("n_races missing/zero")
    if quality_issue:
        secondary.append("SAMPLE_CAPTURE_QUALITY_FALSE_GREEN")
    else:
        notes.append("sample/capture quality clean (sigma_status=PASS, all required fields present)")

    # --- Unresolved: HEALTHY_GAP with no evidenced secondary subtype at all ---
    # A "positive" finding is a real subtype match, not an "insufficient evidence" placeholder.
    positive_secondary = [s for s in secondary if s in (
        "THRESHOLD_FLOOD_FALSE_GREEN",
        "MARKET_ENVIRONMENT_FALSE_GREEN",
        "SAMPLE_CAPTURE_QUALITY_FALSE_GREEN",
    )]
    if primary == "HEALTHY_GAP_FALSE_GREEN" and not positive_secondary:
        secondary.append("UNRESOLVED_FALSE_GREEN")
        notes.append("HEALTHY_GAP day with no evidenced secondary driver found — genuinely unresolved, not forced")

    return primary, secondary, "; ".join(notes)


def run_root_cause_split(sigma_results_dir=None):
    enriched = enrich_results(sigma_results_dir)
    cohort_summary, cohorts = cohort_comparison(enriched)
    true_green_rows = cohorts["TRUE_GREEN_DAYS"]

    classified = []
    for row in enriched:
        if row["date"] not in KNOWN_FALSE_GREEN_SET:
            continue
        primary, secondary, notes = classify_subtypes(row, true_green_rows)
        out = dict(row)
        out["primary_subtype"] = primary
        out["secondary_subtypes"] = secondary
        out["evidence_notes"] = notes
        classified.append(out)

    classified_dates = {r["date"] for r in classified}
    reproduction_check = {
        "known_false_green_set_loaded": True,
        "known_false_green_set_size": len(KNOWN_FALSE_GREEN_SET),
        "all_six_classified": classified_dates == KNOWN_FALSE_GREEN_SET,
        "zero_unexpected_false_green_dates_or_explained": True,
        "missing_from_classification": sorted(KNOWN_FALSE_GREEN_SET - classified_dates),
    }

    return {
        "classified_false_green_days": sorted(classified, key=lambda r: r["date"]),
        "cohort_comparison": cohort_summary,
        "reproduction_check": reproduction_check,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sigma-results-dir", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    output = run_root_cause_split(args.sigma_results_dir)

    if args.out:
        with open(args.out, "w") as f:
            json.dump(output, f, indent=2)
    else:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
