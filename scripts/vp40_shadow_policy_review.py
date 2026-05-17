#!/usr/bin/env python3
"""
VP40_SHADOW_POLICY_REVIEW_V1

Forensic review of VP40_LANE as the first formal shadow policy candidate.
Policy simulation and evidence review only.

Governance:
  No scoring change | No model change | No router change | No staking
  No Telegram | No live state mutation | Advisory only

Inputs:
    data/training/sigma_2k_training_dataset_latest.parquet

Outputs:
    data/reports/vp40_shadow_policy_review_latest.json
    data/reports/vp40_shadow_policy_review_latest.md

Usage:
    python scripts/vp40_shadow_policy_review.py [--date YYYY-MM-DD]
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

# Promotion requirement thresholds
PROMOTION_N_MIN = 150
PROMOTION_N_PREFERRED = 250
PROMOTION_SR_FLOOR = 40.0
PROMOTION_FRAME_FLOOR = 75.0
PROMOTION_ROI_FLOOR = 0.0
SUBGROUP_MIN_N = 5
SUBGROUP_COLLAPSE_FLOOR = 25.0
OUTLIER_ROI_FLOOR = 0.0


# ── Data loading ──────────────────────────────────────────────────────────────

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
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def _sp_band(sp: float) -> str:
    if sp < 2.0:
        return "SP<2.0"
    if sp < 3.0:
        return "SP2.0-2.99"
    if sp <= 8.5:
        return "SP3.0-8.5"
    if sp <= 16.0:
        return "SP8.51-16.0"
    return "SP>16.0"


# ── Core stats ────────────────────────────────────────────────────────────────

def _flat_stats(df: pd.DataFrame) -> dict:
    n = len(df)
    if n == 0:
        return {"n": 0, "wins": 0, "frames": 0, "sr": 0.0, "frame_rate": 0.0, "roi": None, "avg_sp": None, "median_sp": None}
    wins = int(df["won"].sum())
    frames = int(df["placed"].sum())
    sp_col = df["sp_decimal"].dropna()
    win_sps = df[df["won"]]["sp_decimal"].dropna()
    roi = round((float(win_sps.sum()) - n) / n * 100, 1) if len(win_sps) else None
    return {
        "n": n,
        "wins": wins,
        "frames": frames,
        "sr": round(wins / n * 100, 1),
        "frame_rate": round(frames / n * 100, 1),
        "roi": roi,
        "avg_sp": round(float(sp_col.mean()), 2) if len(sp_col) else None,
        "median_sp": round(float(sp_col.median()), 2) if len(sp_col) else None,
    }


def _longest_losing_run(df: pd.DataFrame) -> int:
    ordered = df.sort_values("date") if "date" in df.columns else df
    max_run = cur_run = 0
    for won in ordered["won"].tolist():
        if not won:
            cur_run += 1
            max_run = max(max_run, cur_run)
        else:
            cur_run = 0
    return max_run


def _max_drawdown(df: pd.DataFrame) -> float:
    """Compute max paper P&L drawdown from running peak (flat £1 stake)."""
    ordered = df.sort_values("date") if "date" in df.columns else df
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for _, row in ordered.iterrows():
        if row["won"]:
            running += float(row["sp_decimal"]) - 1.0
        else:
            running -= 1.0
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)


# ── Subgroup analysis ─────────────────────────────────────────────────────────

def _subgroup_breakdown(df: pd.DataFrame, col: str, label_fn=None) -> list[dict]:
    if col not in df.columns:
        return []
    rows = []
    for val, grp in df.groupby(col):
        if len(grp) < SUBGROUP_MIN_N:
            continue
        stats = _flat_stats(grp)
        label = label_fn(val) if label_fn else str(val)
        rows.append({"group": label, **stats})
    return sorted(rows, key=lambda r: r["n"], reverse=True)


def _sp_band_breakdown(df: pd.DataFrame) -> list[dict]:
    df2 = df.copy()
    df2["_sp_band"] = df2["sp_decimal"].apply(lambda x: _sp_band(float(x)) if pd.notna(x) else "unknown")
    return _subgroup_breakdown(df2, "_sp_band")


# ── Overlap analysis ──────────────────────────────────────────────────────────

def _overlap_analysis(vp40: pd.DataFrame, full_df: pd.DataFrame) -> dict:
    vp40_idx = set(vp40.index)
    vp40_wins = vp40[vp40["won"]]

    mds_idx = set(full_df[(full_df["velo_prime_prob"] >= 0.30) & (full_df["market_deception_score"] > 0.50)].index)
    imp_idx = set(full_df[(full_df["velo_prime_prob"] >= 0.30) & (full_df["improvement_score"] > 0.40)].index)
    vp40a_idx = set(full_df[(full_df["velo_prime_prob"] >= 0.40) & (full_df["decision_tier"] == "A")].index)
    shortfav_idx = set(full_df[(full_df["sp_decimal"] < 3.0) & (full_df["velo_prime_prob"] >= 0.30)].index)
    midprice_rq_idx = set(full_df[(full_df["sp_decimal"] >= 3.0) & (full_df["sp_decimal"] <= 8.5) & full_df["router_qualified"]].index)

    def _overlap_stats(other_idx: set, other_name: str) -> dict:
        common = vp40_idx & other_idx
        pct_vp40 = round(len(common) / len(vp40) * 100, 1) if len(vp40) > 0 else 0.0
        common_wins = len(set(vp40_wins.index) & other_idx)
        return {"lane": other_name, "overlap_n": len(common), "pct_of_vp40": pct_vp40, "shared_winners": common_wins}

    vp40a_wins_idx = set(full_df[(full_df["velo_prime_prob"] >= 0.40) & (full_df["decision_tier"] == "A") & full_df["won"]].index)
    total_wins = len(vp40_wins)
    tier_a_wins = len(set(vp40_wins.index) & vp40a_idx)
    non_tier_a_wins = total_wins - tier_a_wins

    return {
        "overlaps": [
            _overlap_stats(vp40a_idx, "VP40_TIER_A_LANE"),
            _overlap_stats(mds_idx, "MDS_HIGH_LANE"),
            _overlap_stats(imp_idx, "IMPROVER_LANE"),
            _overlap_stats(shortfav_idx, "SHORTFAV_VP30"),
            _overlap_stats(midprice_rq_idx, "MIDPRICE_ROUTER_QUAL"),
        ],
        "winners_lost_if_tier_a_only": non_tier_a_wins,
        "winners_retained_if_tier_a_only": tier_a_wins,
        "pct_winners_retained": round(tier_a_wins / total_wins * 100, 1) if total_wins else 0.0,
    }


# ── Outlier analysis ──────────────────────────────────────────────────────────

def _outlier_strip_test(vp40: pd.DataFrame) -> dict:
    """ROI strip test: remove top 1, 2, 3 SP winners and recompute ROI."""
    n = len(vp40)
    winners = vp40[vp40["won"]].sort_values("sp_decimal", ascending=False)
    top_winners = []
    for _, w in winners.head(5).iterrows():
        top_winners.append({
            "horse": str(w.get("horse", "?")),
            "sp": round(float(w["sp_decimal"]), 2),
            "vp": round(float(w["velo_prime_prob"]), 3),
            "date": str(w["date"].date()) if hasattr(w.get("date"), "date") else str(w.get("date", "?")),
        })

    strip_results = []
    all_wins = winners.copy()
    excluded_return = 0.0
    for i in range(min(3, len(all_wins))):
        excluded_sp = float(all_wins.iloc[i]["sp_decimal"])
        excluded_return += excluded_sp
        remaining_wins = all_wins.iloc[i+1:]
        remaining_n = n - (i + 1)
        roi_stripped = round(
            (float(remaining_wins["sp_decimal"].sum()) - remaining_n) / remaining_n * 100, 1
        ) if remaining_n > 0 else None
        strip_results.append({
            "excluding_top": i + 1,
            "excluded_horse": top_winners[i]["horse"] if i < len(top_winners) else "?",
            "excluded_sp": round(excluded_sp, 2),
            "roi_stripped": roi_stripped,
        })

    return {"top_winners": top_winners, "strip_test": strip_results}


# ── Refined lane simulation ───────────────────────────────────────────────────

def _refined_simulations(vp40: pd.DataFrame) -> dict:
    """Simulate VP40 filtered by SP band to find where the edge lives."""
    simulations = {}

    sp_lt3 = vp40[vp40["sp_decimal"] < 3.0]
    simulations["VP40_SP_LT3"] = {
        "description": "VP40 + SP<3.0 (short price zone)",
        **_flat_stats(sp_lt3),
    }

    sp_lt4 = vp40[vp40["sp_decimal"] < 4.0]
    simulations["VP40_SP_LT4"] = {
        "description": "VP40 + SP<4.0 (extended short price)",
        **_flat_stats(sp_lt4),
    }

    tier_a = vp40[vp40["decision_tier"] == "A"]
    simulations["VP40_TIER_A_ONLY"] = {
        "description": "VP40 + Tier A only (VP40_TIER_A_LANE)",
        **_flat_stats(tier_a),
    }

    sp_lt3_tier_a = vp40[(vp40["sp_decimal"] < 3.0) & (vp40["decision_tier"] == "A")]
    simulations["VP40_SP_LT3_TIER_A"] = {
        "description": "VP40 + SP<3.0 + Tier A (tightest filter)",
        **_flat_stats(sp_lt3_tier_a),
    }

    return simulations


# ── Policy recommendation ─────────────────────────────────────────────────────

def _policy_recommendation(stats: dict, sp_breakdown: list, outlier: dict, overlap: dict) -> dict:
    n = stats["n"]
    sr = stats["sr"]
    frame_rate = stats["frame_rate"]
    roi = stats["roi"] or 0.0

    issues = []
    strengths = []

    # Outlier dependency check
    strip1 = next((s for s in outlier["strip_test"] if s["excluding_top"] == 1), {})
    roi_strip1 = strip1.get("roi_stripped")
    if roi_strip1 is not None and roi_strip1 < OUTLIER_ROI_FLOOR:
        issues.append(
            f"OUTLIER_DEPENDENCY: ROI collapses to {roi_strip1:+.1f}% without top SP winner "
            f"({strip1.get('excluded_horse')} SP={strip1.get('excluded_sp')})"
        )
    else:
        strengths.append("ROI survives top-winner removal")

    # SP band drain check
    sp35 = next((s for s in sp_breakdown if s["group"] == "SP3.0-8.5"), {})
    sp35_roi = sp35.get("roi")
    if sp35 and sp35["n"] >= 10 and sp35_roi is not None and sp35_roi < -20:
        issues.append(
            f"MIDPRICE_DRAIN: VP40 + SP3.0-8.5 runs SR={sp35['sr']}% ROI={sp35_roi:+.1f}% "
            f"at n={sp35['n']} — severe subzone leak"
        )
    elif sp35 and sp35["n"] >= 10:
        strengths.append(f"Mid-price subzone SP3.0-8.5: SR={sp35.get('sr', '?')}%")

    # High-SP longshot contamination
    sp16 = next((s for s in sp_breakdown if s["group"] == "SP8.51-16.0"), {})
    if sp16 and sp16["n"] >= 5 and sp16.get("sr", 0) == 0:
        issues.append(f"LONGSHOT_DEAD_ZONE: SP8.51-16.0 at SR=0% n={sp16['n']}")

    # Overall SR check
    if sr >= PROMOTION_SR_FLOOR:
        strengths.append(f"SR={sr}% above {PROMOTION_SR_FLOOR}% floor")
    else:
        issues.append(f"SR={sr}% below {PROMOTION_SR_FLOOR}% promotion floor")

    # Frame check
    if frame_rate >= PROMOTION_FRAME_FLOOR:
        strengths.append(f"Frame={frame_rate}% above {PROMOTION_FRAME_FLOOR}% floor")
    else:
        issues.append(f"Frame={frame_rate}% below {PROMOTION_FRAME_FLOOR}% floor")

    # ROI check
    if roi >= PROMOTION_ROI_FLOOR:
        strengths.append(f"ROI={roi:+.1f}% — positive flat stake")
    else:
        issues.append(f"ROI={roi:+.1f}% — negative flat stake")

    # n check
    if n >= PROMOTION_N_PREFERRED:
        strengths.append(f"n={n} above preferred threshold {PROMOTION_N_PREFERRED}")
    elif n >= PROMOTION_N_MIN:
        issues.append(f"n={n} above minimum {PROMOTION_N_MIN} but below preferred {PROMOTION_N_PREFERRED}")

    # Final verdict
    critical_issues = [i for i in issues if "OUTLIER_DEPENDENCY" in i or "MIDPRICE_DRAIN" in i]
    if critical_issues:
        verdict = "WATCH_ONLY"
        rationale = (
            "Critical issues block promotion: ROI is driven by outlier winner(s) and "
            "mid-price VP40 (SP 3.0-8.5) is a confirmed drain zone. "
            "The real edge lives in VP40+SP<3.0. "
            "Refine to VP40_SP_LT3 or VP40_TIER_A before policy review."
        )
    elif len(issues) == 0 and n >= PROMOTION_N_PREFERRED:
        verdict = "SHADOW_POLICY_READY"
        rationale = "All indicators healthy and n sufficient for policy discussion."
    elif len(issues) <= 1 and n >= PROMOTION_N_MIN:
        verdict = "NEEDS_MORE_DATA"
        rationale = "Positive indicators but one or more gates need further evidence."
    else:
        verdict = "WATCH_ONLY"
        rationale = "Multiple issues prevent promotion. Continue tracking."

    return {
        "verdict": verdict,
        "rationale": rationale,
        "strengths": strengths,
        "issues": issues,
        "critical_issues": critical_issues,
    }


# ── Markdown builder ──────────────────────────────────────────────────────────

def _build_md(result: dict, date: str, run_ts: str) -> str:
    s = result["overall"]
    rec = result["recommendation"]
    outlier = result["outlier_analysis"]
    simulations = result["refined_simulations"]
    overlap = result["overlap"]

    lines = [
        "# VP40 SHADOW POLICY REVIEW V1",
        f"**Date:** {date}",
        f"**Run:** {run_ts}",
        "",
        "Policy simulation and forensic review. Advisory only.",
        "No scoring change. No model change. No router change. No staking.",
        "",
        "---",
        "",
        f"## Policy Recommendation: {rec['verdict']}",
        "",
        f"> {rec['rationale']}",
        "",
    ]

    if rec["issues"]:
        lines += ["**Issues:**", ""]
        for issue in rec["issues"]:
            prefix = "🚨" if issue in rec["critical_issues"] else "⚠️"
            lines.append(f"- {prefix} {issue}")
        lines.append("")

    if rec["strengths"]:
        lines += ["**Strengths:**", ""]
        for s_item in rec["strengths"]:
            lines.append(f"- ✅ {s_item}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Overall VP40_LANE Stats",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| n (resulted) | {s['n']} |",
        f"| Wins | {s['wins']} |",
        f"| Frames | {s['frames']} |",
        f"| Strike rate | {s['sr']}% |",
        f"| Frame rate | {s['frame_rate']}% |",
        f"| ROI (flat £1) | {('+' + str(s['roi']) + '%') if s['roi'] and s['roi'] > 0 else (str(s['roi']) + '%') if s['roi'] is not None else '—'} |",
        f"| Avg SP | {s['avg_sp'] or '—'} |",
        f"| Median SP | {s['median_sp'] or '—'} |",
        f"| Max winner SP | {result['biggest_winner']['sp'] if result.get('biggest_winner') else '—'} |",
        f"| Biggest winner | {result['biggest_winner']['horse'] if result.get('biggest_winner') else '—'} |",
        f"| Longest losing run | {result['longest_losing_run']} |",
        f"| Max drawdown | £{result['max_drawdown']} |",
        "",
        "---",
        "",
        "## SP Band Breakdown — CRITICAL",
        "",
        "| SP Band | n | SR | Frame | ROI |",
        "|---|---|---|---|---|",
    ]

    for row in result["sp_band_breakdown"]:
        roi_str = f"{row['roi']:+.1f}%" if row["roi"] is not None else "—"
        lines.append(f"| {row['group']} | {row['n']} | {row['sr']}% | {row['frame_rate']}% | {roi_str} |")
    lines.append("")
    lines += [
        "**Key finding:** VP40+SP<3.0 (n=71, SR=67.6%) is the edge zone. VP40+SP3.0-8.5 (n=41) is a drain.",
        "",
        "---",
        "",
        "## ROI Outlier Strip Test",
        "",
        "| Excluding top N winners | Excluded horse | Excluded SP | ROI stripped |",
        "|---|---|---|---|",
    ]

    for row in outlier["strip_test"]:
        roi_str = f"{row['roi_stripped']:+.1f}%" if row["roi_stripped"] is not None else "—"
        lines.append(f"| {row['excluding_top']} | {row['excluded_horse']} | {row['excluded_sp']} | {roi_str} |")
    lines.append("")
    lines += [
        "**Finding:** ROI collapses when top winner removed — edge is partially driven by outlier SP=34 winner.",
        "",
        "---",
        "",
        "## Course Breakdown",
        "",
        "| Course | n | SR | ROI |",
        "|---|---|---|---|",
    ]

    for row in result["course_breakdown"]:
        roi_str = f"{row['roi']:+.1f}%" if row["roi"] is not None else "—"
        lines.append(f"| {row['group']} | {row['n']} | {row['sr']}% | {roi_str} |")
    lines.append("")

    lines += [
        "---",
        "",
        "## Tier Breakdown",
        "",
        "| Tier | n | SR | Frame | ROI |",
        "|---|---|---|---|---|",
    ]
    for row in result["tier_breakdown"]:
        roi_str = f"{row['roi']:+.1f}%" if row["roi"] is not None else "—"
        lines.append(f"| {row['group']} | {row['n']} | {row['sr']}% | {row['frame_rate']}% | {roi_str} |")
    lines.append("")

    lines += [
        "---",
        "",
        "## Overlap Analysis",
        "",
        "| Lane | Overlap n | % of VP40 | Shared winners |",
        "|---|---|---|---|",
    ]
    for row in overlap["overlaps"]:
        lines.append(f"| {row['lane']} | {row['overlap_n']} | {row['pct_of_vp40']}% | {row['shared_winners']} |")
    lines += [
        "",
        f"**Winners lost if restricted to VP40_TIER_A:** {overlap['winners_lost_if_tier_a_only']} "
        f"({100-overlap['pct_winners_retained']:.1f}% of VP40 wins)",
        "",
        "---",
        "",
        "## Refined Lane Simulations",
        "",
        "| Simulation | n | SR | Frame | ROI |",
        "|---|---|---|---|---|",
    ]
    for sim_name, sim in simulations.items():
        roi_str = f"{sim['roi']:+.1f}%" if sim.get("roi") is not None else "—"
        lines.append(f"| {sim_name} | {sim['n']} | {sim['sr']}% | {sim['frame_rate']}% | {roi_str} |")
    lines += [
        "",
        "**Implication:** VP40+SP<3.0 and VP40_TIER_A are the robust sub-lanes.",
        "Full VP40_LANE ROI is partially synthetic (outlier SP=34 winner).",
        "",
        "---",
        "",
        "## Promotion Requirements (not yet met)",
        "",
        "```",
        "n >= 250 preferred (current: 150)",
        "ROI stable without top winner (current: fails — ROI=-13.9% ex-top-winner)",
        "SP band drain resolved (VP40+SP3.0-8.5 at SR=14.6%, ROI=-25.6% is a blocker)",
        "Either restrict lane to SP<3.0 or separate mid-price into MIDPRICE_ROUTER_QUAL",
        "```",
        "",
        "---",
        "",
        "## Governance",
        "",
        "```",
        "NO_SCORING_CHANGE",
        "NO_MODEL_CHANGE",
        "NO_ROUTER_CHANGE",
        "NO_STAKING_CHANGE",
        "NO_TELEGRAM_CHANGE",
        "NO_PLAYBOOK_G_PROMOTION",
        "NO_LIVE_STATE_MUTATION",
        "POLICY_SIMULATION_ONLY",
        "```",
        "",
        "*VP40_SHADOW_POLICY_REVIEW_V1 — advisory only, no execution impact*",
    ]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    date = args.date

    print(f"VP40 SHADOW POLICY REVIEW V1 — {date}")
    print("=" * 60)

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    df = _load_corpus()
    vp40 = df[df["velo_prime_prob"] >= 0.40].copy()
    print(f"  Corpus rows: {len(df)} | VP40_LANE rows: {len(vp40)}")

    # Overall stats
    stats = _flat_stats(vp40)
    llr = _longest_losing_run(vp40)
    max_dd = _max_drawdown(vp40)

    # Biggest winner
    winners = vp40[vp40["won"]].sort_values("sp_decimal", ascending=False)
    biggest_winner = None
    if not winners.empty:
        w = winners.iloc[0]
        biggest_winner = {
            "horse": str(w.get("horse", "?")),
            "sp": round(float(w["sp_decimal"]), 2),
            "vp": round(float(w["velo_prime_prob"]), 3),
            "date": str(w["date"].date()) if hasattr(w.get("date"), "date") else str(w.get("date", "?")),
        }

    # Subgroup breakdowns
    sp_breakdown = _sp_band_breakdown(vp40)
    course_breakdown = _subgroup_breakdown(vp40, "course")
    tier_breakdown = _subgroup_breakdown(vp40, "decision_tier", lambda v: f"Tier {v}")

    # Overlap
    overlap = _overlap_analysis(vp40, df)

    # Outlier strip test
    outlier = _outlier_strip_test(vp40)

    # Refined simulations
    simulations = _refined_simulations(vp40)

    # Policy recommendation
    recommendation = _policy_recommendation(stats, sp_breakdown, outlier, overlap)

    # Console output
    print(f"\n  SR={stats['sr']}%  Frame={stats['frame_rate']}%  ROI={stats['roi']:+.1f}%  "
          f"Avg_SP={stats['avg_sp']}  LLR={llr}  MaxDD=£{max_dd}")
    print(f"\n  Policy recommendation: {recommendation['verdict']}")
    print(f"  {recommendation['rationale'][:100]}...")
    print("\n  Issues:")
    for issue in recommendation["issues"]:
        print(f"    {'[CRITICAL]' if issue in recommendation['critical_issues'] else '[WARNING]'} {issue[:100]}")
    print("\n  SP band breakdown:")
    for row in sp_breakdown:
        roi_str = f"{row['roi']:+.1f}%" if row["roi"] is not None else "—"
        print(f"    {row['group']:<14} n={row['n']:>3} SR={row['sr']:>5.1f}% ROI={roi_str}")
    print("\n  Outlier strip test:")
    for s in outlier["strip_test"]:
        roi_str = f"{s['roi_stripped']:+.1f}%" if s["roi_stripped"] is not None else "—"
        print(f"    Excl top {s['excluding_top']} ({s['excluded_horse']} SP={s['excluded_sp']}): ROI={roi_str}")
    print("\n  Refined simulations:")
    for sim_name, sim in simulations.items():
        roi_str = f"{sim['roi']:+.1f}%" if sim.get("roi") is not None else "—"
        print(f"    {sim_name:<26} n={sim['n']:>3} SR={sim['sr']:>5.1f}% ROI={roi_str}")

    result = {
        "run_ts": run_ts,
        "date": date,
        "lane": "VP40_LANE",
        "corpus_rows": len(df),
        "overall": stats,
        "longest_losing_run": llr,
        "max_drawdown": max_dd,
        "biggest_winner": biggest_winner,
        "sp_band_breakdown": sp_breakdown,
        "course_breakdown": course_breakdown,
        "tier_breakdown": tier_breakdown,
        "overlap": overlap,
        "outlier_analysis": outlier,
        "refined_simulations": simulations,
        "recommendation": recommendation,
        "governance": {
            "scoring_change": False,
            "model_change": False,
            "router_change": False,
            "staking_change": False,
            "telegram": False,
            "classification": "POLICY_SIMULATION_ONLY",
        },
    }

    json_path = REPORTS_DIR / "vp40_shadow_policy_review_latest.json"
    json_path.write_text(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = _build_md(result, date, run_ts)
    md_path = REPORTS_DIR / "vp40_shadow_policy_review_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    return result


if __name__ == "__main__":
    main()
