#!/usr/bin/env python3
"""
new_build_core_v0_dataset.py
Build the safe Core V0 historical training dataset from raceform_v17_features.parquet.
Flat races only. No RPR. No final SP. No post-race leakage.
Shadow only — outputs are archive/training only, never live scoring.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

OUT_DIR = ROOT / "data" / "new_build" / "training"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RPT_DIR = ROOT / "data" / "new_build" / "reports"
RPT_DIR.mkdir(parents=True, exist_ok=True)

TRUST_POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
VELO_SCORING_ALLOWED = False

# Safe pre-race features for Core V0 morning model (no SP, no RPR, no post-race)
CORE_V0_FEATURES = [
    "type", "class_num", "dist_f", "going_code", "is_aw",
    "field_size", "draw_num", "draw_pct", "age_num", "wgt_lbs",
    "or_num", "or_vs_field", "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "mark_compression_score", "runs_since_win", "runs_since_place",
    "release_window_score", "course_fit_score", "going_fit_score",
    "distance_fit_score", "quiet_run_score", "trainer_timing_score",
    "jockey_switch_intent", "setup_run_flag", "cash_run_flag",
]

IDENTITY_COLS = ["race_id", "date", "course", "horse", "jockey", "trainer"]

BANNED = {"rpr_num", "rpr_vs_field", "rpr", "ts_num", "ts",
          "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav",
          "odds_resilience_score", "odds_contraction_score", "decoy_support_flag",
          "runs_since_mkt_support", "pos", "ovr_btn", "btn", "comment", "time", "target"}


def _parse_pos(pos_series):
    """Convert pos column (object) to int — non-numeric → NaN."""
    return pd.to_numeric(pos_series, errors="coerce")


def run():
    print("Loading raceform_v17_features.parquet ...")
    df = pd.read_parquet(ROOT / "data" / "raceform_v17_features.parquet")
    print(f"  Loaded: {len(df):,} rows")

    # Anti-leakage assertion
    for banned in BANNED:
        if banned in CORE_V0_FEATURES:
            raise AssertionError(f"LEAKAGE: {banned} is in CORE_V0_FEATURES — abort")

    # Flat only
    df = df[df["type"] == "Flat"].copy()
    print(f"  After Flat filter: {len(df):,} rows")

    # Parse pos, filter to valid finishers
    df["pos_num"] = _parse_pos(df["pos"])
    df = df[df["pos_num"].notna()].copy()
    df["pos_num"] = df["pos_num"].astype(int)
    print(f"  After valid pos filter: {len(df):,} rows")

    # Targets
    df["won"] = (df["pos_num"] == 1).astype(int)
    df["framed"] = (df["pos_num"] <= 3).astype(int)

    # Parse date
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date_dt"].notna()].copy()

    # Check null coverage for feature columns — drop cols >30% null
    present_features = [c for c in CORE_V0_FEATURES if c in df.columns]
    missing_features = [c for c in CORE_V0_FEATURES if c not in df.columns]
    null_rates = {c: df[c].isna().mean() for c in present_features}
    high_null = [c for c, r in null_rates.items() if r > 0.30]
    kept_features = [c for c in present_features if c not in high_null]

    print(f"  Features: {len(kept_features)} kept, {len(high_null)} dropped (>30% null), {len(missing_features)} missing from parquet")
    if high_null:
        print(f"  High-null dropped: {high_null}")
    if missing_features:
        print(f"  Missing from parquet: {missing_features}")

    # Chronological split
    train_df = df[df["date_dt"].dt.year <= 2023].copy()
    val_df   = df[df["date_dt"].dt.year == 2024].copy()
    test_df  = df[df["date_dt"].dt.year == 2025].copy()

    print(f"  Train 2015-2023: {len(train_df):,} rows, {train_df['race_id'].nunique():,} races")
    print(f"  Val  2024:       {len(val_df):,} rows,  {val_df['race_id'].nunique():,} races")
    print(f"  Test 2025:       {len(test_df):,} rows,  {test_df['race_id'].nunique():,} races")

    save_cols = IDENTITY_COLS + kept_features + ["won", "framed", "pos_num"]
    save_cols = [c for c in save_cols if c in df.columns]

    full_ds = df[save_cols].copy()
    full_ds.to_parquet(OUT_DIR / "core_v0_historical_dataset.parquet", index=False)
    train_df[save_cols].to_parquet(OUT_DIR / "core_v0_train.parquet", index=False)
    val_df[save_cols].to_parquet(OUT_DIR / "core_v0_val.parquet", index=False)
    test_df[save_cols].to_parquet(OUT_DIR / "core_v0_test.parquet", index=False)

    target_dist = {
        "win_rate_overall": round(float(full_ds["won"].mean()), 4),
        "win_rate_train": round(float(train_df["won"].mean()), 4),
        "win_rate_val": round(float(val_df["won"].mean()), 4),
        "win_rate_test": round(float(test_df["won"].mean()), 4),
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": VELO_SCORING_ALLOWED,
        "rpr_in_features": any("rpr" in c.lower() for c in kept_features),
        "sp_in_features": any(c in kept_features for c in ["sp_dec", "log_sp", "is_fav", "sp_rank"]),
        "leakage_check": "PASS",
        "total_rows": len(full_ds),
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "test_rows": len(test_df),
        "total_races": int(full_ds["race_id"].nunique()),
        "train_races": int(train_df["race_id"].nunique()),
        "val_races": int(val_df["race_id"].nunique()),
        "test_races": int(test_df["race_id"].nunique()),
        "total_horses": int(full_ds["horse"].nunique()),
        "date_range": f"{full_ds['date'].min()} → {full_ds['date'].max()}",
        "features_kept": kept_features,
        "features_dropped_high_null": high_null,
        "features_missing_from_parquet": missing_features,
        "target_distribution": target_dist,
    }

    (RPT_DIR / "core_v0_historical_dataset_latest.json").write_text(json.dumps(report, indent=2))

    lines = [
        "# Core V0 Historical Dataset",
        f"Generated: {report['generated_at']}",
        "",
        "## Dataset Size",
        f"- **Total rows**: {report['total_rows']:,}",
        f"- **Total races**: {report['total_races']:,}",
        f"- **Total horses**: {report['total_horses']:,}",
        f"- **Date range**: {report['date_range']}",
        "",
        "## Splits",
        f"| Split | Rows | Races |",
        f"|---|---|---|",
        f"| Train (2015-2023) | {report['train_rows']:,} | {report['train_races']:,} |",
        f"| Val (2024) | {report['val_rows']:,} | {report['val_races']:,} |",
        f"| Test (2025) | {report['test_rows']:,} | {report['test_races']:,} |",
        "",
        "## Leakage Audit",
        f"- RPR in features: **{report['rpr_in_features']}** (must be False)",
        f"- SP in features: **{report['sp_in_features']}** (must be False for morning model)",
        f"- Result: **{report['leakage_check']}**",
        "",
        "## Target Distribution",
        f"- Win rate overall: {target_dist['win_rate_overall']:.1%}",
        f"- Win rate train: {target_dist['win_rate_train']:.1%}",
        "",
        "## Features Kept",
        f"**{len(kept_features)} features:**",
        "",
    ]
    for f in kept_features:
        lines.append(f"- `{f}`")
    if high_null:
        lines += ["", f"## Dropped (>30% null): {high_null}"]

    (RPT_DIR / "core_v0_historical_dataset_latest.md").write_text("\n".join(lines))
    print("\nDataset built. Reports written.")
    return report


if __name__ == "__main__":
    run()
