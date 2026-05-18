#!/usr/bin/env python3
"""
BUILD_JTC_D_PROFILES_V1

Builds shrinkage-adjusted Jockey/Trainer/Course/Distance lookup tables
from raceform_v17_features.parquet (1.7M rows, 2015-2025).

Shrinkage formula:
  adjusted_sr = (wins + PRIOR_WINS) / (runs + PRIOR_RUNS)
  confidence   = min(1.0, log(1 + runs) / log(1 + CONFIDENCE_N))
  jtc_signal   = adjusted_sr * confidence

Outputs (data/features/jtc_d/):
  trainer_course_profile.parquet
  trainer_dist_profile.parquet
  jockey_course_profile.parquet
  jockey_dist_profile.parquet
  trainer_jockey_profile.parquet

Usage:
  python scripts/build_jtc_d_profiles.py [--source-years N]
"""
import argparse
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "raceform_v17_features.parquet"
OUT_DIR = ROOT / "data" / "features" / "jtc_d"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Shrinkage prior: 20% baseline, n=25 equivalent
PRIOR_WINS = 5
PRIOR_RUNS = 25
CONFIDENCE_N = 50


def _shrinkage(wins: pd.Series, runs: pd.Series) -> pd.DataFrame:
    adj_sr = (wins + PRIOR_WINS) / (runs + PRIOR_RUNS)
    confidence = (runs.apply(lambda r: min(1.0, math.log(1 + r) / math.log(1 + CONFIDENCE_N))))
    return pd.DataFrame({
        "wins": wins,
        "runs": runs,
        "raw_sr": (wins / runs).round(4),
        "adj_sr": adj_sr.round(4),
        "confidence": confidence.round(4),
        "jtc_signal": (adj_sr * confidence).round(4),
    })


def _dist_band(dist_f: pd.Series) -> pd.Series:
    """Bin dist_f (furlongs) into canonical distance groups."""
    bins = [0, 5.5, 6.5, 7.5, 8.5, 10.5, 12.5, 14.5, 17.5, 999]
    labels = ["5f", "6f", "7f", "8f", "9-10f", "11-12f", "13-14f", "15-17f", "18f+"]
    return pd.cut(dist_f, bins=bins, labels=labels, right=False)


def build_trainer_course(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["trainer", "course"]).agg(wins=("target", "sum"), runs=("target", "count"))
    stats = _shrinkage(g["wins"], g["runs"])
    return g.join(stats.drop(columns=["wins", "runs"])).reset_index()


def build_trainer_dist(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["dist_band"] = _dist_band(df["dist_f"])
    g = df.groupby(["trainer", "dist_band"]).agg(wins=("target", "sum"), runs=("target", "count"))
    stats = _shrinkage(g["wins"], g["runs"])
    return g.join(stats.drop(columns=["wins", "runs"])).reset_index()


def build_jockey_course(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["jockey", "course"]).agg(wins=("target", "sum"), runs=("target", "count"))
    stats = _shrinkage(g["wins"], g["runs"])
    return g.join(stats.drop(columns=["wins", "runs"])).reset_index()


def build_jockey_dist(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["dist_band"] = _dist_band(df["dist_f"])
    g = df.groupby(["jockey", "dist_band"]).agg(wins=("target", "sum"), runs=("target", "count"))
    stats = _shrinkage(g["wins"], g["runs"])
    return g.join(stats.drop(columns=["wins", "runs"])).reset_index()


def build_trainer_jockey(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["trainer", "jockey"]).agg(wins=("target", "sum"), runs=("target", "count"))
    stats = _shrinkage(g["wins"], g["runs"])
    return g.join(stats.drop(columns=["wins", "runs"])).reset_index()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-years", type=int, default=10,
                        help="Use only last N years of history (default: all)")
    args = parser.parse_args()

    print(f"JTC-D PROFILE BUILD V1")
    print("=" * 60)
    print(f"Loading: {SOURCE}")

    cols = ["trainer", "jockey", "course", "dist_f", "target", "date"]
    df = pd.read_parquet(SOURCE, columns=cols)
    df = df.dropna(subset=["trainer", "jockey", "course", "dist_f", "target"])
    df["target"] = df["target"].astype(int)

    if args.source_years < 10:
        cutoff = pd.Timestamp.now() - pd.DateOffset(years=args.source_years)
        df = df[pd.to_datetime(df["date"]) >= cutoff]
        print(f"Filtered to last {args.source_years} years: {len(df):,} rows")
    else:
        print(f"Loaded: {len(df):,} rows ({df['date'].min()} → {df['date'].max()})")

    builds = [
        ("trainer_course_profile.parquet", build_trainer_course),
        ("trainer_dist_profile.parquet", build_trainer_dist),
        ("jockey_course_profile.parquet", build_jockey_course),
        ("jockey_dist_profile.parquet", build_jockey_dist),
        ("trainer_jockey_profile.parquet", build_trainer_jockey),
    ]

    for filename, fn in builds:
        out = OUT_DIR / filename
        result = fn(df)
        result.to_parquet(out, index=False)
        high_conf = result[result["confidence"] >= 0.8]
        print(f"  {filename:<40} {len(result):>7,} groups  "
              f"high-conf(>=0.8): {len(high_conf):,}  → {out.name}")

    print(f"\nWritten to: {OUT_DIR}")
    print("JTC-D profiles ready for rp_runner_profile join.")


if __name__ == "__main__":
    main()
