#!/usr/bin/env python3
"""
new_build_intent_features.py
Build Intent Layer V1 features from raceform history.

Two signal groups:

GROUP A — Already computed in raceform_v17_features, not in champion:
  mark_compression_score      OR near last winning mark
  curr_or_minus_last_win_or   distance below winning mark
  curr_or_minus_best_or       distance below career best OR
  runs_since_win              runs without a win (timing)
  runs_since_place            runs without a place
  runs_since_mkt_support      runs without market backing
  odds_resilience_score       historical SP consistency
  odds_contraction_score      SP shortening vs expected
  decoy_support_flag          binary: mkt backed but underperformed

GROUP B — New, computed from horse-sorted history:
  intent_trip_match           today's dist_f == dist_f at last win
  intent_course_win_history   count of wins at today's course
  intent_going_match          today's going within 0.5 of last win going
  intent_class_drop_vs_best   class improvement vs best winning class
  intent_run_after_break      run number since last layoff (1/2/3/4+)
  intent_sp_shortening        avg SP last 3 shorter than avg SP last 6
  intent_wins_last10          wins in last 10 races
  intent_top3_last6           top-3 finishes in last 6 races

Output: data/new_build/training/intent_features.parquet
Join key: race_id + horse
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

OUT_DIR = ROOT / "data" / "new_build" / "training"
OUT_DIR.mkdir(parents=True, exist_ok=True)

GROUP_A = [
    "mark_compression_score", "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "runs_since_win", "runs_since_place", "runs_since_mkt_support",
    "odds_resilience_score",
    # odds_contraction_score BANNED: uses current race SP → leakage
    # decoy_support_flag BANNED: uses current race is_fav → leakage
]

GROUP_B = [
    "intent_trip_match", "intent_course_win_history", "intent_going_match",
    "intent_class_drop_vs_best", "intent_run_after_break",
    "intent_sp_shortening", "intent_wins_last10", "intent_top3_last6",
]

ALL_INTENT = GROUP_A + GROUP_B


def _pos_numeric(s):
    return pd.to_numeric(s, errors="coerce")


def run():
    print("Loading raceform_v17_features.parquet ...")
    df = pd.read_parquet(ROOT / "data" / "raceform_v17_features.parquet")
    print(f"  Loaded: {len(df):,} rows")

    df["date_dt"] = pd.to_datetime(
        df.get("date_parsed", df["date"]), errors="coerce"
    )
    df = df[df["date_dt"].notna()].copy()

    df["pos_num"] = _pos_numeric(df["pos"])
    df["_won"]    = (df["pos_num"] == 1).astype(float)
    df["_top3"]   = (df["pos_num"] <= 3).astype(float)

    print("  Sorting by horse + date ...")
    df = df.sort_values(["horse", "date_dt", "race_id"]).reset_index(drop=True)

    grp = df.groupby("horse", sort=False)
    career_idx = grp.cumcount()  # 0-based: 0 = debut

    # ── GROUP B — new intent features ─────────────────────────────────────────

    print("  Computing GROUP B intent features ...")

    # --- intent_trip_match: today's dist_f == last winning dist_f ---
    if "dist_f" in df.columns:
        # For each row: dist_f of the most recent PRIOR win
        last_win_dist = pd.Series(np.nan, index=df.index)
        last_win_going = pd.Series(np.nan, index=df.index)
        last_win_class = pd.Series(np.nan, index=df.index)

        for horse_name, sub_idx in grp.groups.items():
            sub = df.loc[sub_idx]
            win_dist_vals  = np.where(sub["_won"].values == 1, sub["dist_f"].values, np.nan)
            win_going_vals = np.where(sub["_won"].values == 1,
                                       sub["going_code"].values if "going_code" in df.columns else np.nan,
                                       np.nan)
            win_class_vals = np.where(sub["_won"].values == 1,
                                       sub["class_num"].values if "class_num" in df.columns else np.nan,
                                       np.nan)
            # ffill shifted by 1 so current race is excluded
            last_win_dist.loc[sub_idx]  = pd.Series(win_dist_vals,  index=sub_idx).shift(1).ffill().values
            last_win_going.loc[sub_idx] = pd.Series(win_going_vals, index=sub_idx).shift(1).ffill().values
            last_win_class.loc[sub_idx] = pd.Series(win_class_vals, index=sub_idx).shift(1).ffill().values

        df["intent_trip_match"]  = (df["dist_f"] == last_win_dist).astype(float)
        df.loc[last_win_dist.isna(), "intent_trip_match"] = np.nan

        if "going_code" in df.columns:
            going_diff = (df["going_code"] - last_win_going).abs()
            df["intent_going_match"] = (going_diff <= 0.5).astype(float)
            df.loc[last_win_going.isna(), "intent_going_match"] = np.nan
        else:
            df["intent_going_match"] = np.nan

        if "class_num" in df.columns:
            class_diff = last_win_class - df["class_num"]
            df["intent_class_drop_vs_best"] = class_diff  # positive = dropped in class vs best win
            df.loc[last_win_class.isna(), "intent_class_drop_vs_best"] = np.nan
        else:
            df["intent_class_drop_vs_best"] = np.nan
    else:
        df["intent_trip_match"] = np.nan
        df["intent_going_match"] = np.nan
        df["intent_class_drop_vs_best"] = np.nan

    # --- intent_course_win_history: wins at today's course before this race ---
    if "course" in df.columns:
        df["_course_key"] = df["horse"] + "||" + df["course"].astype(str)
        df["_course_cumwins"] = (
            df.groupby("_course_key")["_won"]
            .transform(lambda s: s.shift(1).cumsum().fillna(0))
        )
        df["intent_course_win_history"] = df["_course_cumwins"]
        df.drop(columns=["_course_key", "_course_cumwins"], inplace=True)
    else:
        df["intent_course_win_history"] = np.nan

    # --- intent_run_after_break: run count since last layoff (>90 days) ---
    if "date_dt" in df.columns:
        days_gap = grp["date_dt"].diff().dt.days
        layoff_flag = (days_gap > 90)
        run_after = pd.Series(np.nan, index=df.index)
        for horse_name, sub_idx in grp.groups.items():
            sub_layoff = layoff_flag.loc[sub_idx]
            counter = 0
            vals = []
            for i, (idx, is_layoff) in enumerate(sub_layoff.items()):
                if i == 0:
                    vals.append(np.nan)
                    continue
                if is_layoff:
                    counter = 1
                else:
                    if counter > 0:
                        counter += 1
                vals.append(float(counter) if counter > 0 else np.nan)
            run_after.loc[sub_idx] = vals
        df["intent_run_after_break"] = run_after
    else:
        df["intent_run_after_break"] = np.nan

    # --- intent_sp_shortening: avg SP last 3 < avg SP last 6 ---
    if "sp_dec" in df.columns:
        sp_shift = grp["sp_dec"].shift(1)
        avg3 = sp_shift.groupby(df["horse"]).transform(
            lambda s: s.rolling(3, min_periods=2).mean()
        )
        avg6 = sp_shift.groupby(df["horse"]).transform(
            lambda s: s.rolling(6, min_periods=3).mean()
        )
        df["intent_sp_shortening"] = (avg3 < avg6).astype(float)
        df.loc[avg3.isna() | avg6.isna(), "intent_sp_shortening"] = np.nan
    else:
        df["intent_sp_shortening"] = np.nan

    # --- intent_wins_last10 and intent_top3_last6 ---
    won_shift  = grp["_won"].shift(1)
    top3_shift = grp["_top3"].shift(1)
    df["intent_wins_last10"] = won_shift.groupby(df["horse"]).transform(
        lambda s: s.rolling(10, min_periods=3).sum()
    )
    df["intent_top3_last6"] = top3_shift.groupby(df["horse"]).transform(
        lambda s: s.rolling(6, min_periods=2).sum()
    )
    # debut / early career → NaN for these
    df.loc[career_idx < 3,  "intent_wins_last10"] = np.nan
    df.loc[career_idx < 2,  "intent_top3_last6"]  = np.nan

    # ── Output ────────────────────────────────────────────────────────────────
    present_a = [c for c in GROUP_A if c in df.columns]
    present_b = [c for c in GROUP_B if c in df.columns]
    present_all = present_a + present_b

    out = df[["race_id", "horse"] + present_all].copy()

    print(f"  Output rows: {len(out):,}")
    print("  Coverage (non-null %):")
    for col in present_all:
        pct = out[col].notna().mean() * 100
        tag = "  [A]" if col in GROUP_A else "  [B]"
        print(f"    {col:<35} {pct:5.1f}%{tag}")

    out_path = OUT_DIR / "intent_features.parquet"
    out.to_parquet(out_path, index=False)
    print(f"\n  Saved → {out_path.relative_to(ROOT)}")
    print(f"  Total intent features: {len(present_all)}  ({len(present_a)} existing + {len(present_b)} new)")


if __name__ == "__main__":
    run()
