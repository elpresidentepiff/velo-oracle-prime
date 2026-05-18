#!/usr/bin/env python3
"""RUNNER_MASTER_FEATURE_AUDIT_V1 — Step 4

Audits each signal alone against won/placed before any model training.
Runs two feature set configurations:

  A. NO_SP_FEATURE_SET        — SP excluded (production-safe)
  B. SP_INCLUDED_DIAGNOSTIC   — SP included (diagnostic only, NEVER for production models)

Also audits TJ threshold:
  TJ_HIGH_GLOBAL_D8    — trainer_jockey_sr >= 80th pct of full 178k raceform distribution
  TJ_HIGH_TODAY_TOP20  — trainer_jockey_sr >= 80th pct of THIS dataset's covered distribution

Answers:
  Does ts_slope_6 separate winners?
  Does silent_improver_flag produce ROI or just narrative?
  Does exposed_regression_flag identify horses to downgrade?
  Does trainer_jockey_sr still work after RP trainer-name fix?
  Does TJ_HIGH remain useful?
  Does VELO + TJ + last-six compound cleanly?

Input:
  data/training/runner_master_training_dataset_latest.parquet

Outputs:
  data/reports/runner_master_feature_audit_latest.json
  data/reports/runner_master_feature_audit_latest.md

Governance: NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE
"""

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

ROOT       = Path(__file__).resolve().parent.parent
TRAIN_PATH = ROOT / "data" / "training" / "runner_master_training_dataset_latest.parquet"
JTCD_DIR   = ROOT / "data" / "features" / "jtc_d"
REPORT_DIR = ROOT / "data" / "reports"
REPORT_DIR.mkdir(exist_ok=True)

REPORT_JSON = REPORT_DIR / "runner_master_feature_audit_latest.json"
REPORT_MD   = REPORT_DIR / "runner_master_feature_audit_latest.md"


# ─── Core statistics ──────────────────────────────────────────────────────────

def roi(sp_series: pd.Series, won_series: pd.Series) -> float | None:
    n = len(sp_series)
    if n == 0:
        return None
    winnings = sp_series[won_series].sum()
    return round((winnings - n) / n * 100, 2)


def roi_strip_top(sp_series: pd.Series, won_series: pd.Series) -> dict:
    """ROI after removing the highest-SP winner (outlier sensitivity check)."""
    if won_series.sum() == 0:
        return {"roi_stripped": None, "stripped_sp": None, "n_stripped": len(sp_series)}
    winning_sps = sp_series[won_series]
    top_sp = float(winning_sps.max())
    # Remove one instance of the highest SP winner
    top_idx = winning_sps.idxmax()
    sp_stripped = sp_series.drop(index=top_idx)
    won_stripped = won_series.drop(index=top_idx)
    return {
        "roi_stripped": roi(sp_stripped, won_stripped),
        "stripped_sp": round(top_sp, 2),
        "n_stripped": len(sp_stripped),
    }


def winner_concentration(sp_series: pd.Series, won_series: pd.Series) -> dict:
    """What % of total return comes from top-1 and top-3 winners."""
    n = len(sp_series)
    if n == 0 or won_series.sum() == 0:
        return {"top1_pct": None, "top3_pct": None}
    total_return = float(sp_series[won_series].sum())
    sorted_wins = sp_series[won_series].sort_values(ascending=False)
    top1 = float(sorted_wins.iloc[0]) if len(sorted_wins) >= 1 else 0
    top3 = float(sorted_wins.iloc[:3].sum()) if len(sorted_wins) >= 3 else float(sorted_wins.sum())
    return {
        "top1_pct": round(top1 / total_return * 100, 1) if total_return else None,
        "top3_pct": round(top3 / total_return * 100, 1) if total_return else None,
    }


def sample_size_verdict(n: int) -> str:
    if n < 30:
        return "INSUFFICIENT_SAMPLE"
    if n < 100:
        return "SMALL_SAMPLE"
    if n < 300:
        return "MODERATE_SAMPLE"
    return "ADEQUATE_SAMPLE"


# ─── Numeric signal audit ─────────────────────────────────────────────────────

def audit_numeric(df: pd.DataFrame, col: str, label: str) -> dict:
    """Full audit for a continuous numeric signal."""
    sub = df[["won", "sp_decimal", col]].dropna(subset=[col])
    n = len(sub)
    n_win = int(sub["won"].sum())

    result: dict = {
        "signal":    col,
        "label":     label,
        "type":      "numeric",
        "n":         n,
        "n_winners": n_win,
        "win_rate":  round(n_win / n * 100, 2) if n else None,
        "sample_verdict": sample_size_verdict(n),
        "coverage_pct": round(n / len(df) * 100, 1),
    }

    if n < 5:
        result["error"] = "Insufficient data"
        return result

    # Winner vs loser means
    winner_vals = sub.loc[sub["won"], col]
    loser_vals  = sub.loc[~sub["won"], col]
    result["winner_mean"] = round(float(winner_vals.mean()), 4) if len(winner_vals) else None
    result["loser_mean"]  = round(float(loser_vals.mean()),  4) if len(loser_vals)  else None
    result["winner_median"] = round(float(winner_vals.median()), 4) if len(winner_vals) else None
    result["loser_median"]  = round(float(loser_vals.median()),  4) if len(loser_vals)  else None
    result["mean_diff"] = (
        round(result["winner_mean"] - result["loser_mean"], 4)
        if result["winner_mean"] is not None and result["loser_mean"] is not None else None
    )

    # Spearman rank correlation with won
    rho, pval = scipy_stats.spearmanr(sub[col], sub["won"].astype(int))
    result["spearman_rho"]  = round(float(rho), 4)
    result["spearman_pval"] = round(float(pval), 4)
    result["spearman_sig"]  = pval < 0.05

    # Decile breakdown (10 buckets of equal size)
    sub = sub.copy()
    sub["decile"] = pd.qcut(sub[col], q=10, labels=False, duplicates="drop")
    decile_stats = []
    for d_idx, grp in sub.groupby("decile"):
        d_n    = len(grp)
        d_wins = int(grp["won"].sum())
        d_wr   = round(d_wins / d_n * 100, 1) if d_n else None
        d_roi  = roi(grp["sp_decimal"], grp["won"])
        decile_stats.append({
            "decile":   int(d_idx),
            "n":        d_n,
            "win_rate": d_wr,
            "roi":      d_roi,
            "mean_val": round(float(grp[col].mean()), 4),
        })
    result["deciles"] = decile_stats

    if decile_stats:
        top_d = decile_stats[-1]
        bot_d = decile_stats[0]
        base_wr = result["win_rate"]
        result["top_decile_wr"]   = top_d["win_rate"]
        result["top_decile_roi"]  = top_d["roi"]
        result["top_decile_lift"] = (
            round(top_d["win_rate"] - base_wr, 1) if top_d["win_rate"] is not None else None
        )
        result["bot_decile_wr"]   = bot_d["win_rate"]
        result["bot_decile_drag"] = (
            round(base_wr - bot_d["win_rate"], 1) if bot_d["win_rate"] is not None else None
        )

    # SP-band split for top decile
    if len(sub[sub["decile"] == sub["decile"].max()]) >= 10:
        top_sub = sub[sub["decile"] == sub["decile"].max()].copy()
        sp_bands = {
            "short(<3)":    top_sub[top_sub["sp_decimal"] < 3],
            "fav(3-5)":     top_sub[(top_sub["sp_decimal"] >= 3) & (top_sub["sp_decimal"] < 5)],
            "mid(5-8.5)":   top_sub[(top_sub["sp_decimal"] >= 5) & (top_sub["sp_decimal"] < 8.5)],
            "long(8.5-15)": top_sub[(top_sub["sp_decimal"] >= 8.5) & (top_sub["sp_decimal"] < 15)],
            "outsider(15+)":top_sub[top_sub["sp_decimal"] >= 15],
        }
        result["top_decile_sp_bands"] = {
            band: {
                "n": len(g),
                "win_rate": round(g["won"].mean() * 100, 1) if len(g) else None,
                "roi": roi(g["sp_decimal"], g["won"]) if len(g) else None,
            }
            for band, g in sp_bands.items() if len(g) > 0
        }

    # Full-group strip + concentration
    result.update(roi_strip_top(sub["sp_decimal"], sub["won"]))
    result.update(winner_concentration(sub["sp_decimal"], sub["won"]))
    result["full_roi"] = roi(sub["sp_decimal"], sub["won"])

    return result


# ─── Binary flag audit ────────────────────────────────────────────────────────

def audit_flag(df: pd.DataFrame, col: str, label: str) -> dict:
    """Full audit for a binary flag signal."""
    sub = df[["won", "sp_decimal", col]].copy()
    # Treat NaN flags as False
    sub[col] = sub[col].fillna(False).astype(bool)

    flag_on  = sub[sub[col]]
    flag_off = sub[~sub[col]]

    n_on  = len(flag_on)
    n_off = len(flag_off)
    n_total = len(sub)

    result: dict = {
        "signal":       col,
        "label":        label,
        "type":         "flag",
        "n_flag_true":  n_on,
        "n_flag_false": n_off,
        "flag_rate":    round(n_on / n_total * 100, 1) if n_total else None,
        "sample_verdict": sample_size_verdict(n_on),
    }

    def _block(grp, name):
        n = len(grp)
        if n == 0:
            return {f"{name}_n": 0, f"{name}_wr": None, f"{name}_roi": None}
        n_win = int(grp["won"].sum())
        return {
            f"{name}_n":   n,
            f"{name}_wr":  round(n_win / n * 100, 2),
            f"{name}_roi": roi(grp["sp_decimal"], grp["won"]),
        }

    result.update(_block(flag_on,  "on"))
    result.update(_block(flag_off, "off"))

    if result.get("on_wr") is not None and result.get("off_wr") is not None:
        result["lift_vs_off"] = round(result["on_wr"] - result["off_wr"], 2)
        result["roi_delta"]   = (
            round(result["on_roi"] - result["off_roi"], 2)
            if result["on_roi"] is not None and result["off_roi"] is not None else None
        )

    # SP-band split for flag=True
    if n_on >= 5:
        sp_bands = {
            "short(<3)":    flag_on[flag_on["sp_decimal"] < 3],
            "fav(3-5)":     flag_on[(flag_on["sp_decimal"] >= 3) & (flag_on["sp_decimal"] < 5)],
            "mid(5-8.5)":   flag_on[(flag_on["sp_decimal"] >= 5) & (flag_on["sp_decimal"] < 8.5)],
            "long(8.5-15)": flag_on[(flag_on["sp_decimal"] >= 8.5) & (flag_on["sp_decimal"] < 15)],
            "outsider(15+)":flag_on[flag_on["sp_decimal"] >= 15],
        }
        result["flag_true_sp_bands"] = {
            band: {
                "n": len(g),
                "win_rate": round(g["won"].mean() * 100, 1) if len(g) else None,
                "roi": roi(g["sp_decimal"], g["won"]) if len(g) else None,
            }
            for band, g in sp_bands.items() if len(g) > 0
        }

    # Strip + concentration for flag=True
    if n_on >= 2:
        result.update(roi_strip_top(flag_on["sp_decimal"], flag_on["won"]))
        result.update(winner_concentration(flag_on["sp_decimal"], flag_on["won"]))

    result["verdict"] = _flag_verdict(result)
    return result


def _flag_verdict(r: dict) -> str:
    wr_on  = r.get("on_wr")
    roi_on = r.get("on_roi")
    lift   = r.get("lift_vs_off")
    n      = r.get("n_flag_true", 0)
    sv     = r.get("sample_verdict", "")
    if sv == "INSUFFICIENT_SAMPLE":
        return "INSUFFICIENT_SAMPLE"
    if wr_on is None:
        return "NO_DATA"
    if lift is not None and lift >= 5 and roi_on is not None and roi_on > 0:
        return "POSITIVE_SIGNAL"
    if lift is not None and lift >= 2:
        return "WEAK_POSITIVE"
    if lift is not None and lift < -2:
        return "NEGATIVE_SIGNAL"
    return "NEUTRAL"


# ─── Compound signal audit ────────────────────────────────────────────────────

def audit_compound(df: pd.DataFrame, conditions: list[tuple[str, str]], label: str) -> dict:
    """Audit a compound AND condition across multiple columns."""
    mask = pd.Series([True] * len(df), index=df.index)
    for col, op in conditions:
        if col not in df.columns:
            return {"label": label, "error": f"Missing column: {col}"}
        if op == "high":
            mask = mask & (df[col].fillna(False).astype(bool))
        elif op == "low":
            mask = mask & (~df[col].fillna(False).astype(bool))
        elif op.startswith(">="):
            val = float(op[2:])
            mask = mask & (df[col] >= val)
        elif op.startswith(">"):
            val = float(op[1:])
            mask = mask & (df[col] > val)

    sub_on  = df[mask]
    sub_off = df[~mask]
    n_on    = len(sub_on)
    n_total = len(df)

    result: dict = {
        "label":     label,
        "n_on":      n_on,
        "n_off":     len(sub_off),
        "rate":      round(n_on / n_total * 100, 1) if n_total else None,
        "conditions": [f"{c} {o}" for c, o in conditions],
        "sample_verdict": sample_size_verdict(n_on),
    }

    for grp, name in [(sub_on, "on"), (sub_off, "off")]:
        n = len(grp)
        if n == 0:
            result.update({f"{name}_n": 0, f"{name}_wr": None, f"{name}_roi": None})
            continue
        n_win = int(grp["won"].sum())
        result.update({
            f"{name}_n":   n,
            f"{name}_wr":  round(n_win / n * 100, 2),
            f"{name}_roi": roi(grp["sp_decimal"], grp["won"]),
        })

    if result.get("on_wr") and result.get("off_wr"):
        result["lift_vs_off"] = round(result["on_wr"] - result["off_wr"], 2)

    if n_on >= 2:
        result.update(roi_strip_top(sub_on["sp_decimal"], sub_on["won"]))
        result.update(winner_concentration(sub_on["sp_decimal"], sub_on["won"]))

    return result


# ─── TJ threshold audit ───────────────────────────────────────────────────────

def audit_tj_thresholds(df: pd.DataFrame) -> dict:
    """Compare TJ_HIGH_GLOBAL_D8 vs TJ_HIGH_TODAY_TOP20.

    GLOBAL_D8:    threshold from full 178k raceform distribution (= 0.0847)
    TODAY_TOP20:  80th pct of trainer_jockey_sr values in THIS training dataset
    """
    tj_col = "trainer_jockey_sr"
    if tj_col not in df.columns:
        return {"error": "trainer_jockey_sr not in dataset"}

    tj_covered = df[df[tj_col].notna()].copy()
    n_covered  = len(tj_covered)

    # Load global threshold
    try:
        tj_profile = pd.read_parquet(JTCD_DIR / "trainer_jockey_profile.parquet", columns=["jtc_signal"])
        global_d8 = float(tj_profile["jtc_signal"].quantile(0.80))
    except Exception:
        global_d8 = 0.0847

    # Today (training dataset) threshold
    today_d8 = float(tj_covered[tj_col].quantile(0.80))

    result = {
        "n_tj_covered":          n_covered,
        "n_total":               len(df),
        "coverage_pct":          round(n_covered / len(df) * 100, 1),
        "global_d8_threshold":   round(global_d8, 6),
        "today_d8_threshold":    round(today_d8, 6),
        "tj_distribution": {
            "min":  round(float(tj_covered[tj_col].min()), 4),
            "p20":  round(float(tj_covered[tj_col].quantile(0.20)), 4),
            "p50":  round(float(tj_covered[tj_col].median()), 4),
            "p80":  round(float(tj_covered[tj_col].quantile(0.80)), 4),
            "p90":  round(float(tj_covered[tj_col].quantile(0.90)), 4),
            "max":  round(float(tj_covered[tj_col].max()), 4),
        },
    }

    for name, threshold in [("global_d8", global_d8), ("today_top20", today_d8)]:
        high = tj_covered[tj_covered[tj_col] >= threshold]
        low  = tj_covered[tj_covered[tj_col] <  threshold]
        n_h, n_l = len(high), len(low)
        result[f"{name}"] = {
            "threshold":     round(threshold, 6),
            "n_high":        n_h,
            "n_low":         n_l,
            "pct_of_covered": round(n_h / n_covered * 100, 1) if n_covered else None,
            "high_wr":   round(high["won"].mean() * 100, 2) if n_h else None,
            "high_roi":  roi(high["sp_decimal"], high["won"]) if n_h else None,
            "low_wr":    round(low["won"].mean()  * 100, 2) if n_l else None,
            "low_roi":   roi(low["sp_decimal"],  low["won"])  if n_l else None,
        }
        if n_h and n_l:
            result[f"{name}"]["lift_high_vs_low"] = round(
                result[f"{name}"]["high_wr"] - result[f"{name}"]["low_wr"], 2
            )
        if n_h >= 2:
            result[f"{name}"].update(roi_strip_top(high["sp_decimal"], high["won"]))
            result[f"{name}"].update(winner_concentration(high["sp_decimal"], high["won"]))

    result["diagnosis"] = (
        "THRESHOLD_TOO_LOW"
        if result["global_d8"]["pct_of_covered"] > 60
        else "THRESHOLD_OK"
    )
    return result


# ─── SP leakage section ───────────────────────────────────────────────────────

def audit_sp_leakage(df: pd.DataFrame) -> dict:
    """Quantify the SP leakage risk: how much does knowing SP add?"""
    sp = df["sp_decimal"].dropna()
    result: dict = {
        "sp_in_dataset":     True,
        "n_with_sp":         int(sp.notna().sum()),
        "sp_is_pre_race":    False,
        "sp_leakage_risk":   "HIGH",
        "recommendation":    "DO_NOT_USE_SP_AS_FEATURE_IN_PRODUCTION",
        "sp_ok_for":         ["ROI_calculation", "SP_band_stratification", "target_actual_sp"],
    }

    # SP Spearman vs won
    sub = df[["won", "sp_decimal"]].dropna()
    if len(sub) >= 10:
        rho, pval = scipy_stats.spearmanr(sub["sp_decimal"], sub["won"].astype(int))
        result["sp_vs_won_rho"]  = round(float(rho), 4)
        result["sp_vs_won_pval"] = round(float(pval), 4)
        result["sp_vs_won_note"] = (
            "Negative rho expected (lower SP = favourite = more likely to win). "
            "If rho strongly negative, SP is a powerful but post-hoc signal. "
            "Using SP as a feature would rank future predictions by implied odds, not VELO signal."
        )

    # Decile breakdown of SP vs won
    sub2 = sub.copy()
    sub2["sp_decile"] = pd.qcut(sub2["sp_decimal"], q=10, labels=False, duplicates="drop")
    sp_deciles = []
    for d, grp in sub2.groupby("sp_decile"):
        sp_deciles.append({
            "decile": int(d),
            "n": len(grp),
            "mean_sp": round(float(grp["sp_decimal"].mean()), 2),
            "win_rate": round(float(grp["won"].mean()) * 100, 1),
            "roi": roi(grp["sp_decimal"], grp["won"]),
        })
    result["sp_deciles"] = sp_deciles
    return result


# ─── VP continuous audit with SP stratification ───────────────────────────────

def audit_vp_detailed(df: pd.DataFrame) -> dict:
    """VP is the backbone signal. Detailed breakdown with SP bands and SP-excluded validation."""
    base = audit_numeric(df, "velo_prime_prob", "VELO Prime Probability")

    # VP bands (canonical VELO gates)
    vp_bands = {
        "VP<0.20":     df[df["velo_prime_prob"] < 0.20],
        "VP 0.20-0.30": df[(df["velo_prime_prob"] >= 0.20) & (df["velo_prime_prob"] < 0.30)],
        "VP 0.30-0.40": df[(df["velo_prime_prob"] >= 0.30) & (df["velo_prime_prob"] < 0.40)],
        "VP>=0.40":     df[df["velo_prime_prob"] >= 0.40],
        "VP>=0.30":     df[df["velo_prime_prob"] >= 0.30],
    }
    base["vp_bands"] = {}
    for band_label, grp in vp_bands.items():
        n = len(grp)
        n_win = int(grp["won"].sum())
        base["vp_bands"][band_label] = {
            "n": n,
            "win_rate": round(n_win / n * 100, 2) if n else None,
            "roi": roi(grp["sp_decimal"], grp["won"]) if n else None,
        }

    # VP + TJ_HIGH compound
    if "tj_high_flag" in df.columns:
        vp30_tj = df[(df["velo_prime_prob"] >= 0.30) & (df["tj_high_flag"])]
        vp30_no_tj = df[(df["velo_prime_prob"] >= 0.30) & (~df["tj_high_flag"])]
        n_c = len(vp30_tj)
        n_nc = len(vp30_no_tj)
        base["vp30_tj_compound"] = {
            "n": n_c,
            "win_rate": round(vp30_tj["won"].mean() * 100, 2) if n_c else None,
            "roi": roi(vp30_tj["sp_decimal"], vp30_tj["won"]) if n_c else None,
        }
        base["vp30_no_tj"] = {
            "n": n_nc,
            "win_rate": round(vp30_no_tj["won"].mean() * 100, 2) if n_nc else None,
            "roi": roi(vp30_no_tj["sp_decimal"], vp30_no_tj["won"]) if n_nc else None,
        }

    return base


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    today = date.today()
    print(f"\nRUNNER_MASTER_FEATURE_AUDIT_V1 — {today}")
    print("=" * 62)

    df = pd.read_parquet(TRAIN_PATH)
    n_total = len(df)
    n_win   = int(df["won"].sum())
    baseline_wr = round(n_win / n_total * 100, 2)
    baseline_roi = roi(df["sp_decimal"], df["won"])
    print(f"Dataset: {n_total} rows | {n_win} winners | WR={baseline_wr}% | ROI={baseline_roi}%")

    # ── Map user-facing column names ──────────────────────────────────────────
    # The training dataset uses API column names; expose both names in report
    col_map = {
        "current_or":  "ofr_api",
        "current_ts":  "ts_api",
        "current_rpr": "rpr_api",
    }
    for friendly, actual in col_map.items():
        if actual in df.columns and friendly not in df.columns:
            df[friendly] = df[actual]

    # ── Signal audit definitions ──────────────────────────────────────────────
    numeric_signals = [
        ("velo_prime_prob",    "VELO Prime Prob"),
        ("trainer_jockey_sr",  "TJ Partnership SR"),
        ("ts_slope_6",         "TS Slope (last-6)"),
        ("or_slope_6",         "OR Slope (last-6)"),
        ("rpr_slope_6",        "RPR Slope (last-6)"),
        ("or_drop_from_peak",  "OR Drop from Peak"),
        ("ts_vs_or_gap",       "TS vs OR Gap"),
        ("current_or",         "Current OR"),
        ("current_ts",         "Current TS"),
        ("current_rpr",        "Current RPR"),
    ]

    flag_signals = [
        ("silent_improver_flag",    "Silent Improver"),
        ("rating_rebound_flag",     "Rating Rebound"),
        ("exposed_regression_flag", "Exposed Regression"),
        ("mds_high_flag",           "MDS High"),
        ("tj_high_flag",            "TJ HIGH (global D8)"),
    ]

    # ── Run audits ────────────────────────────────────────────────────────────
    print("\nAuditing numeric signals...")
    numeric_results = []
    for col, label in numeric_signals:
        if col not in df.columns:
            print(f"  SKIP {label} — column not found")
            continue
        r = audit_numeric(df, col, label)
        numeric_results.append(r)
        lift = r.get("top_decile_lift")
        rho  = r.get("spearman_rho")
        print(f"  {label:<28} n={r['n']:4d} cov={r['coverage_pct']:4.0f}% "
              f"rho={rho:+.3f} top_decile_lift={f'{lift:+.1f}pp' if lift is not None else 'n/a'}")

    print("\nAuditing flag signals...")
    flag_results = []
    for col, label in flag_signals:
        if col not in df.columns:
            print(f"  SKIP {label} — column not found")
            continue
        r = audit_flag(df, col, label)
        flag_results.append(r)
        wr_on = r.get("on_wr")
        lift  = r.get("lift_vs_off")
        roi_on = r.get("on_roi")
        verdict = r.get("verdict", "?")
        print(f"  {label:<28} n_true={r['n_flag_true']:4d} "
              f"WR={wr_on:.1f}% lift={f'{lift:+.1f}pp' if lift else 'n/a'} "
              f"ROI={roi_on:.1f}% [{verdict}]" if wr_on else f"  {label:<28} n_true={r['n_flag_true']:4d} [NO_DATA]")

    # ── Compound signals ──────────────────────────────────────────────────────
    print("\nAuditing compound signals...")
    compounds = [
        ("VP≥0.30 + TJ_HIGH",
         [("vp30_flag", "high"), ("tj_high_flag", "high")]),
        ("VP≥0.30 + silent_improver",
         [("vp30_flag", "high"), ("silent_improver_flag", "high")]),
        ("VP≥0.30 + rating_rebound",
         [("vp30_flag", "high"), ("rating_rebound_flag", "high")]),
        ("VP≥0.30 + ts_slope>2",
         [("vp30_flag", "high"), ("ts_slope_6", ">=2")]),
        ("VP≥0.30 + or_drop>3",
         [("vp30_flag", "high"), ("or_drop_from_peak", ">=3")]),
        ("VP≥0.40 + TJ_HIGH",
         [("vp40_flag", "high"), ("tj_high_flag", "high")]),
        ("VP≥0.30 only (no TJ)",
         [("vp30_flag", "high"), ("tj_high_flag", "low")]),
        ("exposed_regression + VP<0.20",
         [("exposed_regression_flag", "high"), ("vp30_flag", "low")]),
    ]
    compound_results = []
    for label, conditions in compounds:
        r = audit_compound(df, conditions, label)
        compound_results.append(r)
        wr_on = r.get("on_wr")
        lift  = r.get("lift_vs_off")
        print(f"  {label:<38} n={r['n_on']:3d} "
              f"WR={wr_on:.1f}% lift={f'{lift:+.1f}pp' if lift else 'n/a'}" if wr_on else
              f"  {label:<38} n={r['n_on']:3d} [NO_DATA]")

    # ── TJ threshold audit ────────────────────────────────────────────────────
    print("\nAuditing TJ threshold (GLOBAL_D8 vs TODAY_TOP20)...")
    tj_audit = audit_tj_thresholds(df)
    g = tj_audit.get("global_d8", {})
    t = tj_audit.get("today_top20", {})
    print(f"  GLOBAL_D8  threshold={tj_audit['global_d8_threshold']:.4f} "
          f"n_high={g.get('n_high',0)} ({g.get('pct_of_covered',0):.0f}% of covered) "
          f"WR={g.get('high_wr')}% ROI={g.get('high_roi')}%")
    print(f"  TODAY_TOP20 threshold={tj_audit['today_d8_threshold']:.4f} "
          f"n_high={t.get('n_high',0)} ({t.get('pct_of_covered',0):.0f}% of covered) "
          f"WR={t.get('high_wr')}% ROI={t.get('high_roi')}%")
    print(f"  DIAGNOSIS: {tj_audit.get('diagnosis')}")

    # ── SP leakage audit ──────────────────────────────────────────────────────
    print("\nAuditing SP leakage risk...")
    sp_audit = audit_sp_leakage(df)
    print(f"  SP vs won Spearman rho={sp_audit.get('sp_vs_won_rho')} "
          f"(pval={sp_audit.get('sp_vs_won_pval')})")
    print(f"  RISK: {sp_audit['sp_leakage_risk']} | Rec: {sp_audit['recommendation']}")

    # ── VP detailed ───────────────────────────────────────────────────────────
    vp_detailed = audit_vp_detailed(df)

    # ── SP feature set comparison ─────────────────────────────────────────────
    # NO_SP: feature set without SP
    # SP_DIAG: feature set including SP as a feature (diagnostic only)
    # We don't run a model here, but we flag what SP correlation would add
    sp_feature_governance = {
        "sp_feature_set_NO_SP": {
            "status": "PRODUCTION_SAFE",
            "sp_decimal_excluded": True,
            "recommendation": "Use this set for any shadow or live model",
        },
        "sp_feature_set_SP_DIAGNOSTIC": {
            "status": "DIAGNOSTIC_ONLY",
            "sp_decimal_included": True,
            "recommendation": "DO_NOT_USE_IN_PRODUCTION_MODEL",
            "reason": (
                "sp_decimal is the realised SP (post-race settlement). "
                "A model trained with SP as a feature learns to rank by market odds, "
                "not by VELO's independent signal. This defeats the purpose. "
                "SP may only be used for ROI calculation (target), SP-band stratification, "
                "or as a post-hoc diagnostic."
            ),
        },
    }

    # ── Build report ──────────────────────────────────────────────────────────
    report = {
        "generated":    today.isoformat(),
        "source":       str(TRAIN_PATH.name),
        "n_rows":       n_total,
        "n_winners":    n_win,
        "baseline_wr":  baseline_wr,
        "baseline_roi": baseline_roi,
        "governance": "NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE",
        "numeric_signals":    numeric_results,
        "flag_signals":       flag_results,
        "compound_signals":   compound_results,
        "tj_threshold_audit": tj_audit,
        "sp_leakage_audit":   sp_audit,
        "vp_detailed":        vp_detailed,
        "sp_feature_governance": sp_feature_governance,
    }

    class _Enc(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, (np.integer,)): return int(o)
            if isinstance(o, (np.floating,)): return float(o)
            if isinstance(o, (np.bool_,)):    return bool(o)
            return super().default(o)

    with open(REPORT_JSON, "w") as f:
        json.dump(report, f, indent=2, cls=_Enc)
    print(f"\nJSON report: {REPORT_JSON.name}")

    # ── Markdown report ───────────────────────────────────────────────────────
    _write_md(report, today)
    print(f"MD report:   {REPORT_MD.name}")
    print(f"\nRUNNER_MASTER_FEATURE_AUDIT_V1 complete.")
    print(f"Governance: NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_STAKING_CHANGE")


# ─── Markdown writer ──────────────────────────────────────────────────────────

def _fmt(v, fmt=".2f", suffix="") -> str:
    if v is None: return "—"
    return f"{v:{fmt}}{suffix}"


def _write_md(report: dict, today: date):
    bwr  = report["baseline_wr"]
    broi = report["baseline_roi"]
    lines = [
        "# runner_master_profile — Feature Audit V1",
        f"**Generated:** {today.isoformat()}  ",
        f"**Governance:** NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_STAKING_CHANGE",
        "",
        "## Baseline",
        f"| | |",
        f"|---|---|",
        f"| Rows | {report['n_rows']:,} |",
        f"| Winners | {report['n_winners']:,} ({bwr}%) |",
        f"| Flat-stake ROI (all sigma) | {broi}% |",
        "",
        "---",
        "",
        "## SP Leakage Governance",
        "",
        "```",
        "sp_decimal = realised Starting Price (post-race settlement)",
        "RISK: HIGH",
        "DO NOT USE SP AS A PREDICTIVE FEATURE IN ANY PRODUCTION/SHADOW MODEL",
        "",
        "SP is approved for:",
        "  ROI calculation (target field)",
        "  SP-band stratification (grouping rows for analysis)",
        "  target: actual_sp",
        "",
        "If pre-race odds are needed as a feature, use:",
        "  odds_at_prediction / live_price_pre_off / forecast_price",
        "  (none currently in dataset — must be ingested separately)",
        "```",
    ]

    sp_a = report.get("sp_leakage_audit", {})
    lines += [
        "",
        f"SP vs won: Spearman rho = {_fmt(sp_a.get('sp_vs_won_rho'), '.4f')} "
        f"(p = {_fmt(sp_a.get('sp_vs_won_pval'), '.4f')})",
        "> Negative rho confirms SP encodes market expectation (lower SP = more likely to win).",
        "> This makes SP a leakage proxy — the model would learn to re-rank by market rather than by VELO signal.",
        "",
        "---",
        "",
        "## TJ Threshold Audit",
    ]

    tj = report.get("tj_threshold_audit", {})
    g  = tj.get("global_d8", {})
    t  = tj.get("today_top20", {})
    diag = tj.get("diagnosis", "?")
    lines += [
        "",
        f"| | GLOBAL_D8 | TODAY_TOP20 |",
        f"|---|---|---|",
        f"| Threshold | {_fmt(tj.get('global_d8_threshold'), '.4f')} | {_fmt(tj.get('today_d8_threshold'), '.4f')} |",
        f"| n_high | {g.get('n_high','—')} | {t.get('n_high','—')} |",
        f"| % of covered | {_fmt(g.get('pct_of_covered'), '.0f')}% | {_fmt(t.get('pct_of_covered'), '.0f')}% |",
        f"| Win rate | {_fmt(g.get('high_wr'), '.1f')}% | {_fmt(t.get('high_wr'), '.1f')}% |",
        f"| ROI | {_fmt(g.get('high_roi'), '.1f')}% | {_fmt(t.get('high_roi'), '.1f')}% |",
        f"| Lift vs low | {_fmt(g.get('lift_high_vs_low'), '+.1f')}pp | {_fmt(t.get('lift_high_vs_low'), '+.1f')}pp |",
        f"| Strip-top ROI | {_fmt(g.get('roi_stripped'), '.1f')}% | {_fmt(t.get('roi_stripped'), '.1f')}% |",
        "",
        f"**Diagnosis: {diag}**",
        "",
        "---",
        "",
        "## Numeric Signals",
        "",
        "| Signal | n | Cov% | Winner mean | Loser mean | Spearman ρ | Top-decile lift | Top-decile ROI |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for r in report.get("numeric_signals", []):
        lines.append(
            f"| {r['label']} | {r['n']} | {r['coverage_pct']:.0f}% "
            f"| {_fmt(r.get('winner_mean'), '.3f')} | {_fmt(r.get('loser_mean'), '.3f')} "
            f"| {_fmt(r.get('spearman_rho'), '+.4f')} {'*' if r.get('spearman_sig') else ''}"
            f"| {_fmt(r.get('top_decile_lift'), '+.1f')}pp | {_fmt(r.get('top_decile_roi'), '.1f')}% |"
        )

    lines += [
        "",
        "## Flag Signals",
        "",
        "| Signal | n (true) | Flag % | WR on | WR off | Lift | ROI on | ROI off | Verdict |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in report.get("flag_signals", []):
        lines.append(
            f"| {r['label']} | {r['n_flag_true']} | {_fmt(r.get('flag_rate'), '.1f')}% "
            f"| {_fmt(r.get('on_wr'), '.1f')}% | {_fmt(r.get('off_wr'), '.1f')}% "
            f"| {_fmt(r.get('lift_vs_off'), '+.1f')}pp "
            f"| {_fmt(r.get('on_roi'), '.1f')}% | {_fmt(r.get('off_roi'), '.1f')}% "
            f"| **{r.get('verdict','?')}** |"
        )

    lines += [
        "",
        "## Compound Signals",
        "",
        "| Compound | n | WR | Lift vs base | ROI | Strip-top ROI |",
        "|---|---|---|---|---|---|",
    ]
    for r in report.get("compound_signals", []):
        wr = r.get("on_wr")
        lift = r.get("lift_vs_off")
        base_roi = r.get("on_roi")
        strip = r.get("roi_stripped")
        lines.append(
            f"| {r['label']} | {r['n_on']} "
            f"| {_fmt(wr, '.1f')}% | {_fmt(lift, '+.1f')}pp "
            f"| {_fmt(base_roi, '.1f')}% | {_fmt(strip, '.1f')}% |"
        )

    lines += [
        "",
        "## VP Band Truth (this dataset)",
        "",
        "| VP Band | n | Win rate | ROI |",
        "|---|---|---|---|",
    ]
    vp_bands = report.get("vp_detailed", {}).get("vp_bands", {})
    for band, stats in vp_bands.items():
        lines.append(
            f"| {band} | {stats['n']} "
            f"| {_fmt(stats.get('win_rate'), '.1f')}% "
            f"| {_fmt(stats.get('roi'), '.1f')}% |"
        )

    vp30_tj = report.get("vp_detailed", {}).get("vp30_tj_compound", {})
    vp30_no = report.get("vp_detailed", {}).get("vp30_no_tj", {})
    lines += [
        "",
        "## VP×TJ Compound (this dataset)",
        "",
        "| | n | Win rate | ROI |",
        "|---|---|---|---|",
        f"| VP≥0.30 + TJ_HIGH (global D8) | {vp30_tj.get('n','—')} "
        f"| {_fmt(vp30_tj.get('win_rate'), '.1f')}% | {_fmt(vp30_tj.get('roi'), '.1f')}% |",
        f"| VP≥0.30 + no TJ_HIGH | {vp30_no.get('n','—')} "
        f"| {_fmt(vp30_no.get('win_rate'), '.1f')}% | {_fmt(vp30_no.get('roi'), '.1f')}% |",
        "",
        "---",
        "",
        "## Next Steps",
        "1. Review TJ threshold diagnosis — if THRESHOLD_TOO_LOW, use TODAY_TOP20 for shadow model",
        "2. Features with positive Spearman rho AND positive top-decile ROI → candidate model features",
        "3. Flags with POSITIVE_SIGNAL verdict → include in shadow model feature set",
        "4. Features with NEGATIVE_SIGNAL or neutral → deprioritise or drop",
        "5. Step 5: train on rolling date split only (never random split)",
        "6. NO sp_decimal as predictive feature in any production/shadow model",
    ]

    with open(REPORT_MD, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
