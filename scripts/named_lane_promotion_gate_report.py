#!/usr/bin/env python3
"""
NAMED_LANE_PROMOTION_GATE_REPORT_V1

Applies 7-gate promotion gate analysis to each named signal lane.
Reads outcome tracker data + training corpus for subgroup analysis.

Governance:
  No scoring change | No model change | No router change | No staking | Advisory only

Gate logic (all gates must pass for promotion eligibility):
  Gate 1: n >= 50 minimum viable evidence
  Gate 2: n >= 100 for serious policy review
  Gate 3: SR materially above baseline (>15pp over ~20% random)
  Gate 4: Frame rate >= 70%
  Gate 5: ROI not negative
  Gate 6: Losing-run risk acceptable (LLR <= n * 0.25)
  Gate 7: No contradictory subgroup collapse (no class/course group SR < lane SR - 20pp at n>=10)

Outputs:
    data/reports/named_lane_promotion_gate_report_latest.json
    data/reports/named_lane_promotion_gate_report_latest.md

Usage:
    python scripts/named_lane_promotion_gate_report.py [--date YYYY-MM-DD]
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS_DIR = DATA / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

PARQUET_PATH = DATA / "training" / "sigma_2k_training_dataset_latest.parquet"
TRACKER_PATH = REPORTS_DIR / "named_lane_outcome_tracker_latest.json"

GLOBAL_SR_BASELINE = 20.0
SR_LIFT_FLOOR = 15.0
FRAME_FLOOR = 70.0
SUBGROUP_COLLAPSE_PP = 20.0
SUBGROUP_MIN_N = 10

# Promotion verdict thresholds
VERDICT_THRESHOLDS = {
    "SHADOW_POLICY_CANDIDATE": {"n_min": 100, "sr_floor": 35.0, "frame_floor": 70.0, "roi_floor": 0.0},
    "EARLY_REVIEW_READY":       {"n_min": 50,  "sr_floor": 30.0, "frame_floor": 65.0, "roi_floor": None},
    "INSUFFICIENT_N":           {"n_min": 0,   "sr_floor": 0.0,  "frame_floor": 0.0,  "roi_floor": None},
}


def _load_tracker() -> dict[str, dict]:
    if not TRACKER_PATH.exists():
        return {}
    try:
        data = json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
        return {lane["lane"]: lane for lane in data.get("lanes", [])}
    except Exception:
        return {}


def _load_corpus() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET_PATH)
    df = df[df["result_matched"] == True].copy()
    for col in ["velo_prime_prob", "market_deception_score", "improvement_score",
                "place_prob", "sp_decimal"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["won"] = df["won"].fillna(False).astype(bool)
    df["placed"] = df["placed"].fillna(False).astype(bool)
    df["router_qualified"] = (
        df.get("router_v1_shadow_pass", False)
        | df.get("router_v2_class4_shadow_pass", False)
        | df.get("router_v6_gold_seam_watchlist", False)
    ).fillna(False).astype(bool)
    return df


def _apply_lane_filter(df: pd.DataFrame, lane_name: str) -> pd.DataFrame:
    vp = df["velo_prime_prob"]
    mds = df["market_deception_score"]
    imp = df["improvement_score"]
    sp = df["sp_decimal"]
    tier = df["decision_tier"]
    rq = df["router_qualified"]
    if lane_name == "MDS_HIGH_LANE":
        return df[(vp >= 0.30) & (mds > 0.50)]
    if lane_name == "IMPROVER_LANE":
        return df[(vp >= 0.30) & (imp > 0.40)]
    if lane_name == "VP40_LANE":
        return df[vp >= 0.40]
    if lane_name == "VP40_TIER_A_LANE":
        return df[(vp >= 0.40) & (tier == "A")]
    if lane_name == "SHORTFAV_VP30":
        return df[(sp < 3.0) & (vp >= 0.30)]
    if lane_name == "MIDPRICE_ROUTER_QUAL":
        return df[(sp >= 3.0) & (sp <= 8.5) & rq]
    if lane_name == "MIDPRICE_SUPPRESS":
        return df[(sp >= 3.0) & (sp <= 8.5) & ~rq]
    if lane_name == "LONGSHOT_SUPPRESS":
        return df[sp > 8.5]
    return df


def _subgroup_analysis(df_lane: pd.DataFrame, lane_sr: float) -> dict:
    """Check for subgroup collapses in class and course breakdowns."""
    collapses = []
    subgroups = []

    if "class_num" in df_lane.columns:
        for cls, grp in df_lane.groupby("class_num"):
            if len(grp) < SUBGROUP_MIN_N:
                continue
            g_sr = round(grp["won"].sum() / len(grp) * 100, 1)
            g_n = len(grp)
            subgroups.append({"group": f"Class {int(cls)}", "n": g_n, "sr": g_sr})
            if g_sr < lane_sr - SUBGROUP_COLLAPSE_PP:
                collapses.append({"group": f"Class {int(cls)}", "n": g_n, "sr": g_sr, "gap_pp": round(lane_sr - g_sr, 1)})

    if "course" in df_lane.columns:
        course_groups = df_lane.groupby("course").filter(lambda g: len(g) >= SUBGROUP_MIN_N)
        for course, grp in course_groups.groupby("course"):
            g_sr = round(grp["won"].sum() / len(grp) * 100, 1)
            g_n = len(grp)
            subgroups.append({"group": str(course), "n": g_n, "sr": g_sr})
            if g_sr < lane_sr - SUBGROUP_COLLAPSE_PP:
                collapses.append({"group": str(course), "n": g_n, "sr": g_sr, "gap_pp": round(lane_sr - g_sr, 1)})

    return {"collapses": collapses, "subgroups": subgroups[:20]}


def _evaluate_gates(lane_stats: dict, df_lane: pd.DataFrame) -> dict:
    n = lane_stats.get("n", 0)
    sr = lane_stats.get("sr", 0.0)
    frame_rate = lane_stats.get("frame_rate", 0.0)
    roi = lane_stats.get("roi")
    llr = lane_stats.get("longest_losing_run", 0)
    llr_pct = (llr / n * 100) if n > 0 else 0

    g1 = n >= 50
    g2 = n >= 100
    g3 = sr >= (GLOBAL_SR_BASELINE + SR_LIFT_FLOOR)
    g4 = frame_rate >= FRAME_FLOOR
    g5 = roi is not None and roi >= 0.0
    g6 = llr_pct <= 25.0

    subgroup = _subgroup_analysis(df_lane, sr)
    g7 = len(subgroup["collapses"]) == 0

    gates = {
        "gate_1_n50":       {"pass": g1, "value": n, "required": 50,          "label": "Min evidence n≥50"},
        "gate_2_n100":      {"pass": g2, "value": n, "required": 100,         "label": "Serious review n≥100"},
        "gate_3_sr_lift":   {"pass": g3, "value": round(sr, 1), "required": round(GLOBAL_SR_BASELINE + SR_LIFT_FLOOR, 1), "label": f"SR lift ≥{SR_LIFT_FLOOR}pp over {GLOBAL_SR_BASELINE}% baseline"},
        "gate_4_frame":     {"pass": g4, "value": round(frame_rate, 1), "required": FRAME_FLOOR, "label": f"Frame rate ≥{FRAME_FLOOR}%"},
        "gate_5_roi":       {"pass": g5, "value": roi, "required": 0.0,       "label": "ROI not negative"},
        "gate_6_llr":       {"pass": g6, "value": round(llr_pct, 1), "required": 25.0, "label": "LLR ≤25% of n"},
        "gate_7_subgroup":  {"pass": g7, "value": len(subgroup["collapses"]), "required": 0, "label": "No subgroup collapse"},
    }

    gates_passed = sum(1 for g in gates.values() if g["pass"])
    gates_total = len(gates)

    if not g1:
        verdict = "INSUFFICIENT_N"
        next_step = f"Accumulate +{50 - n} more results to n=50"
    elif gates_passed == gates_total:
        if g2:
            verdict = "SHADOW_POLICY_CANDIDATE"
        else:
            verdict = "EARLY_REVIEW_READY"
        next_step = "All gates passed — operator promotion discussion required"
    else:
        blocked = [f"Gate {k.replace('gate_', '').split('_')[0]}: {v['label']}" for k, v in gates.items() if not v["pass"]]
        verdict = "GATE_BLOCKED"
        next_step = f"Blocked by: {'; '.join(blocked[:3])}"

    return {
        "gates": gates,
        "gates_passed": gates_passed,
        "gates_total": gates_total,
        "verdict": verdict,
        "next_step": next_step,
        "subgroup": subgroup,
    }


def _build_md(results: list[dict], date: str, run_ts: str) -> str:
    lines = [
        "# NAMED LANE PROMOTION GATE REPORT",
        f"**Date:** {date}",
        f"**Run:** {run_ts}",
        "",
        "7-gate promotion gate analysis. Advisory only. No automatic promotion.",
        "All promotions are operator decisions.",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Lane | n | SR | Gates | Verdict |",
        "|---|---|---|---|---|",
    ]

    for r in results:
        gs = r["gate_analysis"]
        verdict = gs["verdict"]
        gate_str = f"{gs['gates_passed']}/{gs['gates_total']}"
        lines.append(f"| {r['lane']} | {r['n']} | {r['sr']}% | {gate_str} | **{verdict}** |")
    lines.append("")

    # Per-lane gate detail
    for r in results:
        gs = r["gate_analysis"]
        lines += [
            f"## {r['lane']}",
            "",
            f"**Verdict: {gs['verdict']}**",
            f"*{gs['next_step']}*",
            "",
            "| Gate | Pass | Value | Required |",
            "|---|---|---|---|",
        ]
        for gate_key, gd in gs["gates"].items():
            status = "✅ PASS" if gd["pass"] else "❌ FAIL"
            val = gd["value"] if gd["value"] is not None else "—"
            lines.append(f"| {gd['label']} | {status} | {val} | {gd['required']} |")
        lines.append("")

        collapses = gs["subgroup"]["collapses"]
        if collapses:
            lines += ["**Subgroup collapses detected:**", ""]
            for c in collapses:
                lines.append(f"- {c['group']}: SR={c['sr']}% at n={c['n']} (gap={c['gap_pp']:.1f}pp below lane SR)")
            lines.append("")
        elif gs["gates"]["gate_7_subgroup"]["pass"]:
            lines.append("*No subgroup collapses detected.*")
            lines.append("")

    lines += [
        "---",
        "",
        "## Promotion Gate Definitions",
        "",
        "| Gate | Condition | Rationale |",
        "|---|---|---|",
        "| Gate 1 | n ≥ 50 | Minimum viable evidence |",
        "| Gate 2 | n ≥ 100 | Serious policy review threshold |",
        "| Gate 3 | SR ≥ 35% (15pp above 20% baseline) | Material SR lift confirmed |",
        "| Gate 4 | Frame rate ≥ 70% | Frame coverage healthy |",
        "| Gate 5 | ROI ≥ 0% | Not losing money flat-stake |",
        "| Gate 6 | LLR ≤ 25% of n | Losing-run risk acceptable |",
        "| Gate 7 | No subgroup collapse | No class/course collapses (SR gap > 20pp at n≥10) |",
        "",
        "All 7 gates must pass for SHADOW_POLICY_CANDIDATE verdict.",
        "Promotions are operator decisions only — no gate triggers automatic change.",
        "",
        "---",
        "",
        "## Governance",
        "",
        "```",
        "NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE",
        "NO_STAKING_CHANGE | NO_TELEGRAM_CHANGE | NO_PLAYBOOK_G_PROMOTION",
        "NO_LIVE_STATE_MUTATION | ADVISORY_TRACKING_ONLY",
        "```",
        "",
        "*NAMED_LANE_PROMOTION_GATE_REPORT_V1 — advisory only, no execution impact*",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    date = args.date

    print(f"NAMED LANE PROMOTION GATE REPORT V1 — {date}")
    print("=" * 60)

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    tracker = _load_tracker()
    if not tracker:
        print("  WARNING: no tracker data found — run named_lane_outcome_tracker.py first")

    df = _load_corpus()
    print(f"  Corpus rows: {len(df)} (result_matched=True)")

    results = []
    for lane_name in [
        "MDS_HIGH_LANE", "IMPROVER_LANE", "VP40_TIER_A_LANE", "VP40_LANE",
        "SHORTFAV_VP30", "MIDPRICE_ROUTER_QUAL", "MIDPRICE_SUPPRESS", "LONGSHOT_SUPPRESS"
    ]:
        lane_stats = tracker.get(lane_name) or {"n": 0, "sr": 0.0, "frame_rate": 0.0, "roi": None, "longest_losing_run": 0}
        df_lane = _apply_lane_filter(df, lane_name)
        gate_analysis = _evaluate_gates(lane_stats, df_lane)
        results.append({
            "lane": lane_name,
            "n": lane_stats.get("n", 0),
            "sr": lane_stats.get("sr", 0.0),
            "gate_analysis": gate_analysis,
        })

    # Console summary
    print(f"\n{'Lane':<24} {'n':>5} {'SR':>7} {'Gates':>7}  Verdict")
    print("-" * 70)
    for r in results:
        gs = r["gate_analysis"]
        gate_str = f"{gs['gates_passed']}/{gs['gates_total']}"
        print(f"  {r['lane']:<24} {r['n']:>5} {r['sr']:>6.1f}% {gate_str:>7}  {gs['verdict']}")

    # Candidates ready for review
    candidates = [r for r in results if r["gate_analysis"]["verdict"] in ("SHADOW_POLICY_CANDIDATE", "EARLY_REVIEW_READY")]
    if candidates:
        print(f"\nPROMOTION REVIEW CANDIDATES:")
        for c in candidates:
            print(f"  {c['lane']}: {c['gate_analysis']['verdict']} — {c['gate_analysis']['next_step']}")

    output = {
        "run_ts": run_ts,
        "date": date,
        "results": results,
        "governance": {
            "scoring_change": False,
            "model_change": False,
            "router_change": False,
            "staking_change": False,
            "telegram": False,
            "classification": "ADVISORY_TRACKING_ONLY",
        },
    }

    json_path = REPORTS_DIR / "named_lane_promotion_gate_report_latest.json"
    json_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = _build_md(results, date, run_ts)
    md_path = REPORTS_DIR / "named_lane_promotion_gate_report_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    return output


if __name__ == "__main__":
    main()
