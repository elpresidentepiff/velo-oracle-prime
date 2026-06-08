#!/usr/bin/env python3
"""
new_build_passport_features.py
Build horse-passport-style lag features from raceform_v17_features.parquet.
These are historical per-horse features safe to use at inference time (no current-race leakage).

Passport features computed (all use only PRIOR runs, not current race):
  pp_career_runs       — number of prior career starts
  pp_win_rate          — career win rate up to this race
  pp_place_rate        — career place rate up to this race
  pp_days_since_last   — days since previous race (NaN for debut)
  pp_layoff            — 1 if days_since_last > 90 else 0
  pp_avg_sp_last5      — mean SP over last 5 prior runs (historical SP, not current)
  pp_jockey_continuity — 1 if same jockey as last race
  pp_course_seen       — 1 if horse has run at this course before
  pp_or_change_3       — or_num minus or_num from 3 races ago (form direction)
  pp_class_moved_up    — 1 if class_num < class_num of last race (stepped up)
  pp_class_moved_down  — 1 if class_num > class_num of last race (dropped down)

Output: data/new_build/training/passport_features.parquet
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

PASSPORT_COLS = [
    "pp_career_runs",
    "pp_win_rate",
    "pp_place_rate",
    "pp_days_since_last",
    "pp_layoff",
    "pp_avg_sp_last5",
    "pp_jockey_continuity",
    "pp_course_seen",
    "pp_or_change_3",
    "pp_class_moved_up",
    "pp_class_moved_down",
]


def _won(pos_series):
    return (pd.to_numeric(pos_series, errors="coerce") == 1).astype(float)


def _placed(pos_series):
    return (pd.to_numeric(pos_series, errors="coerce") <= 3).astype(float)


def run():
    print("Loading raceform_v17_features.parquet ...")
    df = pd.read_parquet(ROOT / "data" / "raceform_v17_features.parquet")
    print(f"  Loaded: {len(df):,} rows")

    # Parse date
    df["date_dt"] = pd.to_datetime(df["date_parsed"] if "date_parsed" in df.columns else df["date"], errors="coerce")
    df = df[df["date_dt"].notna()].copy()

    # Sort by horse + date (ascending) for lag computation
    print("  Sorting by horse + date ...")
    df = df.sort_values(["horse", "date_dt", "race_id"]).reset_index(drop=True)

    # Binary win/place from pos
    df["_won"]    = _won(df["pos"])
    df["_placed"] = _placed(df["pos"])

    print("  Computing passport features ...")

    grp = df.groupby("horse", sort=False)

    # --- career runs (count of prior races, 0 for debut) ---
    df["pp_career_runs"] = grp.cumcount()  # 0 for first race, 1 for second...

    # --- cumulative win / place rate (shifted so current race excluded) ---
    cum_wins   = grp["_won"].cumsum().shift(1).fillna(0)
    cum_places = grp["_placed"].cumsum().shift(1).fillna(0)
    career     = df["pp_career_runs"].clip(lower=1)  # avoid /0
    df["pp_win_rate"]   = (cum_wins   / career).where(df["pp_career_runs"] > 0, np.nan)
    df["pp_place_rate"] = (cum_places / career).where(df["pp_career_runs"] > 0, np.nan)

    # --- days since last run ---
    df["pp_days_since_last"] = grp["date_dt"].diff().dt.days.astype(float)
    df["pp_layoff"] = (df["pp_days_since_last"] > 90).astype(float)
    df.loc[df["pp_days_since_last"].isna(), "pp_layoff"] = np.nan  # debut = unknown

    # --- avg SP of last 5 prior runs (historical SP, not current) ---
    if "sp_dec" in df.columns:
        sp_shifted = grp["sp_dec"].shift(1)
        df["pp_avg_sp_last5"] = (
            sp_shifted.groupby(df["horse"])
            .transform(lambda s: s.rolling(5, min_periods=1).mean())
        )
    else:
        df["pp_avg_sp_last5"] = np.nan

    # --- jockey continuity (same jockey as previous race) ---
    if "jockey" in df.columns:
        prev_jockey = grp["jockey"].shift(1)
        df["pp_jockey_continuity"] = (df["jockey"] == prev_jockey).astype(float)
        df.loc[df["pp_career_runs"] == 0, "pp_jockey_continuity"] = np.nan
    else:
        df["pp_jockey_continuity"] = np.nan

    # --- course seen before ---
    if "course" in df.columns:
        # cumcount of times horse ran at this course BEFORE this race
        df["_course_key"] = df["horse"] + "||" + df["course"].astype(str)
        df["pp_course_seen"] = (
            df.groupby("_course_key").cumcount() > 0
        ).astype(float)
        df.drop(columns=["_course_key"], inplace=True)
    else:
        df["pp_course_seen"] = np.nan

    # --- OR change over last 3 races ---
    if "or_num" in df.columns:
        or_shifted   = grp["or_num"].shift(1)
        or_3_back    = grp["or_num"].shift(3)
        df["pp_or_change_3"] = or_shifted - or_3_back
    else:
        df["pp_or_change_3"] = np.nan

    # --- class movement ---
    if "class_num" in df.columns:
        prev_class = grp["class_num"].shift(1)
        diff = df["class_num"] - prev_class
        df["pp_class_moved_up"]   = (diff < 0).astype(float)
        df["pp_class_moved_down"] = (diff > 0).astype(float)
        # debut: unknown
        df.loc[df["pp_career_runs"] == 0, ["pp_class_moved_up", "pp_class_moved_down"]] = np.nan
    else:
        df["pp_class_moved_up"]   = np.nan
        df["pp_class_moved_down"] = np.nan

    # Output: keep only join key + passport cols
    out = df[["race_id", "horse"] + PASSPORT_COLS].copy()

    print(f"  Output rows: {len(out):,}")
    print("  Coverage (non-null %):")
    for col in PASSPORT_COLS:
        pct = out[col].notna().mean() * 100
        print(f"    {col:<28} {pct:.1f}%")

    out_path = OUT_DIR / "passport_features.parquet"
    out.to_parquet(out_path, index=False)
    print(f"\n  Saved → {out_path.relative_to(ROOT)}")

    # Quick stats
    print(f"\n  pp_career_runs: median={out['pp_career_runs'].median():.0f}  max={out['pp_career_runs'].max():.0f}")
    print(f"  pp_win_rate:    mean={out['pp_win_rate'].mean():.3f}")
    print(f"  pp_avg_sp_last5: mean={out['pp_avg_sp_last5'].mean():.2f}")
    print(f"  pp_layoff=1:    {(out['pp_layoff']==1).mean()*100:.1f}%")


if __name__ == "__main__":
    run()
