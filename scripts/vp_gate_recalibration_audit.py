"""
vp_gate_recalibration_audit.py

Tests VP gate thresholds against the sidecar training dataset.
Compares static thresholds, dynamic gates (class/field/SP/Racing API enrichment),
and returns a recommendation.

Input:  data/sidecar_training_dataset_v1.csv  (from build_sidecar_training_dataset.py)
Output: data/vp_gate_recalibration_audit_latest.json
        data/vp_gate_recalibration_audit_latest.md

Usage:
    PYTHONPATH=. python scripts/vp_gate_recalibration_audit.py
    PYTHONPATH=. python scripts/vp_gate_recalibration_audit.py --csv data/sidecar_training_dataset_v1.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def _load(csv_path: Path) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        try:
            vp = float(r["velo_prime_prob"]) if r.get("velo_prime_prob") else None
            win = int(r["is_winner"]) if r.get("is_winner") != "" else None
            placed = int(r["placed"]) if r.get("placed") != "" else None
            sp = float(r["sp_dec"]) if r.get("sp_dec") else None
            pnl = float(r["flat_profit_loss"]) if r.get("flat_profit_loss") else None
        except (ValueError, TypeError):
            continue
        if vp is None or win is None:
            continue
        r["_vp"] = vp
        r["_win"] = win
        r["_placed"] = placed or 0
        r["_sp"] = sp
        r["_pnl"] = pnl
        out.append(r)
    return out


def _metrics(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0, "sr": None, "frame": None, "roi": None, "avg_sp": None}
    wins = sum(r["_win"] for r in rows)
    placed = sum(r["_placed"] for r in rows)
    pnls = [r["_pnl"] for r in rows if r["_pnl"] is not None]
    sps = [r["_sp"] for r in rows if r["_sp"] is not None]
    return {
        "n": n,
        "sr": round(100 * wins / n, 2),
        "frame": round(100 * placed / n, 2),
        "roi": round(sum(pnls) / len(pnls), 4) if pnls else None,
        "avg_sp": round(statistics.mean(sps), 2) if sps else None,
    }


def _gate_analysis(rows: list[dict], threshold: float, split: str | None = None) -> dict:
    if split:
        rows = [r for r in rows if r.get("split") == split]
    filtered = [r for r in rows if r["_vp"] >= threshold]
    return _metrics(filtered)


def _recommend(gate_results: dict, all_rows: list[dict]) -> str:
    """Derive recommendation from gate analysis results."""
    full_data = gate_results.get("all", {})
    vp25 = full_data.get(0.25, {})
    vp30 = full_data.get(0.30, {})
    vp35 = full_data.get(0.35, {})

    # Check sample size
    if vp30.get("n", 0) < 30:
        return "UNDER_CALIBRATION"

    # If VP25 shows better SR AND ROI vs VP30, recommend lower gate
    if (vp25.get("sr", 0) or 0) > (vp30.get("sr", 0) or 0) and \
       (vp25.get("roi") or -99) > (vp30.get("roi") or -99):
        return "LOWER_GATE"

    # If VP35 ROI significantly better, suggest raising
    vp30_roi = vp30.get("roi") or -99
    vp35_roi = vp35.get("roi") or -99
    if vp35_roi > vp30_roi + 0.05 and (vp35.get("n") or 0) >= 30:
        return "RAISE_GATE"

    return "KEEP_VP30"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="data/sidecar_training_dataset_v1.csv")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found. Run build_sidecar_training_dataset.py first.")
        return

    print("=== VP Gate Recalibration Audit ===")
    rows = _load(csv_path)
    print(f"Loaded: {len(rows)} resolved rows")
    if not rows:
        print("ERROR: No rows loaded.")
        return

    baseline = _metrics(rows)
    print(f"Overall baseline: n={baseline['n']} SR={baseline['sr']}% frame={baseline['frame']}% ROI={baseline['roi']}")

    thresholds = [0.20, 0.25, 0.28, 0.30, 0.32, 0.35, 0.40]
    splits = ["all", "train", "validation", "test"]

    gate_results: dict = {}

    print("\n--- Static VP Gate Analysis ---")
    print(f"{'Split':<14} {'Gate':>6} {'n':>6} {'SR%':>7} {'Frame%':>8} {'ROI':>8} {'AvgSP':>7}")
    print("-" * 60)

    for sp_name in splits:
        sp_rows = rows if sp_name == "all" else [r for r in rows if r.get("split") == sp_name]
        gate_results[sp_name] = {}
        for th in thresholds:
            filtered = [r for r in sp_rows if r["_vp"] >= th]
            m = _metrics(filtered)
            gate_results[sp_name][th] = m
            if sp_name in ("all", "test"):
                roi_str = f"{m['roi']:+.4f}" if m["roi"] is not None else "  N/A "
                print(f"{sp_name:<14} {th:>6.2f} {m['n']:>6} {(m['sr'] or 0):>7.1f} {(m['frame'] or 0):>8.1f} {roi_str:>8} {(m['avg_sp'] or 0):>7.1f}")

    print("\n--- Dynamic Gate: By Class ---")
    class_results: dict = {}
    for cls_group, cls_values in [("Class1-2", ["Class 1","Class 2"]),
                                   ("Class3-4", ["Class 3","Class 4"]),
                                   ("Class5-7", ["Class 5","Class 6","Class 7"])]:
        cls_rows = [r for r in rows if r.get("race_class","") in cls_values]
        vp30_cls = [r for r in cls_rows if r["_vp"] >= 0.30]
        m = _metrics(vp30_cls)
        class_results[cls_group] = m
        roi_str = f"{m['roi']:+.4f}" if m["roi"] is not None else "  N/A "
        print(f"  {cls_group:<14} VP30: n={m['n']:>4} SR={m['sr'] or 0:.1f}% ROI={roi_str}")

    print("\n--- Dynamic Gate: By Field Size ---")
    field_results: dict = {}
    for grp, lo, hi in [("small<8", 0, 7), ("medium8-12", 8, 12), ("large>12", 13, 99)]:
        fs_rows = [r for r in rows
                   if r.get("field_size") and lo <= int(r["field_size"] or 0) <= hi]
        vp30_fs = [r for r in fs_rows if r["_vp"] >= 0.30]
        m = _metrics(vp30_fs)
        field_results[grp] = m
        roi_str = f"{m['roi']:+.4f}" if m["roi"] is not None else "  N/A "
        print(f"  {grp:<14} VP30: n={m['n']:>4} SR={m['sr'] or 0:.1f}% ROI={roi_str}")

    print("\n--- Dynamic Gate: By SP Band ---")
    sp_results: dict = {}
    for grp, lo, hi in [("<4.0", 0, 3.99), ("4-8", 4.0, 7.99), ("8-16", 8.0, 15.99), (">16", 16.0, 9999)]:
        sp_rows = [r for r in rows
                   if r["_sp"] is not None and lo <= r["_sp"] <= hi]
        vp30_sp = [r for r in sp_rows if r["_vp"] >= 0.30]
        m = _metrics(vp30_sp)
        sp_results[grp] = m
        roi_str = f"{m['roi']:+.4f}" if m["roi"] is not None else "  N/A "
        print(f"  SP {grp:<10} VP30: n={m['n']:>4} SR={m['sr'] or 0:.1f}% ROI={roi_str}")

    print("\n--- Dynamic Gate: VP30 + Racing API Enrichment ---")
    enrich_results: dict = {}
    # Baseline VP30
    vp30_base = [r for r in rows if r["_vp"] >= 0.30]
    m_base = _metrics(vp30_base)

    # VP30 + trainer_course_win_pct > 15%
    vp30_tc = [r for r in vp30_base
               if r.get("trainer_course_win_pct") and float(r["trainer_course_win_pct"] or 0) > 0.15]
    m_tc = _metrics(vp30_tc)

    # VP30 + jockey_dist_win_pct > 15%
    vp30_jd = [r for r in vp30_base
               if r.get("jockey_dist_win_pct") and float(r["jockey_dist_win_pct"] or 0) > 0.15]
    m_jd = _metrics(vp30_jd)

    # VP30 + trainer_jockey_win_pct > 15%
    vp30_tj = [r for r in vp30_base
               if r.get("trainer_jockey_win_pct") and float(r["trainer_jockey_win_pct"] or 0) > 0.15]
    m_tj = _metrics(vp30_tj)

    enrich_results = {
        "vp30_baseline": m_base,
        "vp30_trainer_course_gt15": m_tc,
        "vp30_jockey_dist_gt15": m_jd,
        "vp30_trainer_jockey_gt15": m_tj,
    }

    for label, m in enrich_results.items():
        roi_str = f"{m['roi']:+.4f}" if m["roi"] is not None else "  N/A "
        print(f"  {label:<30} n={m['n']:>4} SR={m['sr'] or 0:.1f}% frame={m['frame'] or 0:.1f}% ROI={roi_str}")

    # Recommendation
    recommendation = _recommend(gate_results, rows)
    print(f"\n=== RECOMMENDATION: {recommendation} ===")

    # Assess Racing API impact
    api_win_lift = None
    api_frame_lift = None
    api_roi_lift = None
    if m_tc["n"] >= 10 and m_base["n"] >= 10:
        api_win_lift = (m_tc["sr"] or 0) - (m_base["sr"] or 0)
        api_frame_lift = (m_tc["frame"] or 0) - (m_base["frame"] or 0)
        if m_tc["roi"] is not None and m_base["roi"] is not None:
            api_roi_lift = m_tc["roi"] - m_base["roi"]

    api_improves_win = api_win_lift is not None and api_win_lift > 0
    api_improves_frame = api_frame_lift is not None and api_frame_lift > 0
    api_improves_roi = api_roi_lift is not None and api_roi_lift > 0
    print(f"Racing API trainer_course enrichment:")
    print(f"  WIN lift:   {api_win_lift:+.1f}pp  → {'YES' if api_improves_win else 'NO/INSUFFICIENT'}")
    print(f"  FRAME lift: {api_frame_lift:+.1f}pp  → {'YES' if api_improves_frame else 'NO/INSUFFICIENT'}")
    print(f"  ROI lift:   {api_roi_lift:+.4f}  → {'YES' if api_improves_roi else 'NO/INSUFFICIENT'}" if api_roi_lift is not None else "  ROI: INSUFFICIENT DATA")

    # Sidecar tier table
    tier_table = {
        "sqpe_v17": "TIER 5 — LIVE_WEIGHT_CANDIDATE (active in SQPE_IMPROVEMENT_MDS_V1)",
        "improvement_score": "TIER 5 — LIVE_WEIGHT_CANDIDATE (active in SQPE_IMPROVEMENT_MDS_V1)",
        "market_deception_score": "TIER 5 — LIVE_WEIGHT_CANDIDATE (active in SQPE_IMPROVEMENT_MDS_V1)",
        "place_prob": "TIER 2 — SHADOW_SCORED / BADGE_ONLY (frozen from live VP, 2026-05-08)",
        "longshot_score": "TIER 2 — SHADOW_SCORED / FROZEN (FREEZE_CANDIDATE, ROI=-6.5%)",
        "release_day_prob": "TIER 1 — OPERATOR_VISIBLE (feature pipeline not wired)",
        "comment_intel_score": "TIER 1 — OPERATOR_VISIBLE (feature pipeline not wired)",
        "trainer_course_stats": "TIER 3 — CALIBRATION_TEST (in full_analysis, needs evidence gate)",
        "trainer_dist_stats": "TIER 3 — CALIBRATION_TEST (in full_analysis, needs evidence gate)",
        "jockey_course_stats": "TIER 2 — SHADOW_SCORED (Supabase live, calibration pending)",
        "jockey_dist_stats": "TIER 2 — SHADOW_SCORED (Supabase live, calibration pending)",
        "trainer_jockey_combo": "TIER 2 — SHADOW_SCORED (Supabase live, calibration pending)",
        "rpdc_score": "TIER 2 — SHADOW_SCORED (field mapping fixed 2026-05-08, observability only)",
    }

    # Build output
    result = {
        "generated_at": datetime.now().isoformat(),
        "dataset": str(csv_path),
        "total_rows": len(rows),
        "baseline": baseline,
        "gate_analysis": {sp: {str(th): m for th, m in thresholds_dict.items()}
                         for sp, thresholds_dict in gate_results.items()},
        "class_analysis": class_results,
        "field_size_analysis": field_results,
        "sp_band_analysis": sp_results,
        "enrichment_analysis": enrich_results,
        "recommendation": recommendation,
        "racing_api_improves_win": api_improves_win,
        "racing_api_improves_frame": api_improves_frame,
        "racing_api_improves_roi": api_improves_roi,
        "sidecar_tier_table": tier_table,
    }

    json_path = Path("data/vp_gate_recalibration_audit_latest.json")
    json_path.write_text(json.dumps(result, indent=2))
    print(f"Written: {json_path}")

    # MD report
    md_lines = [
        "# VP Gate Recalibration Audit",
        f"Generated: {result['generated_at']}",
        f"Dataset: {csv_path} ({len(rows)} rows)",
        "",
        f"## Recommendation: **{recommendation}**",
        "",
        "## VP Gate Comparison (all splits)",
        f"| Gate | n | SR% | Frame% | ROI | AvgSP |",
        f"|---|---|---|---|---|---|",
    ]
    for th in thresholds:
        m = gate_results["all"].get(th, {})
        roi_str = f"{m['roi']:+.4f}" if m.get("roi") is not None else "—"
        md_lines.append(f"| ≥{th:.2f} | {m.get('n',0)} | {m.get('sr',0):.1f}% | {m.get('frame',0):.1f}% | {roi_str} | {m.get('avg_sp',0):.1f} |")

    md_lines += [
        "",
        "## Racing API Enrichment at VP30",
        f"| Filter | n | SR% | Frame% | ROI |",
        f"|---|---|---|---|---|",
    ]
    for label, m in enrich_results.items():
        roi_str = f"{m['roi']:+.4f}" if m.get("roi") is not None else "—"
        md_lines.append(f"| {label} | {m.get('n',0)} | {(m.get('sr') or 0):.1f}% | {(m.get('frame') or 0):.1f}% | {roi_str} |")

    md_lines += [
        "",
        "## Racing API Signal Assessment",
        f"- Improves WIN probability: {'YES' if api_improves_win else 'NO/INSUFFICIENT DATA'}",
        f"- Improves FRAME rate: {'YES' if api_improves_frame else 'NO/INSUFFICIENT DATA'}",
        f"- Improves ROI: {'YES' if api_improves_roi else 'NO/INSUFFICIENT DATA'}",
        "",
        "## Sidecar Tier Table",
        f"| Component | Tier |",
        f"|---|---|",
    ]
    for comp, tier in tier_table.items():
        md_lines.append(f"| {comp} | {tier} |")

    md_lines += [
        "",
        "## VP Gate Recalibration Status",
        "VP gate threshold is **UNDER_CALIBRATION** due to Ensemble Surgery v1 VP compression.",
        "Average VP dropped ~0.05 (improvement_score raw values lower than place_prob).",
        "Collect 30 live sigma days before changing VP30 threshold.",
        "",
        "**DO NOT change VP thresholds until 30-day monitoring period completes (~2026-06-08).**",
    ]

    md_path = Path("data/vp_gate_recalibration_audit_latest.md")
    md_path.write_text("\n".join(md_lines))
    print(f"Written: {md_path}")


if __name__ == "__main__":
    main()
