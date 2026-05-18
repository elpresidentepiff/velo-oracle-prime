#!/usr/bin/env python3
"""
SHADOW_AUDIT_JTC_D_VS_SIGMA_V2

Full-field rank analysis — builds a complete race dataset from results JSONs
(all runners per race with actual positions/SP), joins VP scores from sigma
for VÉLØ-scored candidates, computes JTC-D for all runners.

Ranking methods tested:
  A. velo_prime_prob alone           (current engine — baseline, 0 for non-sigma)
  B. trainer_course_sr alone         (pure JTC-D)
  C. jockey_course_sr alone          (pure JTC-D)
  D. trainer_jockey_sr alone         (partnership signal)
  E. vp + 0.3*trainer_course_sr      (VP + trainer course)
  F. vp + 0.3*jockey_course_sr       (VP + jockey course)
  G. vp + 0.2*tc + 0.1*jc           (VP + both JTC-D)
  H. vp + 0.2*tc + 0.1*jc + 0.1*tj (VP + full JTC-D blend)

Also: lift analysis on sigma-scored candidates only (winners vs non-winners).

Governance:
  NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_STAKING_CHANGE
  Shadow analysis only — do not use to justify live changes

Usage:
  python scripts/shadow_audit_jtc_d_vs_sigma.py [--min-runners N]
"""
import argparse
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "data"
JTCD_DIR = ROOT / "data" / "features" / "jtc_d"
SIGMA = ROOT / "data" / "training" / "sigma_2k_training_dataset_latest.parquet"
REPORTS_DIR = ROOT / "data" / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


# ── JTC-D ────────────────────────────────────────────────────────────────────

def _load_jtcd_lookups() -> dict:
    lookups = {}
    for name in ["trainer_course", "trainer_dist", "jockey_course",
                 "jockey_dist", "trainer_jockey"]:
        path = JTCD_DIR / f"{name}_profile.parquet"
        if not path.exists():
            lookups[name] = {}
            continue
        df = pd.read_parquet(path)
        if name == "trainer_course":
            lookups[name] = {
                (str(r["trainer"]).upper(), str(r["course"]).upper()): r["jtc_signal"]
                for _, r in df.iterrows() if r["trainer"] and r["course"]
            }
        elif name == "trainer_dist":
            lookups[name] = {
                (str(r["trainer"]).upper(), str(r["dist_band"]).upper()): r["jtc_signal"]
                for _, r in df.iterrows() if r["trainer"]
            }
        elif name == "jockey_course":
            lookups[name] = {
                (str(r["jockey"]).upper(), str(r["course"]).upper()): r["jtc_signal"]
                for _, r in df.iterrows() if r["jockey"] and r["course"]
            }
        elif name == "jockey_dist":
            lookups[name] = {
                (str(r["jockey"]).upper(), str(r["dist_band"]).upper()): r["jtc_signal"]
                for _, r in df.iterrows() if r["jockey"]
            }
        elif name == "trainer_jockey":
            lookups[name] = {
                (str(r["trainer"]).upper(), str(r["jockey"]).upper()): r["jtc_signal"]
                for _, r in df.iterrows() if r["trainer"] and r["jockey"]
            }
    return lookups


def _dist_band(dist_text: str) -> str:
    t = str(dist_text or "").lower().replace(" ", "").replace("½", ".5").replace("¼", ".25")
    m = re.match(r"(?:(\d+)m)?(\d+(?:\.\d+)?f)?", t)
    if not m:
        return "unknown"
    miles = int(m.group(1) or 0)
    furlongs = float((m.group(2) or "0f").replace("f", "") or 0)
    total_f = miles * 8 + furlongs
    bins = [(5.5, "5f"), (6.5, "6f"), (7.5, "7f"), (8.5, "8f"),
            (10.5, "9-10f"), (12.5, "11-12f"), (14.5, "13-14f"), (17.5, "15-17f")]
    for ceil, label in bins:
        if total_f < ceil:
            return label
    return "18f+"


def _lookup_jtcd(lookups: dict, trainer: str, jockey: str,
                 course: str, dist_text: str) -> dict:
    t = str(trainer or "").upper()
    j = str(jockey or "").upper()
    c = str(course or "").upper()
    d = _dist_band(dist_text).upper()
    return {
        "trainer_course_sr": lookups["trainer_course"].get((t, c)),
        "trainer_dist_sr": lookups["trainer_dist"].get((t, d)),
        "jockey_course_sr": lookups["jockey_course"].get((j, c)),
        "jockey_dist_sr": lookups["jockey_dist"].get((j, d)),
        "trainer_jockey_sr": lookups["trainer_jockey"].get((t, j)),
    }


# ── Results loader ────────────────────────────────────────────────────────────

def _load_full_field(sigma_dates: set, lookups: dict) -> pd.DataFrame:
    """
    Build full-field DataFrame from results JSONs for all sigma dates.
    One row per runner per race.
    """
    rows = []
    files = sorted(RESULTS_DIR.glob("results_*.json"))

    for f in files:
        if "_partial" in f.name:
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results = data.get("results", data) if isinstance(data, dict) else data
            if not isinstance(results, list):
                continue
            for race in results:
                date_str = str(race.get("date", ""))[:10]
                if date_str not in sigma_dates:
                    continue
                race_id = race.get("race_id", "")
                course = race.get("course", "")
                dist = race.get("dist", "")
                race_type = race.get("type", "")
                race_class = race.get("class", "")
                race_name = race.get("race_name", "")
                for runner in race.get("runners", []):
                    position = runner.get("position", "")
                    sp_dec = runner.get("sp_dec", "")
                    try:
                        sp_f = float(sp_dec)
                    except (ValueError, TypeError):
                        sp_f = float("nan")
                    try:
                        pos_i = int(position)
                    except (ValueError, TypeError):
                        pos_i = 99
                    trainer = runner.get("trainer", "")
                    jockey = runner.get("jockey", "")
                    jtcd = _lookup_jtcd(lookups, trainer, jockey, course, dist)
                    rows.append({
                        "race_id": race_id,
                        "date": date_str,
                        "course": course,
                        "dist": dist,
                        "race_type": race_type,
                        "race_class": race_class,
                        "race_name": race_name,
                        "horse_id": runner.get("horse_id", ""),
                        "horse": runner.get("horse", ""),
                        "trainer": trainer,
                        "jockey": jockey,
                        "sp_decimal": sp_f,
                        "position": pos_i,
                        "won": pos_i == 1,
                        "velo_prime_prob": 0.0,  # populated below from sigma
                        **jtcd,
                    })
        except Exception:
            continue

    return pd.DataFrame(rows)


# ── Rank eval ─────────────────────────────────────────────────────────────────

def _evaluate_method(df: pd.DataFrame, signal_col: str,
                     min_runners: int = 3) -> dict:
    results = []
    for race_id, group in df.groupby("race_id"):
        if len(group) < min_runners:
            continue
        if signal_col not in group.columns or group[signal_col].isna().all():
            continue
        valid = group.dropna(subset=[signal_col])
        if len(valid) < min_runners:
            continue
        winner_rows = valid[valid["won"] == True]
        if len(winner_rows) == 0:
            continue

        ranks = valid[signal_col].rank(ascending=False, method="min")
        winner_idx = winner_rows.index[0]
        winner_rank = float(ranks.loc[winner_idx])
        winner_sp = float(winner_rows.iloc[0]["sp_decimal"])

        top1 = winner_rank == 1
        top3 = winner_rank <= 3
        mrr = 1.0 / winner_rank

        # ROI: flat bet on ranked #1 runner
        top_ranked = valid.loc[ranks.idxmin()]
        bet_wins = bool(top_ranked["won"])
        roi = (top_ranked["sp_decimal"] - 1.0) if bet_wins else -1.0

        results.append({
            "race_id": race_id,
            "n_runners": len(valid),
            "winner_rank": winner_rank,
            "winner_sp": winner_sp,
            "top1": top1,
            "top3": top3,
            "mrr": mrr,
            "roi": roi,
        })

    if not results:
        return {"signal": signal_col, "races": 0,
                "top1_rate": None, "top3_rate": None,
                "mrr": None, "roi": None}

    r = pd.DataFrame(results)
    return {
        "signal": signal_col,
        "races": len(r),
        "top1_rate": round(r["top1"].mean() * 100, 1),
        "top3_rate": round(r["top3"].mean() * 100, 1),
        "mrr": round(r["mrr"].mean(), 4),
        "roi": round(r["roi"].mean() * 100, 1),
        "avg_winner_rank": round(r["winner_rank"].mean(), 2),
        "_df": r,
    }


def _build_combined_signal(df: pd.DataFrame, name: str, weights: dict) -> pd.DataFrame:
    df = df.copy()
    signal = pd.Series(0.0, index=df.index)
    any_valid = pd.Series(False, index=df.index)
    for col, w in weights.items():
        if col in df.columns:
            signal += df[col].fillna(0.0) * w
            any_valid = any_valid | df[col].notna()
    df[name] = signal.where(any_valid, np.nan)
    return df


def _breakdown(df: pd.DataFrame, signal_col: str, by_col: str,
               by_vals: list, min_runners: int) -> list:
    results = []
    for val in by_vals:
        subset = df[df[by_col] == val]
        if len(subset) == 0:
            continue
        r = _evaluate_method(subset, signal_col, min_runners)
        r["group"] = str(val)
        results.append(r)
    return results


def _sprint_cat(dist_text: str) -> str:
    t = str(dist_text or "").lower().replace(" ", "").replace("½", ".5").replace("¼", ".25")
    m = re.match(r"(?:(\d+)m)?(\d+(?:\.\d+)?f)?", t)
    if not m:
        return "unknown"
    miles = int(m.group(1) or 0)
    furlongs = float((m.group(2) or "0f").replace("f", "") or 0)
    total_f = miles * 8 + furlongs
    if total_f <= 7:
        return "sprint"
    elif total_f <= 10:
        return "mile"
    else:
        return "route"


# ── Lift analysis on sigma candidates only ───────────────────────────────────

def _sigma_lift_analysis(df: pd.DataFrame) -> dict:
    """
    On rows where velo_prime_prob > 0 (sigma-scored candidates),
    measure winner vs non-winner signal means and AUC.
    """
    sigma_rows = df[df["velo_prime_prob"] > 0].copy()
    if len(sigma_rows) == 0:
        return {}
    w = sigma_rows[sigma_rows["won"] == True]
    nw = sigma_rows[sigma_rows["won"] == False]
    results = {}
    for col in ["velo_prime_prob", "trainer_course_sr", "jockey_course_sr",
                "trainer_jockey_sr", "trainer_dist_sr", "jockey_dist_sr"]:
        if col not in sigma_rows.columns:
            continue
        w_mean = w[col].dropna().mean()
        nw_mean = nw[col].dropna().mean()
        results[col] = {
            "winner_mean": round(float(w_mean), 5) if not math.isnan(w_mean) else None,
            "non_winner_mean": round(float(nw_mean), 5) if not math.isnan(nw_mean) else None,
            "lift": round(float(w_mean - nw_mean), 5) if not math.isnan(w_mean) else None,
            "winner_coverage": round(float(w[col].notna().mean()), 3),
        }
    return {"n_sigma_candidates": len(sigma_rows), "n_winners": len(w), "signals": results}


# ── Report ────────────────────────────────────────────────────────────────────

def _build_report_md(methods: list, breakdown_results: dict,
                     lift: dict, date_range: tuple, n_races: int,
                     chance_baseline: float = None, sigma_win_rate: float = None) -> str:
    lines = [
        "# SHADOW AUDIT — JTC-D Full-Field Rank Analysis (V2)",
        "",
        f"**Date range:** {date_range[0]} → {date_range[1]}  |  **Races:** {n_races}",
        "",
        "Full-field rank analysis — all runners per race from results JSONs.",
        "JTC-D signals applied to every runner. VP not included (only sigma horses have VP scores).",
        "Shadow analysis only. No scoring change. No live mutation.",
        "",
    ]
    if chance_baseline:
        lines.append(f"**Field average chance baseline:** {chance_baseline}% (1/avg field)")
    if sigma_win_rate:
        lines.append(f"**VÉLØ sigma win rate (reference):** {sigma_win_rate}% (separate test)")
    lines += [
        "",
        "---",
        "",
        "## JTC-D Method Comparison (full field, min 3 runners/race)",
        "",
        "| Method | Races | #1 Hit% | vs Chance | Top-3% | MRR | Flat ROI |",
        "|---|---|---|---|---|---|---|",
    ]

    for m in methods:
        if m["top1_rate"] is None:
            lines.append(f"| `{m['signal']}` | — | — | — | — | — | — |")
            continue
        lift_pp = (m["top1_rate"] - chance_baseline) if chance_baseline else 0
        lift_str = f"{lift_pp:+.1f}pp"
        lines.append(
            f"| `{m['signal']}` | {m['races']} | "
            f"**{m['top1_rate']}%** | {lift_str} | {m['top3_rate']}% | "
            f"{m['mrr']:.4f} | {m['roi']:+.1f}% |"
        )

    # Lift analysis section
    if lift and lift.get("signals"):
        lines += [
            "",
            "---",
            "",
            "## Signal Lift — VÉLØ Candidates (winners vs non-winners)",
            "",
            f"n_candidates: {lift['n_sigma_candidates']} | winners: {lift['n_winners']}",
            "",
            "| Signal | Winner Mean | Non-Winner Mean | Lift | Coverage |",
            "|---|---|---|---|---|",
        ]
        for sig, s in lift["signals"].items():
            if s["lift"] is None:
                continue
            lines.append(
                f"| `{sig}` | {s['winner_mean']:.4f} | {s['non_winner_mean']:.4f} | "
                f"**{s['lift']:+.4f}** | {s['winner_coverage']:.0%} |"
            )

    # Breakdown
    best_method = max(
        (m for m in methods if m.get("top1_rate") is not None),
        key=lambda m: m["top1_rate"],
        default=None,
    )
    if best_method:
        lines += [
            "",
            "---",
            "",
            f"## Breakdown (best signal: `{best_method['signal']}`)",
            "",
            "### By Race Type",
            "| Race Type | Races | #1 Hit% | Top-3% | ROI |",
            "|---|---|---|---|---|",
        ]
        for g in breakdown_results.get("race_type", []):
            if g.get("top1_rate") is None:
                continue
            lines.append(f"| {g['group']} | {g['races']} | "
                         f"{g['top1_rate']}% | {g['top3_rate']}% | {g['roi']:+.1f}% |")

        lines += [
            "",
            "### By Distance Category",
            "| Distance | Races | #1 Hit% | Top-3% | ROI |",
            "|---|---|---|---|---|",
        ]
        for g in breakdown_results.get("dist_cat", []):
            if g.get("top1_rate") is None:
                continue
            lines.append(f"| {g['group']} | {g['races']} | "
                         f"{g['top1_rate']}% | {g['top3_rate']}% | {g['roi']:+.1f}% |")

    lines += ["", "---", "", "## Summary Verdict", ""]

    if best_method and chance_baseline:
        lift_pp = best_method["top1_rate"] - chance_baseline
        if lift_pp > 5:
            verdict = f"JTC-D PREDICTIVE — best method ({best_method['signal']}) at {best_method['top1_rate']}% vs {chance_baseline}% chance (+{lift_pp:.1f}pp). Consider deeper integration."
        elif lift_pp > 2:
            verdict = f"JTC-D WEAKLY PREDICTIVE — {best_method['top1_rate']}% vs {chance_baseline}% chance (+{lift_pp:.1f}pp). Grow sample before wiring."
        else:
            verdict = f"JTC-D NOT PREDICTIVE — {best_method['top1_rate']}% vs {chance_baseline}% chance. Do not wire."
        lines.append(f"**{verdict}**")

    lines += [
        "",
        "```",
        "NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_STAKING_CHANGE",
        "SHADOW_AUDIT_ONLY — advisory only",
        "```",
        "",
        "*SHADOW_AUDIT_JTC_D_VS_SIGMA_V2 — full-field analysis*",
    ]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-runners", type=int, default=3)
    args = parser.parse_args()

    print("SHADOW AUDIT — JTC-D vs VELO PRIME (V2 Full-Field)")
    print("=" * 60)

    # Load sigma for VP scores and date filter
    sigma = pd.read_parquet(SIGMA)
    sigma = sigma[sigma["result_matched"] == True].copy()
    sigma_dates = set(sigma["date"].str[:10].unique())
    # Key on (horse_id, race_id) so VP is only applied to the exact scored race
    sigma_vp = {(r["horse_id"], r["race_id"]): r["velo_prime_prob"]
                for _, r in sigma.iterrows()}
    print(f"Sigma: {len(sigma):,} matched rows | {len(sigma_dates)} dates")

    # Load JTC-D
    lookups = _load_jtcd_lookups()
    n_loaded = sum(1 for v in lookups.values() if v)
    print(f"JTC-D tables: {n_loaded}/5 loaded")

    # Build full-field dataset
    print("Loading results JSONs and building full-field dataset...")
    df = _load_full_field(sigma_dates, lookups)
    if len(df) == 0:
        print("ERROR: No results data found for sigma dates.")
        raise SystemExit(1)

    # Assign VP scores to sigma-matched runners — must match on (horse_id, race_id)
    df["velo_prime_prob"] = df.apply(
        lambda r: sigma_vp.get((r["horse_id"], r["race_id"]), 0.0), axis=1
    )
    vp_assigned = (df["velo_prime_prob"] > 0).sum()
    print(f"Full-field: {len(df):,} runners | {df['race_id'].nunique():,} races")
    print(f"VP assigned: {vp_assigned:,} runners ({vp_assigned/len(df):.1%} of field)")
    print(f"JTC-D coverage: trainer_course={df['trainer_course_sr'].notna().mean():.1%}  "
          f"jockey_course={df['jockey_course_sr'].notna().mean():.1%}")

    # Distance category
    df["dist_cat"] = df["dist"].apply(_sprint_cat)

    # Race type: 'Flat' or 'Jumps' from results type field
    # Also classify handicap from race_name
    df["is_handicap"] = df["race_name"].str.lower().str.contains("handicap|h'cap|hcap", na=False)

    # Combined signals — JTC-D only (no VP dependency)
    # These rank ALL runners fairly using JTC-D signals
    df = _build_combined_signal(df, "tc_jc", {
        "trainer_course_sr": 0.5, "jockey_course_sr": 0.5})
    df = _build_combined_signal(df, "tc_jc_tj", {
        "trainer_course_sr": 0.4, "jockey_course_sr": 0.3, "trainer_jockey_sr": 0.3})
    df = _build_combined_signal(df, "full_jtcd", {
        "trainer_course_sr": 0.25, "trainer_dist_sr": 0.20,
        "jockey_course_sr": 0.25, "jockey_dist_sr": 0.15,
        "trainer_jockey_sr": 0.15})

    # VP + JTC-D: uses VP for sigma horse, JTC-D for everyone else as tiebreaker
    # Rescale JTC-D to VP range (VP ~0.1-0.5, JTC signals ~0.1-0.25)
    df = _build_combined_signal(df, "vp_or_tc_jc", {
        "velo_prime_prob": 1.0,
        "trainer_course_sr": 0.5,
        "jockey_course_sr": 0.3,
        "trainer_jockey_sr": 0.2})

    # Field-average baseline (chance = 1 / avg field size)
    avg_field = df.groupby("race_id").size().mean()
    chance_baseline = round(100.0 / avg_field, 1)
    print(f"\nAvg field size: {avg_field:.1f} runners → chance baseline: {chance_baseline}%")

    # Evaluate methods (JTC-D full-field only — VP not included here;
    # VP is inherently incompatible with full-field ranking since only sigma runners
    # have VP > 0, all others are 0, creating rank-tie artifacts)
    methods_config = [
        "trainer_course_sr",        # A: JTC-D trainer x course
        "jockey_course_sr",         # B: JTC-D jockey x course
        "trainer_jockey_sr",        # C: JTC-D partnership
        "tc_jc",                    # D: trainer+jockey course blend
        "tc_jc_tj",                 # E: TC + JC + partnership
        "full_jtcd",                # F: all 5 JTC-D signals
    ]

    methods_out = []
    print(f"\n{'Signal':<42} {'Races':>6} {'#1%':>6} {'Top3%':>7} {'MRR':>7} {'ROI':>8}")
    print("-" * 80)

    for sig in methods_config:
        r = _evaluate_method(df, sig, args.min_runners)
        methods_out.append(r)
        if r["top1_rate"] is None:
            print(f"  {sig:<42} {'—':>6} {'—':>6} {'—':>7} {'—':>7} {'—':>8}")
        else:
            print(f"  {sig:<42} {r['races']:>6} {r['top1_rate']:>5.1f}% "
                  f"{r['top3_rate']:>5.1f}%  {r['mrr']:>6.4f}  {r['roi']:>+6.1f}%")

    # Sigma candidate lift analysis
    lift = _sigma_lift_analysis(df)
    if lift.get("signals"):
        print(f"\nSignal lift (sigma candidates only, n={lift['n_sigma_candidates']}):")
        for sig, s in lift["signals"].items():
            if s["lift"] is None:
                continue
            print(f"  {sig:<30} W={s['winner_mean']:.4f}  NW={s['non_winner_mean']:.4f}  "
                  f"lift={s['lift']:+.4f}  cov={s['winner_coverage']:.0%}")

    # Breakdowns
    best_sig = max(
        (m for m in methods_out if m.get("top1_rate") is not None),
        key=lambda m: m["top1_rate"],
        default={"signal": "velo_prime_prob"},
    )["signal"]

    breakdown_results: dict = {}

    race_types = sorted(df["race_type"].dropna().unique().tolist())
    if race_types:
        breakdown_results["race_type"] = _breakdown(
            df, best_sig, "race_type", race_types, args.min_runners)
        print(f"\nBreakdown by race type (best signal: {best_sig}):")
        for g in breakdown_results["race_type"]:
            if g.get("top1_rate") is None:
                continue
            print(f"  {g['group']:<20} races={g['races']:>4}  "
                  f"#1={g['top1_rate']:>5.1f}%  ROI={g['roi']:>+6.1f}%")

    breakdown_results["dist_cat"] = _breakdown(
        df, best_sig, "dist_cat", ["sprint", "mile", "route"], args.min_runners)
    print(f"\nBreakdown by distance (best signal: {best_sig}):")
    for g in breakdown_results["dist_cat"]:
        if g.get("top1_rate") is None:
            continue
        print(f"  {g['group']:<20} races={g['races']:>4}  "
              f"#1={g['top1_rate']:>5.1f}%  ROI={g['roi']:>+6.1f}%")

    # Handicap breakdown
    for is_hcap, label in [(True, "Handicap"), (False, "Non-handicap")]:
        subset = df[df["is_handicap"] == is_hcap]
        r = _evaluate_method(subset, best_sig, args.min_runners)
        if r["top1_rate"] is not None:
            print(f"  {label:<20} races={r['races']:>4}  "
                  f"#1={r['top1_rate']:>5.1f}%  ROI={r['roi']:>+6.1f}%")
    breakdown_results["handicap"] = [
        {**_evaluate_method(df[df["is_handicap"] == v], best_sig, args.min_runners),
         "group": lbl}
        for v, lbl in [(True, "Handicap"), (False, "Non-handicap")]
    ]

    # Verdict
    sigma_win_rate = round(sigma["won"].mean() * 100, 1) if "won" in sigma.columns else None
    best_m = max(
        (m for m in methods_out if m.get("top1_rate") is not None),
        key=lambda m: m["top1_rate"],
        default=None,
    )

    print("\n" + "=" * 60)
    print(f"FIELD AVERAGE CHANCE:           {chance_baseline}% (1 / {avg_field:.1f} runners)")
    if sigma_win_rate:
        print(f"VÉLØ SIGMA WIN RATE:            {sigma_win_rate}% (reference — different test)")
    if best_m:
        lift_vs_chance = best_m["top1_rate"] - chance_baseline
        print(f"BEST JTC-D ({best_m['signal']}): {best_m['top1_rate']}% #1 hit rate")
        print(f"LIFT vs chance:                 {lift_vs_chance:+.1f}pp")
        if lift_vs_chance > 5:
            verdict = "JTC-D PREDICTIVE — meaningful lift over field chance"
        elif lift_vs_chance > 2:
            verdict = "JTC-D WEAKLY PREDICTIVE — modest lift, grow sample before wiring"
        else:
            verdict = "JTC-D NOT PREDICTIVE — no meaningful lift over chance"
        print(f"VERDICT:                        {verdict}")

    # Write outputs
    clean_methods = [{k: v for k, v in m.items() if k != "_df"} for m in methods_out]
    clean_breakdown = {
        k: [{kk: vv for kk, vv in g.items() if kk != "_df"} for g in v]
        for k, v in breakdown_results.items()
    }

    output = {
        "version": "V2_FULL_FIELD",
        "date_range": {"min": df["date"].min(), "max": df["date"].max()},
        "total_runners": len(df),
        "total_races": int(df["race_id"].nunique()),
        "sigma_candidates": int((df["velo_prime_prob"] > 0).sum()),
        "avg_field_size": round(float(avg_field), 2),
        "chance_baseline_pct": chance_baseline,
        "sigma_win_rate_pct": sigma_win_rate,
        "min_runners_filter": args.min_runners,
        "methods": clean_methods,
        "breakdown": clean_breakdown,
        "sigma_lift": {k: v for k, v in lift.items() if k != "signals"},
        "sigma_lift_signals": lift.get("signals", {}),
        "governance": "NO_SCORING_CHANGE | NO_MODEL_CHANGE | SHADOW_AUDIT_ONLY",
    }

    json_path = REPORTS_DIR / "shadow_audit_jtc_d_latest.json"
    json_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    date_range = (str(df["date"].min()), str(df["date"].max()))
    md = _build_report_md(
        methods_out, breakdown_results, lift, date_range, df["race_id"].nunique(),
        chance_baseline=chance_baseline, sigma_win_rate=sigma_win_rate,
    )
    md_path = REPORTS_DIR / "shadow_audit_jtc_d_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")
    print("\nGovernance: NO_SCORING_CHANGE | NO_MODEL_CHANGE | SHADOW_AUDIT_ONLY")


if __name__ == "__main__":
    main()
