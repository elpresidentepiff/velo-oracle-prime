#!/usr/bin/env python3
"""
build_jtc_d_rolling.py
======================
Rebuild JTC-D sidecar parquets with a rolling date window to eliminate
all-time cumulative leakage.

Source: data/new_build/training/core_v0_historical_dataset.parquet
  - 2015-2025 UK/IRE + international
  - Columns: date, trainer, jockey, course, dist_f, won, ...

Output: data/features/jtc_d_rp/
  - trainer_jockey_profile.parquet
  - trainer_course_profile.parquet
  - trainer_dist_profile.parquet
  - jockey_course_profile.parquet
  - jockey_dist_profile.parquet

Rolling window: 365 days from last date in dataset (configurable).
Same column schema as old jtc_d/ files so sidecar tournament can swap in.

SHADOW ONLY — do not use in live scoring until validated in sidecar tournament.

Usage:
    source venv/Scripts/activate
    PYTHONPATH=. python scripts/ops/build_jtc_d_rolling.py
    PYTHONPATH=. python scripts/ops/build_jtc_d_rolling.py --window-days 180
    PYTHONPATH=. python scripts/ops/build_jtc_d_rolling.py --window-days 365 --compare-old
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

SOURCE_PATH  = ROOT / "data" / "new_build" / "training" / "core_v0_historical_dataset.parquet"
OUT_DIR      = ROOT / "data" / "features" / "jtc_d_rp"
OLD_DIR      = ROOT / "data" / "features" / "jtc_d"
REPORT_DIR   = ROOT / "data" / "new_build" / "reports"

PRIOR_N      = 20    # Bayesian pseudo-count (runs)
GLOBAL_SR    = 0.10  # Prior win rate (flat racing ≈ 10%)


def _dist_to_band(dist_f) -> str:
    if pd.isna(dist_f):     return "unknown"
    if dist_f < 5.5:        return "5f"
    if dist_f < 6.5:        return "6f"
    if dist_f < 7.5:        return "7f"
    if dist_f < 8.5:        return "8f"
    if dist_f < 10.5:       return "9-10f"
    if dist_f < 12.5:       return "11-12f"
    if dist_f < 14.5:       return "13-14f"
    if dist_f < 17.5:       return "15-17f"
    return "18f+"


def _bayesian_metrics(grp: pd.DataFrame) -> pd.Series:
    wins = int(grp["won"].sum())
    runs = int(len(grp))
    raw_sr = round(wins / runs, 4) if runs > 0 else 0.0
    adj_sr = round((wins + GLOBAL_SR * PRIOR_N) / (runs + PRIOR_N), 4)
    confidence = round(runs / (runs + PRIOR_N), 4)
    jtc_signal = round(adj_sr * confidence, 4)
    return pd.Series({
        "wins": wins,
        "runs": runs,
        "raw_sr": raw_sr,
        "adj_sr": adj_sr,
        "confidence": confidence,
        "jtc_signal": jtc_signal,
    })


def build_profile(df: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
    grp = df.groupby(key_cols, observed=True).apply(_bayesian_metrics, include_groups=False).reset_index()
    grp["wins"] = grp["wins"].astype(int)
    grp["runs"] = grp["runs"].astype(int)
    grp = grp.sort_values("jtc_signal", ascending=False).reset_index(drop=True)
    return grp


def load_window(window_days: int) -> tuple[pd.DataFrame, str, str]:
    df = pd.read_parquet(SOURCE_PATH)
    df["date"] = pd.to_datetime(df["date"])

    cutoff_dt = df["date"].max()
    start_dt = cutoff_dt - pd.DateOffset(days=window_days)

    df_window = df[(df["date"] >= start_dt) & (df["date"] <= cutoff_dt)].copy()
    df_window["dist_band"] = df_window["dist_f"].apply(_dist_to_band).astype("category")

    cutoff_str = cutoff_dt.strftime("%Y-%m-%d")
    start_str = start_dt.strftime("%Y-%m-%d")

    print(f"Window: {start_str} -> {cutoff_str} ({window_days}d)")
    print(f"  Rows: {len(df_window):,} | "
          f"trainers: {df_window['trainer'].nunique():,} | "
          f"jockeys: {df_window['jockey'].nunique():,}")
    return df_window, start_str, cutoff_str


def build_all(window_days: int, compare_old: bool) -> dict:
    df, start_str, cutoff_str = load_window(window_days)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    tables = {
        "trainer_jockey": (["trainer", "jockey"], "trainer_jockey_profile.parquet"),
        "trainer_course": (["trainer", "course"],  "trainer_course_profile.parquet"),
        "trainer_dist":   (["trainer", "dist_band"], "trainer_dist_profile.parquet"),
        "jockey_course":  (["jockey",  "course"],   "jockey_course_profile.parquet"),
        "jockey_dist":    (["jockey",  "dist_band"], "jockey_dist_profile.parquet"),
    }

    stats = {}
    for name, (keys, fname) in tables.items():
        print(f"\nBuilding {name}...")
        profile = build_profile(df, keys)
        out_path = OUT_DIR / fname
        profile.to_parquet(out_path, index=False)

        top = profile.head(5)[keys + ["wins", "runs", "raw_sr", "adj_sr", "jtc_signal"]]
        print(f"  Rows: {len(profile):,} | saved: {out_path}")
        print(f"  Top 5 by jtc_signal:\n{top.to_string(index=False)}")

        stat = {
            "rows": len(profile),
            "total_wins": int(profile["wins"].sum()),
            "total_runs": int(profile["runs"].sum()),
            "mean_jtc_signal": float(profile["jtc_signal"].mean()),
            "max_jtc_signal": float(profile["jtc_signal"].max()),
            "pct_1run_or_less": float((profile["runs"] <= 1).mean()),
        }
        if compare_old:
            old_path = OLD_DIR / fname
            if old_path.exists():
                old = pd.read_parquet(old_path)
                stat["old_rows"] = len(old)
                stat["delta_rows"] = len(profile) - len(old)
                print(f"  Old: {len(old):,} rows -> New: {len(profile):,} rows "
                      f"(delta={stat['delta_rows']:+,})")
        stats[name] = stat

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": str(SOURCE_PATH),
        "window_days": window_days,
        "window_start": start_str,
        "window_cutoff": cutoff_str,
        "prior_n": PRIOR_N,
        "global_sr": GLOBAL_SR,
        "output_dir": str(OUT_DIR),
        "shadow_only": True,
        "leakage_status": "TEMPORALLY_SAFE",
        "tables": stats,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rpt_path = REPORT_DIR / "jtc_d_rp_build_latest.json"
    rpt_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport: {rpt_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-days", type=int, default=365,
                        help="Rolling window in days from latest date (default 365)")
    parser.add_argument("--compare-old", action="store_true",
                        help="Compare row counts against old jtc_d/ files")
    args = parser.parse_args()

    print("=== JTC-D Rolling Rebuild (SHADOW ONLY) ===")
    report = build_all(args.window_days, args.compare_old)

    print("\n=== Summary ===")
    for name, stat in report["tables"].items():
        print(f"  {name:<22} rows={stat['rows']:>7,}  "
              f"max_signal={stat['max_jtc_signal']:.4f}  "
              f"mean_signal={stat['mean_jtc_signal']:.4f}")
    print(f"\nLeakage status: {report['leakage_status']}")
    print(f"Shadow only:    {report['shadow_only']}")
    print(f"Output:         {report['output_dir']}")


if __name__ == "__main__":
    main()
