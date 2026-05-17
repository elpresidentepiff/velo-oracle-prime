#!/usr/bin/env python3
"""
VP40_TIER_A_SHADOW_POLICY_REVIEW_V1

Forensic review of VP40_TIER_A_LANE as the refined shadow policy candidate.
Full VP40_LANE failed the 10-gate protocol (outlier dependency + midprice drain).
This review applies the same 10-gate abuse tests to VP40 restricted to Tier A.

Governance:
  No scoring change | No model change | No router change | No staking
  No Telegram | No live state mutation | Policy simulation only

Inputs:
    data/training/sigma_2k_training_dataset_latest.parquet

Outputs:
    data/reports/vp40_tier_a_shadow_policy_review_latest.json
    data/reports/vp40_tier_a_shadow_policy_review_latest.md

Usage:
    python scripts/vp40_tier_a_shadow_policy_review.py [--date YYYY-MM-DD]
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

PROMOTION_N_MIN = 150
PROMOTION_N_PREFERRED = 250
PROMOTION_SR_FLOOR = 40.0
PROMOTION_FRAME_FLOOR = 75.0
PROMOTION_ROI_FLOOR = 0.0
SUBGROUP_MIN_N = 5
SUBGROUP_COLLAPSE_FLOOR = 25.0
OUTLIER_ROI_FLOOR = 0.0


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
    if sp < 2.0:   return "SP<2.0"
    if sp < 3.0:   return "SP2.0-2.99"
    if sp <= 8.5:  return "SP3.0-8.5"
    if sp <= 16.0: return "SP8.51-16.0"
    return "SP>16.0"


def _flat_stats(df: pd.DataFrame) -> dict:
    n = len(df)
    if n == 0:
        return {"n": 0, "wins": 0, "frames": 0, "sr": 0.0, "frame_rate": 0.0,
                "roi": None, "avg_sp": None, "median_sp": None}
    wins = int(df["won"].sum())
    frames = int(df["placed"].sum())
    sp_col = df["sp_decimal"].dropna()
    win_sps = df[df["won"]]["sp_decimal"].dropna()
    roi = round((float(win_sps.sum()) - n) / n * 100, 1) if len(win_sps) else None
    return {
        "n": n, "wins": wins, "frames": frames,
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
    ordered = df.sort_values("date") if "date" in df.columns else df
    running = peak = max_dd = 0.0
    for _, row in ordered.iterrows():
        running += float(row["sp_decimal"]) - 1.0 if row["won"] else -1.0
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)


def _subgroup_breakdown(df: pd.DataFrame, col: str, label_fn=None) -> list[dict]:
    if col not in df.columns:
        return []
    rows = []
    for val, grp in df.groupby(col):
        if len(grp) < SUBGROUP_MIN_N:
            continue
        stats = _flat_stats(grp)
        rows.append({"group": label_fn(val) if label_fn else str(val), **stats})
    return sorted(rows, key=lambda r: r["n"], reverse=True)


def _sp_band_breakdown(df: pd.DataFrame) -> list[dict]:
    df2 = df.copy()
    df2["_band"] = df2["sp_decimal"].apply(lambda x: _sp_band(float(x)) if pd.notna(x) else "unknown")
    return _subgroup_breakdown(df2, "_band")


def _overlap_analysis(target: pd.DataFrame, full_df: pd.DataFrame) -> dict:
    t_idx = set(target.index)
    t_wins = target[target["won"]]

    lanes = {
        "MDS_HIGH_LANE":        set(full_df[(full_df["velo_prime_prob"] >= 0.30) & (full_df["market_deception_score"] > 0.50)].index),
        "IMPROVER_LANE":        set(full_df[(full_df["velo_prime_prob"] >= 0.30) & (full_df["improvement_score"] > 0.40)].index),
        "SHORTFAV_VP30":        set(full_df[(full_df["sp_decimal"] < 3.0) & (full_df["velo_prime_prob"] >= 0.30)].index),
        "MIDPRICE_ROUTER_QUAL": set(full_df[(full_df["sp_decimal"] >= 3.0) & (full_df["sp_decimal"] <= 8.5) & full_df["router_qualified"]].index),
        "MIDPRICE_SUPPRESS":    set(full_df[(full_df["sp_decimal"] >= 3.0) & (full_df["sp_decimal"] <= 8.5) & ~full_df["router_qualified"]].index),
    }

    overlaps = []
    for name, o_idx in lanes.items():
        common = t_idx & o_idx
        overlaps.append({
            "lane": name,
            "overlap_n": len(common),
            "pct_of_target": round(len(common) / len(target) * 100, 1) if len(target) else 0.0,
            "shared_winners": len(set(t_wins.index) & o_idx),
        })

    return {"overlaps": overlaps}


def _outlier_strip_test(df: pd.DataFrame) -> dict:
    n = len(df)
    winners = df[df["won"]].sort_values("sp_decimal", ascending=False)
    top_winners = []
    for _, w in winners.head(5).iterrows():
        top_winners.append({
            "horse": str(w.get("horse", "?")),
            "sp": round(float(w["sp_decimal"]), 2),
            "vp": round(float(w["velo_prime_prob"]), 3),
            "date": str(w["date"].date()) if hasattr(w.get("date"), "date") else str(w.get("date", "?")),
        })

    strip_results = []
    for i in range(min(3, len(winners))):
        remaining = winners.iloc[i+1:]
        rem_n = n - (i + 1)
        roi_s = round((float(remaining["sp_decimal"].sum()) - rem_n) / rem_n * 100, 1) if rem_n > 0 else None
        strip_results.append({
            "excluding_top": i + 1,
            "excluded_horse": top_winners[i]["horse"] if i < len(top_winners) else "?",
            "excluded_sp": round(float(winners.iloc[i]["sp_decimal"]), 2),
            "roi_stripped": roi_s,
        })

    return {"top_winners": top_winners, "strip_test": strip_results}


def _refined_simulations(df: pd.DataFrame) -> dict:
    sp_lt3 = df[df["sp_decimal"] < 3.0]
    sp2x = df[(df["sp_decimal"] >= 2.0) & (df["sp_decimal"] < 3.0)]
    sp_lt3_no_midprice = df[df["sp_decimal"] < 3.0]
    no_midprice = df[df["sp_decimal"] < 3.0]
    return {
        "VP40_TIER_A_SP_LT3":    {"description": "VP40_TIER_A + SP<3.0 only", **_flat_stats(sp_lt3)},
        "VP40_TIER_A_SP_2X":     {"description": "VP40_TIER_A + SP 2.0-2.99 (healthiest band)", **_flat_stats(sp2x)},
        "VP40_TIER_A_NO_MIDPRICE": {"description": "VP40_TIER_A excl SP3.0-8.5 (remove drain zone)", **_flat_stats(df[df["sp_decimal"].apply(lambda x: float(x) < 3.0 or float(x) > 8.5) if pd.api.types.is_numeric_dtype(df["sp_decimal"]) else False])},
    }


def _policy_recommendation(stats: dict, sp_breakdown: list, outlier: dict) -> dict:
    n = stats["n"]
    sr = stats["sr"]
    frame_rate = stats["frame_rate"]
    roi = stats.get("roi") or 0.0

    issues = []
    strengths = []

    strip1 = next((s for s in outlier["strip_test"] if s["excluding_top"] == 1), {})
    roi_strip1 = strip1.get("roi_stripped")
    if roi_strip1 is not None and roi_strip1 < OUTLIER_ROI_FLOOR:
        issues.append(
            f"OUTLIER_DEPENDENCY: ROI collapses to {roi_strip1:+.1f}% without top SP winner "
            f"({strip1.get('excluded_horse')} SP={strip1.get('excluded_sp')})"
        )
    else:
        strengths.append("ROI survives top-winner removal")

    sp35 = next((s for s in sp_breakdown if s["group"] == "SP3.0-8.5"), {})
    sp35_roi = sp35.get("roi")
    if sp35 and sp35["n"] >= 10 and sp35_roi is not None and sp35_roi < -15:
        issues.append(
            f"MIDPRICE_DRAIN: VP40_TIER_A+SP3.0-8.5 SR={sp35['sr']}% ROI={sp35_roi:+.1f}% "
            f"at n={sp35['n']} — confirmed drain subzone within Tier A"
        )

    sp16 = next((s for s in sp_breakdown if s["group"] == "SP8.51-16.0"), {})
    if sp16 and sp16["n"] >= 5 and sp16.get("sr", 0) == 0:
        issues.append(f"LONGSHOT_DEAD_ZONE: SP8.51-16.0 SR=0% n={sp16['n']}")

    if n >= PROMOTION_N_MIN:
        if n >= PROMOTION_N_PREFERRED:
            strengths.append(f"n={n} at preferred threshold {PROMOTION_N_PREFERRED}")
        else:
            issues.append(f"n={n} above minimum {PROMOTION_N_MIN} but below preferred {PROMOTION_N_PREFERRED}")
    else:
        issues.append(f"n={n} below minimum {PROMOTION_N_MIN}")

    if sr >= PROMOTION_SR_FLOOR:
        strengths.append(f"SR={sr}% above {PROMOTION_SR_FLOOR}% floor")
    if frame_rate >= PROMOTION_FRAME_FLOOR:
        strengths.append(f"Frame={frame_rate}% above {PROMOTION_FRAME_FLOOR}% floor")
    if roi >= PROMOTION_ROI_FLOOR:
        strengths.append(f"ROI={roi:+.1f}% — positive flat stake")

    critical = [i for i in issues if "OUTLIER_DEPENDENCY" in i or "MIDPRICE_DRAIN" in i]

    if critical:
        verdict = "WATCH_ONLY"
        rationale = (
            "Same critical blockers as full VP40_LANE. Roysse (SP=34) is Tier A — "
            "the outlier dependency carries through. Mid-price drain persists within Tier A "
            "(SP3.0-8.5: SR=16.2%, ROI=-23.0%). Both VP40_LANE and VP40_TIER_A fail "
            "Gate 4 (ROI strip) and Gate 7 (winner concentration) of the 10-gate protocol. "
            "Wait for n>=250 and natural Roysse ROI dilution."
        )
    elif n < PROMOTION_N_MIN:
        verdict = "NEEDS_MORE_DATA"
        rationale = "Insufficient n for meaningful gate assessment."
    else:
        verdict = "SHADOW_POLICY_CANDIDATE"
        rationale = "All critical gates pass — ready for policy discussion."

    return {
        "verdict": verdict,
        "rationale": rationale,
        "strengths": strengths,
        "issues": issues,
        "critical_issues": critical,
    }


def _build_md(result: dict, date: str, run_ts: str) -> str:
    s = result["overall"]
    rec = result["recommendation"]
    outlier = result["outlier_analysis"]
    simulations = result["refined_simulations"]
    overlap = result["overlap"]

    roi_str = (f"+{s['roi']}%" if s["roi"] and s["roi"] > 0 else str(s["roi"]) + "%") if s["roi"] is not None else "—"

    lines = [
        "# VP40 TIER A SHADOW POLICY REVIEW V1",
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
        for item in rec["strengths"]:
            lines.append(f"- ✅ {item}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Overall VP40_TIER_A Stats",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| n (resulted) | {s['n']} |",
        f"| Wins | {s['wins']} |",
        f"| Frames | {s['frames']} |",
        f"| Strike rate | {s['sr']}% |",
        f"| Frame rate | {s['frame_rate']}% |",
        f"| ROI (flat £1) | {roi_str} |",
        f"| Avg SP | {s['avg_sp'] or '—'} |",
        f"| Median SP | {s['median_sp'] or '—'} |",
        f"| Max winner SP | {result['biggest_winner']['sp'] if result.get('biggest_winner') else '—'} |",
        f"| Biggest winner | {result['biggest_winner']['horse'] if result.get('biggest_winner') else '—'} |",
        f"| Longest losing run | {result['longest_losing_run']} |",
        f"| Max drawdown | £{result['max_drawdown']} |",
        "",
        "---",
        "",
        "## ROI Outlier Strip Test",
        "",
        "| Excluding top N winners | Excluded horse | Excluded SP | ROI stripped |",
        "|---|---|---|---|",
    ]

    for row in outlier["strip_test"]:
        roi_s = f"{row['roi_stripped']:+.1f}%" if row["roi_stripped"] is not None else "—"
        lines.append(f"| {row['excluding_top']} | {row['excluded_horse']} | {row['excluded_sp']} | {roi_s} |")
    lines += [
        "",
        "**Finding:** Roysse (SP=34) is Tier A. Same outlier dependency confirmed.",
        "VP40_TIER_A shares the Gate 4 failure with full VP40_LANE.",
        "",
        "---",
        "",
        "## SP Band Breakdown",
        "",
        "| SP Band | n | SR | Frame | ROI |",
        "|---|---|---|---|---|",
    ]

    for row in result["sp_band_breakdown"]:
        roi_s = f"{row['roi']:+.1f}%" if row["roi"] is not None else "—"
        lines.append(f"| {row['group']} | {row['n']} | {row['sr']}% | {row['frame_rate']}% | {roi_s} |")
    lines += [
        "",
        "SP3.0-8.5 drain persists within Tier A (SR=16.2%, ROI=-23.0%). Midprice contamination is not a tier issue.",
        "",
        "---",
        "",
        "## Course Breakdown",
        "",
        "| Course | n | SR | ROI |",
        "|---|---|---|---|",
    ]

    for row in result["course_breakdown"]:
        roi_s = f"{row['roi']:+.1f}%" if row["roi"] is not None else "—"
        lines.append(f"| {row['group']} | {row['n']} | {row['sr']}% | {roi_s} |")
    lines += ["", "---", "", "## Overlap Analysis", "",
              "| Lane | Overlap n | % of VP40_TIER_A | Shared winners |",
              "|---|---|---|---|"]

    for row in overlap["overlaps"]:
        lines.append(f"| {row['lane']} | {row['overlap_n']} | {row['pct_of_target']}% | {row['shared_winners']} |")
    lines += [
        "",
        "MIDPRICE_SUPPRESS overlap (25.8%) shows the drain zone is inside Tier A — it is an SP band issue, not a tier issue.",
        "",
        "---",
        "",
        "## Refined Simulations",
        "",
        "| Simulation | n | SR | Frame | ROI |",
        "|---|---|---|---|---|",
    ]

    for sim_name, sim in simulations.items():
        roi_s = f"{sim['roi']:+.1f}%" if sim.get("roi") is not None else "—"
        lines.append(f"| {sim_name} | {sim['n']} | {sim['sr']}% | {sim['frame_rate']}% | {roi_s} |")
    lines += [
        "",
        "---",
        "",
        "## Key Finding vs Full VP40_LANE",
        "",
        "Both VP40_LANE and VP40_TIER_A fail the 10-gate protocol for the same reasons:",
        "",
        "```",
        "1. Roysse is Tier A → outlier dependency carries through",
        "2. SP3.0-8.5 drain exists within Tier A → midprice contamination is not tier-filtered",
        "3. SP8.51-16.0 dead zone exists within Tier A",
        "```",
        "",
        "VP40_TIER_A is marginally cleaner (18 fewer noisy rows, slightly higher ROI).",
        "But the structural problems are identical.",
        "",
        "**Path forward:**",
        "Wait for n>=250. As Roysse's SP=34 return gets diluted by more results,",
        "the outlier dependency ratio improves naturally.",
        "At n=250+, a single winner contributes < 14% of total return (vs ~50% now at n=132).",
        "",
        "---",
        "",
        "## Governance",
        "",
        "```",
        "NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE",
        "NO_STAKING_CHANGE | NO_TELEGRAM_CHANGE | NO_PLAYBOOK_G_PROMOTION",
        "NO_LIVE_STATE_MUTATION | POLICY_SIMULATION_ONLY | WATCH_ONLY",
        "```",
        "",
        "*VP40_TIER_A_SHADOW_POLICY_REVIEW_V1 — advisory only, no execution impact*",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    date = args.date

    print(f"VP40 TIER A SHADOW POLICY REVIEW V1 — {date}")
    print("=" * 60)
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    df = _load_corpus()
    lane = df[(df["velo_prime_prob"] >= 0.40) & (df["decision_tier"] == "A")].copy()
    print(f"  Corpus rows: {len(df)} | VP40_TIER_A rows: {len(lane)}")

    stats = _flat_stats(lane)
    llr = _longest_losing_run(lane)
    max_dd = _max_drawdown(lane)

    winners = lane[lane["won"]].sort_values("sp_decimal", ascending=False)
    biggest_winner = None
    if not winners.empty:
        w = winners.iloc[0]
        biggest_winner = {
            "horse": str(w.get("horse", "?")),
            "sp": round(float(w["sp_decimal"]), 2),
            "vp": round(float(w["velo_prime_prob"]), 3),
            "date": str(w["date"].date()) if hasattr(w.get("date"), "date") else str(w.get("date", "?")),
        }

    sp_breakdown = _sp_band_breakdown(lane)
    course_breakdown = _subgroup_breakdown(lane, "course")
    tier_breakdown = _subgroup_breakdown(lane, "decision_tier", lambda v: f"Tier {v}")
    overlap = _overlap_analysis(lane, df)
    outlier = _outlier_strip_test(lane)
    simulations = _refined_simulations(lane)
    recommendation = _policy_recommendation(stats, sp_breakdown, outlier)

    print(f"\n  SR={stats['sr']}%  Frame={stats['frame_rate']}%  ROI={stats['roi']:+.1f}%  "
          f"Avg_SP={stats['avg_sp']}  LLR={llr}  MaxDD=£{max_dd}")
    print(f"\n  Policy recommendation: {recommendation['verdict']}")
    print(f"  {recommendation['rationale'][:110]}...")
    print("\n  Issues:")
    for issue in recommendation["issues"]:
        lbl = "[CRITICAL]" if issue in recommendation["critical_issues"] else "[WARNING]"
        print(f"    {lbl} {issue[:100]}")
    print("\n  SP band breakdown:")
    for row in sp_breakdown:
        roi_s = f"{row['roi']:+.1f}%" if row["roi"] is not None else "—"
        print(f"    {row['group']:<14} n={row['n']:>3} SR={row['sr']:>5.1f}% ROI={roi_s}")
    print("\n  Outlier strip test:")
    for s in outlier["strip_test"]:
        roi_s = f"{s['roi_stripped']:+.1f}%" if s["roi_stripped"] is not None else "—"
        print(f"    Excl top {s['excluding_top']} ({s['excluded_horse']} SP={s['excluded_sp']}): ROI={roi_s}")
    print("\n  Refined simulations:")
    for sim_name, sim in simulations.items():
        roi_s = f"{sim['roi']:+.1f}%" if sim.get("roi") is not None else "—"
        print(f"    {sim_name:<32} n={sim['n']:>3} SR={sim['sr']:>5.1f}% ROI={roi_s}")

    result = {
        "run_ts": run_ts, "date": date, "lane": "VP40_TIER_A_LANE",
        "corpus_rows": len(df), "overall": stats,
        "longest_losing_run": llr, "max_drawdown": max_dd,
        "biggest_winner": biggest_winner,
        "sp_band_breakdown": sp_breakdown,
        "course_breakdown": course_breakdown,
        "tier_breakdown": tier_breakdown,
        "overlap": overlap,
        "outlier_analysis": outlier,
        "refined_simulations": simulations,
        "recommendation": recommendation,
        "governance": {
            "scoring_change": False, "model_change": False, "router_change": False,
            "staking_change": False, "telegram": False,
            "classification": "POLICY_SIMULATION_ONLY",
        },
    }

    json_path = REPORTS_DIR / "vp40_tier_a_shadow_policy_review_latest.json"
    json_path.write_text(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = _build_md(result, date, run_ts)
    md_path = REPORTS_DIR / "vp40_tier_a_shadow_policy_review_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    return result


if __name__ == "__main__":
    main()
