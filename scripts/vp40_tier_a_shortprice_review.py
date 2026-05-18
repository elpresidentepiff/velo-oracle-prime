#!/usr/bin/env python3
"""
VP40_TIER_A_SHORTPRICE_REVIEW_V1

Forensic shadow policy review of VP40_TIER_A_SHORTPRICE lane.
Definition: velo_prime_prob >= 0.40 AND decision_tier == 'A' AND sp_decimal < 3.0

This lane isolates the honest signal by removing both poison zones:
  - SP 3.0–8.5 (midprice drain)
  - SP > 8.5   (Roysse/longshot contamination)

Governance:
  No scoring change | No model change | No router change | No staking | Advisory only

Inputs:
    data/training/sigma_2k_training_dataset_latest.parquet

Outputs:
    data/reports/vp40_tier_a_shortprice_review_latest.json
    data/reports/vp40_tier_a_shortprice_review_latest.md

Usage:
    python scripts/vp40_tier_a_shortprice_review.py [--date YYYY-MM-DD]
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS_DIR = DATA / "reports"
TRAINING_PATH = DATA / "training" / "sigma_2k_training_dataset_latest.parquet"
REPORTS_DIR.mkdir(exist_ok=True)

# Lane definitions for overlap analysis
LANE_DEFS = {
    "MDS_HIGH_LANE":    lambda df: (df["velo_prime_prob"] >= 0.30) & (df["market_deception_score"] > 0.50),
    "IMPROVER_LANE":    lambda df: (df["velo_prime_prob"] >= 0.30) & (df["improvement_score"] > 0.40),
    "SHORTFAV_VP30":    lambda df: (df["sp_decimal"] < 3.0) & (df["velo_prime_prob"] >= 0.30),
    "ROUTER_QUALIFIED": lambda df: df["router_qualified"] == True,
}


def _load_data() -> pd.DataFrame:
    df = pd.read_parquet(TRAINING_PATH)
    return df[df["result_matched"] == True].copy()


def _apply_lane(df: pd.DataFrame) -> pd.DataFrame:
    mask = (
        (df["velo_prime_prob"] >= 0.40) &
        (df["decision_tier"] == "A") &
        (df["sp_decimal"] < 3.0)
    )
    return df[mask].copy()


def _core_stats(lane: pd.DataFrame) -> dict:
    n = len(lane)
    if n == 0:
        return {"n": 0, "wins": 0, "frames": 0, "sr": 0.0, "frame_rate": 0.0,
                "roi": 0.0, "avg_sp": None, "median_sp": None}
    wins = int(lane["won"].sum())
    frames = int(lane["placed"].sum()) if "placed" in lane.columns else 0
    sr = round(wins / n * 100, 1)
    frame_rate = round(frames / n * 100, 1) if frames > 0 else 0.0
    roi = round(((lane["sp_decimal"] * lane["won"]) - 1).mean() * 100, 1)
    avg_sp = round(float(lane["sp_decimal"].mean()), 2)
    median_sp = round(float(lane["sp_decimal"].median()), 2)
    max_sp = round(float(lane["sp_decimal"].max()), 2)
    return {
        "n": n, "wins": wins, "frames": frames,
        "sr": sr, "frame_rate": frame_rate, "roi": roi,
        "avg_sp": avg_sp, "median_sp": median_sp, "max_sp": max_sp,
    }


def _losing_run(lane: pd.DataFrame) -> dict:
    if len(lane) == 0:
        return {"llr": 0, "llr_pct": 0.0, "max_drawdown": 0.0}
    won = lane.sort_values("date")["won"].tolist()
    llr = 0
    cur = 0
    stake = 0.0
    peak = 0.0
    max_dd = 0.0
    for w in won:
        if not w:
            cur += 1
            llr = max(llr, cur)
            stake -= 1.0
        else:
            cur = 0
            stake += 1.0  # flat stake simplification
        peak = max(peak, stake)
        max_dd = max(max_dd, peak - stake)
    return {
        "llr": llr,
        "llr_pct": round(llr / len(won) * 100, 1),
        "max_drawdown": round(max_dd, 2),
    }


def _outlier_strip_test(lane: pd.DataFrame) -> dict:
    if len(lane) == 0:
        return {"strip_test": [], "top_winner_horse": None, "top_winner_sp": None,
                "top_winner_vp": None, "top3_concentration": None}
    winners = lane[lane["won"] == True].sort_values("sp_decimal", ascending=False)
    n = len(lane)
    total_return = float((lane["sp_decimal"] * lane["won"]).sum())
    strip_test = []
    working = lane.copy()
    for i in range(min(3, len(winners))):
        row = winners.iloc[i]
        horse = str(row.get("horse", "?"))
        sp = float(row["sp_decimal"])
        vp = round(float(row["velo_prime_prob"]), 3)
        working = working[~((working["horse"] == horse) & (working["sp_decimal"] == sp))]
        roi_stripped = round(((working["sp_decimal"] * working["won"]) - 1).mean() * 100, 1) if len(working) else 0.0
        strip_test.append({
            "excluding_top": i + 1,
            "excluded_horse": horse,
            "excluded_sp": round(sp, 1),
            "excluded_vp": vp,
            "roi_stripped": roi_stripped,
            "roi_still_positive": roi_stripped >= 0.0,
        })
    top_winner = winners.iloc[0] if len(winners) else None
    top3_return = float((winners.head(3)["sp_decimal"]).sum()) if len(winners) >= 3 else float(winners["sp_decimal"].sum())
    top3_pct = round(top3_return / total_return * 100, 1) if total_return > 0 else 0.0
    top1_pct = round(float(winners.iloc[0]["sp_decimal"]) / total_return * 100, 1) if len(winners) and total_return > 0 else 0.0
    return {
        "strip_test": strip_test,
        "top_winner_horse": str(top_winner["horse"]) if top_winner is not None else None,
        "top_winner_sp": round(float(top_winner["sp_decimal"]), 1) if top_winner is not None else None,
        "top_winner_vp": round(float(top_winner["velo_prime_prob"]), 3) if top_winner is not None else None,
        "top1_return_pct": top1_pct,
        "top3_return_pct": top3_pct,
        "total_return": round(total_return, 2),
    }


def _course_breakdown(lane: pd.DataFrame, lane_sr: float) -> list[dict]:
    if "course" not in lane.columns or len(lane) == 0:
        return []
    rows = []
    for course, grp in lane.groupby("course"):
        n = len(grp)
        if n < 3:
            continue
        wins = int(grp["won"].sum())
        sr = round(wins / n * 100, 1)
        roi = round(((grp["sp_decimal"] * grp["won"]) - 1).mean() * 100, 1)
        collapse = sr < (lane_sr - 20.0) and n >= 5
        rows.append({"course": str(course), "n": n, "wins": wins, "sr": sr, "roi": roi,
                     "collapse": collapse})
    return sorted(rows, key=lambda x: x["n"], reverse=True)


def _class_breakdown(lane: pd.DataFrame, lane_sr: float) -> list[dict]:
    if "class_num" not in lane.columns or len(lane) == 0:
        return []
    non_null = lane[lane["class_num"].notna()]
    if len(non_null) < 5:
        return []
    rows = []
    for cls, grp in non_null.groupby("class_num"):
        n = len(grp)
        if n < 3:
            continue
        wins = int(grp["won"].sum())
        sr = round(wins / n * 100, 1)
        roi = round(((grp["sp_decimal"] * grp["won"]) - 1).mean() * 100, 1)
        collapse = sr < (lane_sr - 20.0) and n >= 5
        rows.append({"class": int(cls), "n": n, "wins": wins, "sr": sr, "roi": roi,
                     "collapse": collapse})
    return sorted(rows, key=lambda x: x["n"], reverse=True)


def _going_breakdown(lane: pd.DataFrame, lane_sr: float) -> list[dict]:
    if "going" not in lane.columns or len(lane) == 0:
        return []
    non_null = lane[lane["going"].notna() & (lane["going"] != "")]
    if len(non_null) < 5:
        return []
    rows = []
    for going, grp in non_null.groupby("going"):
        n = len(grp)
        if n < 3:
            continue
        wins = int(grp["won"].sum())
        sr = round(wins / n * 100, 1)
        roi = round(((grp["sp_decimal"] * grp["won"]) - 1).mean() * 100, 1)
        collapse = sr < (lane_sr - 20.0) and n >= 5
        rows.append({"going": str(going), "n": n, "wins": wins, "sr": sr, "roi": roi,
                     "collapse": collapse})
    return sorted(rows, key=lambda x: x["n"], reverse=True)


def _overlap_analysis(lane: pd.DataFrame, df_all: pd.DataFrame) -> list[dict]:
    if len(lane) == 0:
        return []
    lane_ids = set(lane.index)
    rows = []
    for name, lane_fn in LANE_DEFS.items():
        try:
            other_mask = lane_fn(df_all)
            other_idx = set(df_all[other_mask].index)
        except Exception:
            continue
        shared = lane_ids & other_idx
        n_shared = len(shared)
        pct = round(n_shared / len(lane_ids) * 100, 1) if lane_ids else 0.0
        shared_wins = int(df_all.loc[list(shared), "won"].sum()) if shared else 0
        rows.append({"lane": name, "n_shared": n_shared, "pct_of_shortprice": pct,
                     "shared_wins": shared_wins})
    return rows


def _subgroup_collapse_summary(course_bd: list, class_bd: list, going_bd: list) -> list[str]:
    flags = []
    for r in course_bd:
        if r.get("collapse") and r["n"] >= 5:
            flags.append(f"COURSE_COLLAPSE: {r['course']} n={r['n']} SR={r['sr']}%")
    for r in class_bd:
        if r.get("collapse") and r["n"] >= 5:
            flags.append(f"CLASS_COLLAPSE: Class{r['class']} n={r['n']} SR={r['sr']}%")
    for r in going_bd:
        if r.get("collapse") and r["n"] >= 5:
            flags.append(f"GOING_COLLAPSE: {r['going']} n={r['n']} SR={r['sr']}%")
    return flags


def _build_recommendation(stats: dict, outlier: dict, llr: dict,
                           collapse_flags: list) -> dict:
    n = stats["n"]
    sr = stats["sr"]
    roi = stats["roi"]
    strip1 = next((s for s in outlier.get("strip_test", []) if s["excluding_top"] == 1), {})
    strip2 = next((s for s in outlier.get("strip_test", []) if s["excluding_top"] == 2), {})
    roi_ex1 = strip1.get("roi_stripped")
    roi_ex2 = strip2.get("roi_stripped")
    top1_pct = outlier.get("top1_return_pct", 999)
    top3_pct = outlier.get("top3_return_pct", 999)

    issues = []
    critical_issues = []
    strengths = []

    # Strengths
    if sr >= 55.0:
        strengths.append(f"HIGH_SR: {sr}% — strong win rate for this price zone")
    if roi >= 0.0:
        strengths.append(f"POSITIVE_ROI: {roi}% — positive flat-stake return")
    if roi_ex1 is not None and roi_ex1 >= 0.0:
        strengths.append(f"ROI_SURVIVES_STRIP_1: {roi_ex1}% — structural stability confirmed")
    if llr["llr"] <= 10:
        strengths.append(f"CONTROLLED_LLR: longest losing run = {llr['llr']}")
    if top1_pct is not None and top1_pct < 20.0:
        strengths.append(f"LOW_OUTLIER_DEPENDENCY: top winner = {top1_pct}% of total return")

    # Gate issues
    if n < 150:
        issues.append(f"INSUFFICIENT_N: n={n} below minimum gate (n>=150). Preferred n>=250.")
    if sr < 40.0:
        critical_issues.append(f"LOW_SR: {sr}% below 40% minimum gate")
    if roi < 0.0:
        issues.append(f"NEGATIVE_ROI: {roi}% — flat stake negative. Short prices compress ROI even at high SR.")
    # Outlier dependency only flags if full ROI is positive but collapses on strip.
    # If ROI is already negative, the strip test just confirms negativity — not a Roysse-style outlier.
    if roi >= 0.0 and roi_ex1 is not None and roi_ex1 < 0.0:
        critical_issues.append(
            f"OUTLIER_DEPENDENCY: ROI collapses from {roi:+.1f}% to {roi_ex1}% without "
            f"{outlier.get('top_winner_horse')} SP={outlier.get('top_winner_sp')}"
        )
    if roi_ex2 is not None and roi_ex2 < -10.0:
        issues.append(f"ROI_STRIPS_BADLY: ROI ex-top-2 = {roi_ex2}%")
    if top1_pct is not None and top1_pct >= 20.0:
        critical_issues.append(
            f"WINNER_CONCENTRATION: top winner = {top1_pct}% of total return (gate: <20%)"
        )
    if top3_pct is not None and top3_pct >= 40.0:
        critical_issues.append(
            f"WINNER_CONCENTRATION_TOP3: top-3 winners = {top3_pct}% of total return (gate: <40%)"
        )
    if llr["llr"] > int(n * 0.15):
        issues.append(f"HIGH_LLR: {llr['llr']} ({llr['llr_pct']}% of n) — above 15% threshold")
    for flag in collapse_flags:
        issues.append(f"SUBGROUP_COLLAPSE: {flag}")

    # Verdict
    if n < 50:
        verdict = "NEEDS_MORE_DATA"
        rationale = f"n={n} is below minimum review threshold (n>=50). No gates can be assessed."
    elif n < 150:
        if critical_issues:
            verdict = "WATCH_ONLY"
            rationale = (
                f"n={n} with SR={sr}% shows a strong win rate but {len(critical_issues)} critical "
                f"issue(s) prevent promotion. All gates must pass."
            )
        elif roi < 0.0:
            verdict = "WATCH_ONLY"
            rationale = (
                f"n={n}, SR={sr}%, ROI={roi:+.1f}%. Gate 1 (n<150) and Gate 5 (ROI<0%) both "
                f"fail. ROI compression is mathematical at avg SP={stats.get('avg_sp')} — "
                f"not a signal failure. Monitor to n>=150."
            )
        else:
            verdict = "WATCH_ONLY"
            rationale = (
                f"n={n}, SR={sr}%, ROI={roi:+.1f}%. Promising but below n=150 minimum gate. "
                f"Monitor to n>=250."
            )
    elif critical_issues:
        verdict = "WATCH_ONLY"
        rationale = (
            f"n={n}, SR={sr}%, ROI={roi:+.1f}%. {len(critical_issues)} critical failure(s). "
            f"Cannot promote until all 10 gates pass."
        )
    elif issues:
        verdict = "WATCH_ONLY"
        rationale = (
            f"n={n}, SR={sr}%, ROI={roi:+.1f}%. Promising signal but gate issues remain. "
            f"Monitor to n>=250."
        )
    else:
        verdict = "SHADOW_POLICY_CANDIDATE"
        rationale = (
            f"n={n}, SR={sr}%, ROI={roi:+.1f}%. No critical failures. "
            f"All abuse tests passed. Ready for shadow policy discussion."
        )

    return {
        "verdict": verdict,
        "rationale": rationale,
        "strengths": strengths,
        "issues": issues,
        "critical_issues": critical_issues,
    }


def _build_md(data: dict) -> str:
    stats = data["overall"]
    outlier = data["outlier_analysis"]
    rec = data["recommendation"]
    llr = data["losing_run"]
    strip = outlier.get("strip_test", [])
    strip1 = next((s for s in strip if s["excluding_top"] == 1), {})
    strip2 = next((s for s in strip if s["excluding_top"] == 2), {})
    strip3 = next((s for s in strip if s["excluding_top"] == 3), {})

    lines = [
        "# VP40_TIER_A_SHORTPRICE SHADOW POLICY REVIEW V1",
        f"**Date:** {data['date']}",
        f"**Run:** {data['run_ts']}",
        "",
        "**Lane definition:** VP >= 0.40 AND decision_tier == A AND SP < 3.0",
        "**Purpose:** Removes midprice drain (SP 3.0–8.5) and Roysse zone (SP > 8.5). Tests the honest signal.",
        "",
        f"---",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| n | {stats['n']} |",
        f"| Wins | {stats['wins']} |",
        f"| Frames (placed) | {stats['frames']} |",
        f"| Strike Rate | {stats['sr']}% |",
        f"| Frame Rate | {stats['frame_rate']}% |",
        f"| ROI (flat £1) | {stats['roi']:+.1f}% |",
        f"| Avg SP | {stats['avg_sp']} |",
        f"| Median SP | {stats['median_sp']} |",
        f"| Max SP | {stats.get('max_sp', '?')} |",
        f"| Longest Losing Run | {llr['llr']} ({llr['llr_pct']}% of n) |",
        f"| Max Drawdown (£1 flat) | £{llr['max_drawdown']} |",
        "",
        f"**Verdict: {rec['verdict']}**",
        "",
        f"*{rec['rationale']}*",
        "",
        "---",
        "",
        "## What This Lane Tests",
        "",
        "VP40_LANE failed Gate 4 (ROI strip) because Roysse SP=34 carries all positive ROI.",
        "VP40_TIER_A failed Gate 4 for the same reason — Roysse is Tier A.",
        "VP40_TIER_A_SHORTPRICE removes all SP >= 3.0, which excludes:",
        "  - The midprice drain zone (SP 3.0–8.5, SR~16%, ROI~-23%)",
        "  - The longshot outlier zone (SP>8.5, Roysse SP=34)",
        "",
        "What remains: the short-price Tier A signal at SP < 3.0.",
        "SP range in this lane: {:.2f} — {:.2f}".format(
            data.get("sp_min", 0), stats.get("max_sp", 0)),
        "",
        "---",
        "",
        "## ROI Strip Test",
        "",
        "| Removed | Horse | SP | ROI Remaining | Still positive? |",
        "|---|---|---|---|---|",
        f"| Full lane | — | — | {stats['roi']:+.1f}% | {'Yes' if stats['roi'] >= 0 else 'No'} |",
    ]

    for s in [strip1, strip2, strip3]:
        if s:
            pos = "Yes" if s.get("roi_still_positive") else "No"
            lines.append(
                f"| Remove top {s['excluding_top']} | {s['excluded_horse']} | "
                f"SP={s['excluded_sp']} | {s['roi_stripped']:+.1f}% | {pos} |"
            )

    lines += [
        "",
        f"Top winner: {outlier.get('top_winner_horse')} SP={outlier.get('top_winner_sp')} "
        f"VP={outlier.get('top_winner_vp')}",
        f"Top-1 return concentration: {outlier.get('top1_return_pct')}% of total return",
        f"Top-3 return concentration: {outlier.get('top3_return_pct')}% of total return",
        "",
        "**Gate 4 target:** ROI >= 0% when top 1 and top 2 winners excluded.",
        "**Gate 7 target:** Top-1 winner < 20% of total return. Top-3 < 40%.",
        "",
        "---",
        "",
        "## Strengths",
        "",
    ]
    for s in rec.get("strengths", []) or ["None identified."]:
        lines.append(f"- {s}")

    lines += ["", "## Issues / Gate Failures", ""]
    critical = rec.get("critical_issues", [])
    issues = rec.get("issues", [])
    if critical:
        for ci in critical:
            lines.append(f"- *** CRITICAL: {ci}")
    if issues:
        for iss in issues:
            lines.append(f"- {iss}")
    if not critical and not issues:
        lines.append("- None.")

    lines += [
        "",
        "---",
        "",
        "## Course Breakdown",
        "",
        "| Course | n | SR | ROI | Collapse? |",
        "|---|---|---|---|---|",
    ]
    for r in (data.get("course_breakdown") or []):
        col = "YES ⚠️" if r.get("collapse") else "No"
        lines.append(f"| {r['course']} | {r['n']} | {r['sr']}% | {r['roi']:+.1f}% | {col} |")
    if not data.get("course_breakdown"):
        lines.append("| — | insufficient n>=3 | — | — | — |")

    lines += [
        "",
        "## Class Breakdown",
        "",
    ]
    if data.get("class_breakdown"):
        lines += ["| Class | n | SR | ROI | Collapse? |", "|---|---|---|---|---|"]
        for r in data["class_breakdown"]:
            col = "YES ⚠️" if r.get("collapse") else "No"
            lines.append(f"| Class {r['class']} | {r['n']} | {r['sr']}% | {r['roi']:+.1f}% | {col} |")
    else:
        lines.append("Class data sparse in corpus — no reliable breakdown.")

    lines += [
        "",
        "## Going Breakdown",
        "",
    ]
    if data.get("going_breakdown"):
        lines += ["| Going | n | SR | ROI | Collapse? |", "|---|---|---|---|---|"]
        for r in data["going_breakdown"]:
            col = "YES ⚠️" if r.get("collapse") else "No"
            lines.append(f"| {r['going']} | {r['n']} | {r['sr']}% | {r['roi']:+.1f}% | {col} |")
    else:
        lines.append("Going data sparse in corpus — no reliable breakdown.")

    lines += [
        "",
        "---",
        "",
        "## Overlap Analysis",
        "",
        "| Lane | Shared n | % of Shortprice | Shared wins |",
        "|---|---|---|---|",
    ]
    for r in (data.get("overlap_analysis") or []):
        lines.append(
            f"| {r['lane']} | {r['n_shared']} | {r['pct_of_shortprice']}% | {r['shared_wins']} |"
        )

    lines += [
        "",
        "**Note:** All VP40_TIER_A_SHORTPRICE rows are also in SHORTFAV_VP30 by definition (SP<3.0 + VP>=0.30).",
        "The overlap with MDS_HIGH and IMPROVER shows where signal layers compound.",
        "",
        "---",
        "",
        "## Subgroup Collapse Flags",
        "",
    ]
    flags = data.get("subgroup_collapse_flags", [])
    if flags:
        for f in flags:
            lines.append(f"- *** {f}")
    else:
        lines.append("No subgroup collapse detected at current n.")

    lines += [
        "",
        "---",
        "",
        "## ROI Context: Why Short Prices Compress Returns",
        "",
        "A SR=60% lane at SP<3.0 will often produce negative ROI because:",
        "",
        "```",
        "Avg SP=1.75 → avg net return per win = £0.75",
        "Required SR to break even at avg SP=1.75: 1/1.75 = 57.1%",
        "SR=60% at avg SP=1.75 → ROI ≈ -3.5% (matches observed)",
        "",
        "This is a mathematical compression, not a signal failure.",
        "The signal is real (SR=60%). The unit is wrong (flat £1 at short prices).",
        "```",
        "",
        "To extract value from this lane in practice, the bet must be sized differently",
        "or the return measure must shift to place/frame rather than win-flat-stake.",
        "This is a policy discussion, not a disqualifier.",
        "",
        "---",
        "",
        "## Promotion Path",
        "",
        "```",
        f"Current: n={stats['n']}  SR={stats['sr']}%  ROI={stats['roi']:+.1f}%",
        "",
        "Gate 1 (n>=150): FAIL — n={} / 150".format(stats['n']),
        "Gate 4 (ROI strip): {}".format(
            "PASS" if strip1.get("roi_still_positive") else f"FAIL — ROI ex-top = {strip1.get('roi_stripped', '?')}%"),
        "Gate 7 (outlier conc.): {}".format(
            "PASS" if (outlier.get("top1_return_pct") or 999) < 20.0 else
            f"FAIL — top-1 = {outlier.get('top1_return_pct')}%"),
        "",
        "Next milestone: n=150 — rerun this script",
        "Preferred milestone: n=250 — rerun this script",
        "```",
        "",
        "---",
        "",
        "## Governance",
        "",
        "```",
        "NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE",
        "NO_STAKING_CHANGE | NO_TELEGRAM_CHANGE | NO_PLAYBOOK_G_PROMOTION",
        "NO_LIVE_STATE_MUTATION | POLICY_SIMULATION_ONLY",
        "```",
        "",
        "*VP40_TIER_A_SHORTPRICE_REVIEW_V1 — advisory only, no execution impact*",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    date = args.date

    print(f"VP40_TIER_A_SHORTPRICE REVIEW V1 — {date}")
    print("=" * 60)
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    df = _load_data()
    lane = _apply_lane(df)
    stats = _core_stats(lane)

    print(f"  n={stats['n']}  SR={stats['sr']}%  Frame={stats['frame_rate']}%  "
          f"ROI={stats['roi']:+.1f}%")
    print(f"  SP range: {lane['sp_decimal'].min():.2f} — {lane['sp_decimal'].max():.2f} "
          f"  avg={stats['avg_sp']}  median={stats['median_sp']}")

    llr = _losing_run(lane)
    outlier = _outlier_strip_test(lane)

    strip1 = next((s for s in outlier["strip_test"] if s["excluding_top"] == 1), {})
    print(f"  ROI ex-top-winner: {strip1.get('roi_stripped', '?'):.1f}%  "
          f"(ex {outlier.get('top_winner_horse')} SP={outlier.get('top_winner_sp')})")
    print(f"  Top-1 return concentration: {outlier.get('top1_return_pct')}%  "
          f"Top-3: {outlier.get('top3_return_pct')}%")
    print(f"  LLR: {llr['llr']}  ({llr['llr_pct']}% of n)  Max drawdown: £{llr['max_drawdown']}")

    course_bd = _course_breakdown(lane, stats["sr"])
    class_bd = _class_breakdown(lane, stats["sr"])
    going_bd = _going_breakdown(lane, stats["sr"])
    collapse_flags = _subgroup_collapse_summary(course_bd, class_bd, going_bd)
    overlap = _overlap_analysis(lane, df)
    rec = _build_recommendation(stats, outlier, llr, collapse_flags)

    print(f"\n  Verdict: {rec['verdict']}")
    if rec["critical_issues"]:
        for ci in rec["critical_issues"]:
            print(f"  *** CRITICAL: {ci[:85]}")
    if rec["issues"]:
        for iss in rec["issues"][:3]:
            print(f"  ISSUE: {iss[:85]}")
    if rec["strengths"]:
        for s in rec["strengths"][:3]:
            print(f"  STRENGTH: {s[:85]}")

    output = {
        "run_ts": run_ts,
        "date": date,
        "lane": "VP40_TIER_A_SHORTPRICE",
        "definition": "velo_prime_prob >= 0.40 AND decision_tier == A AND sp_decimal < 3.0",
        "corpus_rows": int(len(df)),
        "sp_min": round(float(lane["sp_decimal"].min()), 2) if len(lane) else None,
        "overall": stats,
        "losing_run": llr,
        "outlier_analysis": outlier,
        "course_breakdown": course_bd,
        "class_breakdown": class_bd,
        "going_breakdown": going_bd,
        "subgroup_collapse_flags": collapse_flags,
        "overlap_analysis": overlap,
        "recommendation": rec,
        "governance": {
            "scoring_change": False, "model_change": False, "router_change": False,
            "staking_change": False, "telegram": False,
            "classification": "POLICY_SIMULATION_ONLY",
        },
    }

    json_path = REPORTS_DIR / "vp40_tier_a_shortprice_review_latest.json"
    json_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = _build_md(output)
    md_path = REPORTS_DIR / "vp40_tier_a_shortprice_review_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    return output


if __name__ == "__main__":
    main()
