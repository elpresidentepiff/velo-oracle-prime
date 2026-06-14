#!/usr/bin/env python3
"""
new_build_core_v0_or_dataset.py
Challenger dataset: Core V0 + official_rating + is_rated flag.
Merges numeric OR from raceform_clean where available.
Shadow only. No RPR. No SP. No post-race leakage.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd

OUT_DIR = ROOT / "data" / "new_build" / "training"
RPT_DIR = ROOT / "data" / "new_build" / "reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRUST_POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
VELO_SCORING_ALLOWED = False

# Same base features as Core V0 champion
CORE_V0_BASE_FEATURES = [
    "dist_f", "going_code", "is_aw", "field_size", "draw_num", "draw_pct",
    "age_num", "wgt_lbs", "or_vs_field",
    "release_window_score", "going_fit_score", "distance_fit_score",
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    "setup_run_flag", "cash_run_flag",
]

# New OR features for challenger
OR_FEATURES = ["official_rating", "is_rated"]

IDENTITY_COLS = ["race_id", "date", "course", "horse", "jockey", "trainer"]
BANNED = {"rpr_num", "rpr_vs_field", "rpr", "ts_num", "ts",
          "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav",
          "pos", "ovr_btn", "btn", "comment", "time", "target"}


def _parse_pos(s):
    return pd.to_numeric(s, errors="coerce")


def run():
    print("Loading raceform_v17_features.parquet ...")
    df = pd.read_parquet(ROOT / "data" / "raceform_v17_features.parquet")
    print(f"  Loaded: {len(df):,} rows")

    print("Merging or_rating from raceform_clean.parquet ...")
    df_clean = pd.read_parquet(ROOT / "data" / "raceform_clean.parquet",
                               columns=["race_id", "horse", "or_rating"])
    df = df.merge(df_clean, on=["race_id", "horse"], how="left", suffixes=("", "_clean"))

    # Convert or_rating → official_rating numeric (em-dash → NaN → 0 + is_rated flag)
    df["official_rating"] = pd.to_numeric(df["or_rating"], errors="coerce")
    df["is_rated"] = df["official_rating"].notna().astype(int)
    df["official_rating"] = df["official_rating"].fillna(0).astype(float)

    print(f"  official_rating coverage: {(df['is_rated']==1).mean()*100:.1f}% of all rows")

    # Flat only
    df = df[df["type"] == "Flat"].copy()
    print(f"  After Flat filter: {len(df):,} rows")
    print(f"  official_rating (Flat): {(df['is_rated']==1).mean()*100:.1f}% rated")

    # Valid pos
    df["pos_num"] = _parse_pos(df["pos"])
    df = df[df["pos_num"].notna()].copy()
    df["pos_num"] = df["pos_num"].astype(int)

    # Targets
    df["won"] = (df["pos_num"] == 1).astype(int)
    df["framed"] = (df["pos_num"] <= 3).astype(int)

    # Date
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date_dt"].notna()].copy()

    # Anti-leakage
    all_features = CORE_V0_BASE_FEATURES + OR_FEATURES
    for b in BANNED:
        if b in all_features:
            raise AssertionError(f"LEAKAGE ABORT: {b} in feature set")
    rpr_check = [c for c in all_features if "rpr" in c.lower()]
    if rpr_check:
        raise AssertionError(f"RPR VIOLATION: {rpr_check}")
    print(f"  Leakage check: PASS (no RPR, no SP)")

    # Keep only present columns
    present = [c for c in all_features if c in df.columns]
    missing = [c for c in all_features if c not in df.columns]
    if missing:
        print(f"  Missing from df: {missing}")

    # Chronological split
    train_df = df[df["date_dt"].dt.year <= 2023]
    val_df   = df[df["date_dt"].dt.year == 2024]
    test_df  = df[df["date_dt"].dt.year == 2025]

    save_cols = IDENTITY_COLS + present + ["won", "framed", "pos_num"]
    save_cols = [c for c in save_cols if c in df.columns]

    train_df[save_cols].to_parquet(OUT_DIR / "core_v0_or_train.parquet", index=False)
    val_df[save_cols].to_parquet(OUT_DIR / "core_v0_or_val.parquet", index=False)
    test_df[save_cols].to_parquet(OUT_DIR / "core_v0_or_test.parquet", index=False)

    print(f"  Train: {len(train_df):,}  Val: {len(val_df):,}  Test: {len(test_df):,}")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": VELO_SCORING_ALLOWED,
        "rpr_violation": False,
        "sp_violation": False,
        "leakage_check": "PASS",
        "or_diagnosis": "or_rating='–' for unrated horses (maidens/novices). official_rating=numeric OR, is_rated=0/1 flag. or_vs_field retained (100% coverage).",
        "official_rating_coverage_flat": round((df["is_rated"] == 1).mean(), 4),
        "features": present,
        "or_features_added": OR_FEATURES,
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "test_rows": len(test_df),
    }
    (RPT_DIR / "core_v0_or_dataset_latest.json").write_text(json.dumps(report, indent=2))

    lines = [
        "# Core V0_OR Challenger Dataset",
        f"Generated: {report['generated_at']}",
        "",
        "## OR Diagnosis",
        "- `or_rating` in raceform_clean has 100% coverage but 41% are `'–'` (unrated horses: maidens, novice stakes)",
        "- `or_num` in v17_features had 40% nulls — correct, reflects real absence of handicap mark",
        "- Fix: derive `official_rating` (numeric, 0 for unrated) + `is_rated` flag",
        "- `or_vs_field` (relative OR) already in Core V0 at 100% — retained",
        "",
        f"## Coverage",
        f"- official_rating coverage (Flat): {report['official_rating_coverage_flat']*100:.1f}% rated",
        "",
        "## Features Added vs Core V0",
        "- `official_rating` — absolute OR value (0 when unrated)",
        "- `is_rated` — 1 if horse has a handicap mark, 0 otherwise",
        "",
        "## Dataset Size",
        f"| Split | Rows |",
        f"|---|---|",
        f"| Train (2015-2023) | {report['train_rows']:,} |",
        f"| Val (2024) | {report['val_rows']:,} |",
        f"| Test (2025) | {report['test_rows']:,} |",
    ]
    (RPT_DIR / "core_v0_or_dataset_latest.md").write_text("\n".join(lines))
    print("  Dataset written. Reports written.")


if __name__ == "__main__":
    run()
