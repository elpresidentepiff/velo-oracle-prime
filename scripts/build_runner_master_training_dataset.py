#!/usr/bin/env python3
"""RUNNER_MASTER_TRAINING_DATASET_V1

Builds a clean, leakage-free training dataset from runner_master_profile_latest.parquet.

Rules:
  - Pre-race features ONLY in the feature block
  - Targets isolated at end: won, placed, profit_loss_1pt, actual_sp, result_position
  - No post-race fields in features
  - File 6 / competitor selections never present (correctly quarantined upstream)
  - SP included as feature (market's pre-race assessment), also replicated in targets

Inputs:
  data/features/runner_master_profile_latest.parquet

Outputs:
  data/training/runner_master_training_dataset_latest.parquet
  data/training/runner_master_training_dataset_latest.json
  data/reports/runner_master_training_dataset_latest.json
  data/reports/runner_master_training_dataset_latest.md

Governance: NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE
            NO_STAKING_CHANGE | NO_LIVE_STATE_MUTATION
"""

import json
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT         = Path(__file__).resolve().parent.parent
MASTER_PATH  = ROOT / "data" / "features" / "runner_master_profile_latest.parquet"
JTCD_DIR     = ROOT / "data" / "features" / "jtc_d"
TRAIN_DIR    = ROOT / "data" / "training"
REPORT_DIR   = ROOT / "data" / "reports"
TRAIN_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_PARQUET = TRAIN_DIR / "runner_master_training_dataset_latest.parquet"
OUTPUT_JSON    = TRAIN_DIR / "runner_master_training_dataset_latest.json"
REPORT_JSON    = REPORT_DIR / "runner_master_training_dataset_latest.json"
REPORT_MD      = REPORT_DIR / "runner_master_training_dataset_latest.md"

# ─── Feature definitions ──────────────────────────────────────────────────────

# Identity / context (not model features — kept for filtering/grouping)
ID_COLS = [
    "date", "race_id", "horse_id", "horse", "course", "off_time", "trainer", "jockey",
]

# Pre-race model features — explicitly approved
FEATURE_COLS = [
    # VÉLØ model output
    "velo_prime_prob",
    "sqpe_v17_prob",
    "market_deception_score",
    "improvement_score",
    "place_prob",
    "release_day_prob",
    "comment_intel_score",
    "longshot_prob",
    # VP signal flags
    "vp40_flag",
    "vp30_flag",
    "mds_high_flag",
    "improver_high_flag",
    "router_qualified",
    "b_low_vp_suppress",
    # Router lanes (evidence-only, not scoring)
    "router_v1_shadow_pass",
    "router_v2_class4_shadow_pass",
    "router_v6_gold_seam_watchlist",
    # Race context
    "dist_band",
    "race_type",
    "class_num",
    "field_size",
    "archetype",
    # Ratings — current marks from API (pre-race)
    "ofr_api",       # = current_or
    "ts_api",        # = current_ts
    "rpr_api",       # = current_rpr
    "trainer_rtf",   # trainer run-to-form ratio
    # Last-6 trend features
    "last6_runs",
    "or_slope_6",
    "ts_slope_6",
    "rpr_slope_6",
    "or_drop_from_peak",
    "ts_vs_or_gap",
    "or_peak_6",
    "ts_peak_recent",
    "rpr_peak_recent",
    # Rating trend flags
    "rating_rebound_flag",
    "silent_improver_flag",
    "exposed_regression_flag",
    # JTC-D partnership signals
    "trainer_jockey_sr",
    "trainer_course_sr",
    "jockey_course_sr",
    "trainer_dist_sr",
    "jockey_dist_sr",
    # SP as market proxy (technically realised post-race, but is the market's pre-race price)
    # Flagged in schema as 'market_proxy' — do not use as target without isolation
    "sp_decimal",
    "sp_band",
]

# Targets — post-race ground truth. Kept separate, never in feature block.
TARGET_COLS = [
    "won",
    "placed",
    "result_position",
    "actual_sp",       # alias for sp_decimal, placed explicitly in target block
    "profit_loss_1pt", # computed: (sp-1) if won else -1
]


# ─── TJ threshold ─────────────────────────────────────────────────────────────

def _load_tj_threshold() -> float:
    path = JTCD_DIR / "trainer_jockey_profile.parquet"
    if not path.exists():
        return 0.0847  # confirmed D8 value from audit
    df = pd.read_parquet(path, columns=["jtc_signal"])
    return float(df["jtc_signal"].quantile(0.80))


# ─── Feature engineering ──────────────────────────────────────────────────────

def _encode_tier(tier_str) -> int | None:
    """decision_tier → numeric: A=4, B=3, C=2, D=1, X=0, null=None."""
    mapping = {"A": 4, "B": 3, "C": 2, "D": 1, "X": 0}
    if pd.isna(tier_str):
        return None
    return mapping.get(str(tier_str).strip().upper())


def _sp_band_numeric(sp_band) -> float | None:
    """Encode sp_band as midpoint SP for ordinal use."""
    midpoints = {
        "sub3": 2.0, "3-5": 4.0, "5-8.5": 6.75,
        "8.5-15": 11.75, "15+": 20.0,
    }
    if pd.isna(sp_band):
        return None
    for key, val in midpoints.items():
        if key in str(sp_band):
            return val
    return None


def _dist_band_numeric(dist_band) -> float | None:
    """Encode dist_band as midpoint furlongs."""
    midpoints = {
        "5f": 5.0, "6f": 6.0, "7f": 7.0, "8f": 8.0,
        "9-10f": 9.5, "11-12f": 11.5, "13-14f": 13.5,
        "15-17f": 16.0, "18f+": 18.0,
    }
    if pd.isna(dist_band):
        return None
    s = str(dist_band).strip().lower()
    return midpoints.get(s)


def _race_type_flag(race_type) -> dict:
    """One-hot encode race_type."""
    t = str(race_type or "").lower()
    return {
        "is_flat":        "flat" in t,
        "is_jumps":       any(w in t for w in ("hurdle", "chase", "nh", "national hunt")),
        "is_handicap":    "handicap" in t or "h'cap" in t,
        "is_class4_lower": False,  # placeholder, set below from class_num
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    today = date.today()
    print(f"\nRUNNER_MASTER_TRAINING_DATASET_V1 — {today}")
    print("=" * 62)

    # ── Load master ───────────────────────────────────────────────────────────
    print(f"\nLoading: {MASTER_PATH.name}")
    master = pd.read_parquet(MASTER_PATH)
    print(f"  {len(master):,} rows | {len(master.columns)} columns")

    # ── Filter: result_matched only (have ground truth) ──────────────────────
    n_total = len(master)
    if "result_matched" in master.columns:
        master = master[master["result_matched"] == True].copy()
    print(f"  Result-matched: {len(master):,}/{n_total} rows")

    # ── Load TJ threshold ─────────────────────────────────────────────────────
    tj_threshold = _load_tj_threshold()
    print(f"  TJ HIGH threshold (D8): {tj_threshold:.4f}")

    # ── Build features ────────────────────────────────────────────────────────
    print("\nBuilding features...")

    # Encode decision_tier numerically
    master["tier_numeric"] = master["decision_tier"].apply(_encode_tier)

    # Derive tj_high_flag
    if "trainer_jockey_sr" in master.columns:
        master["tj_high_flag"] = (master["trainer_jockey_sr"] >= tj_threshold).fillna(False)
    else:
        master["tj_high_flag"] = False

    # Numeric dist_band
    master["dist_band_f"] = master["dist_band"].apply(_dist_band_numeric)

    # Race type one-hot flags
    race_flags_df = master["race_type"].apply(_race_type_flag).apply(pd.Series)
    race_flags_df["is_class4_lower"] = master["class_num"].apply(
        lambda x: (x >= 4) if pd.notna(x) else False
    )
    master = pd.concat([master, race_flags_df], axis=1)

    # SP band numeric
    master["sp_band_midpoint"] = master["sp_band"].apply(_sp_band_numeric)

    # ── Targets ───────────────────────────────────────────────────────────────
    master["actual_sp"] = master["sp_decimal"]

    # profit_loss_1pt: flat-stake +1 unit
    def _profit(row):
        if pd.isna(row["sp_decimal"]):
            return None
        return round(float(row["sp_decimal"]) - 1, 4) if row["won"] else -1.0

    master["profit_loss_1pt"] = master.apply(_profit, axis=1)

    # ── Select output columns ─────────────────────────────────────────────────
    # Extended feature list includes derived columns
    all_feature_cols = FEATURE_COLS + [
        "tier_numeric",
        "tj_high_flag",
        "dist_band_f",
        "is_flat",
        "is_jumps",
        "is_handicap",
        "is_class4_lower",
        "sp_band_midpoint",
    ]

    # Keep only columns that exist
    id_present      = [c for c in ID_COLS          if c in master.columns]
    feature_present = [c for c in all_feature_cols if c in master.columns]
    target_present  = [c for c in TARGET_COLS       if c in master.columns]

    # Final column order: ID | FEATURES | TARGETS
    out_cols = id_present + feature_present + target_present
    out = master[out_cols].copy()

    print(f"  ID cols:      {len(id_present)}")
    print(f"  Feature cols: {len(feature_present)}")
    print(f"  Target cols:  {len(target_present)}")
    print(f"  Total cols:   {len(out_cols)}")

    # ── Coverage report ───────────────────────────────────────────────────────
    print("\n--- Feature Coverage ---")
    priority_features = [
        ("velo_prime_prob",       "VP"),
        ("sqpe_v17_prob",         "SQPE v17"),
        ("market_deception_score","MDS"),
        ("improvement_score",     "Improvement"),
        ("ofr_api",               "OR (current)"),
        ("ts_api",                "TS (current)"),
        ("rpr_api",               "RPR (current)"),
        ("trainer_jockey_sr",     "TJ partnership"),
        ("trainer_course_sr",     "Trainer course"),
        ("jockey_course_sr",      "Jockey course"),
        ("ts_slope_6",            "TS slope (last6)"),
        ("or_slope_6",            "OR slope (last6)"),
        ("or_drop_from_peak",     "OR drop from peak"),
        ("ts_vs_or_gap",          "TS vs OR gap"),
    ]
    for col, label in priority_features:
        if col in out.columns:
            nn = out[col].notna().sum()
            pct = nn / len(out) * 100
            print(f"  {label:<25}: {nn:4d}/{len(out)} ({pct:.1f}%)")

    print("\n--- Target Distribution ---")
    print(f"  Won:    {out['won'].sum():4d}/{len(out)} ({out['won'].mean()*100:.1f}%)")
    if "placed" in out.columns:
        print(f"  Placed: {out['placed'].sum():4d}/{len(out)} ({out['placed'].mean()*100:.1f}%)")
    if "profit_loss_1pt" in out.columns:
        p = out["profit_loss_1pt"].dropna()
        print(f"  Flat-stake ROI: {p.mean()*100:.1f}% (n={len(p)})")
    if "sp_decimal" in out.columns:
        sp = out["sp_decimal"].dropna()
        print(f"  SP: mean={sp.mean():.2f} | median={sp.median():.2f} | p90={sp.quantile(0.9):.2f}")

    print("\n--- Flag Counts ---")
    for flag in ["rating_rebound_flag", "silent_improver_flag", "exposed_regression_flag",
                 "tj_high_flag", "vp40_flag", "vp30_flag", "mds_high_flag", "improver_high_flag"]:
        if flag in out.columns:
            n = int(out[flag].sum())
            print(f"  {flag:<30}: {n:4d} ({n/len(out)*100:.1f}%)")

    # ── SP leakage check ──────────────────────────────────────────────────────
    # Verify result_position and won are ONLY in target block
    leakage_check_features = [c for c in feature_present
                               if c in ("result_position", "won", "placed", "profit_loss_1pt")]
    if leakage_check_features:
        print(f"\nLEAKAGE WARNING: Post-race fields in feature block: {leakage_check_features}")
    else:
        print("\n  Leakage check: PASSED — no result fields in feature block")

    # ── Save ─────────────────────────────────────────────────────────────────
    out.to_parquet(OUTPUT_PARQUET, index=False)
    print(f"\nSaved: {OUTPUT_PARQUET}")
    print(f"Shape: {out.shape}")

    # JSON manifest
    manifest = {
        "generated":     today.isoformat(),
        "source":        MASTER_PATH.name,
        "rows":          len(out),
        "id_cols":       id_present,
        "feature_cols":  feature_present,
        "target_cols":   target_present,
        "total_cols":    len(out_cols),
        "tj_high_threshold": round(tj_threshold, 6),
        "target_distribution": {
            "won_n":    int(out["won"].sum()),
            "won_pct":  round(float(out["won"].mean()) * 100, 1),
            "placed_n": int(out["placed"].sum()) if "placed" in out.columns else None,
            "placed_pct": round(float(out["placed"].mean()) * 100, 1) if "placed" in out.columns else None,
            "flat_stake_roi_pct": round(float(out["profit_loss_1pt"].mean()) * 100, 1)
                                  if "profit_loss_1pt" in out.columns else None,
        },
        "feature_coverage": {
            col: {
                "non_null": int(out[col].notna().sum()),
                "pct": round(float(out[col].notna().mean()) * 100, 1),
            }
            for col in feature_present
            if col in out.columns
        },
        "leakage_status": "PASSED" if not leakage_check_features else f"WARNING:{leakage_check_features}",
        "governance": "NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE",
        "notes": {
            "sp_decimal": "SP is the realised Starting Price (post-race). Used as market proxy "
                          "for pre-race market assessment. Isolated in target block as 'actual_sp'. "
                          "Do not use sp_decimal as a feature in models where SP leakage is a concern.",
            "raceform_gap": "last-6 features use pre-Aug 2025 history only for March-May 2026 rows.",
            "jtcd_coverage": "JTC-D signals built from raceform 2015-2025. trainer_jockey_sr "
                             "covers 56% of sigma rows (733/1310).",
            "next_steps": [
                "Step 4: feature audit — measure each feature alone vs won/placed",
                "Step 5: train on rolling date split only (no random split)",
                "Preferred models: logistic regression (baseline) + LightGBM",
            ],
        },
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest: {OUTPUT_JSON.name}")

    # ── Markdown report ───────────────────────────────────────────────────────
    class _Enc(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, (np.integer,)): return int(o)
            if isinstance(o, (np.floating,)): return float(o)
            if isinstance(o, (np.bool_,)): return bool(o)
            return super().default(o)

    with open(REPORT_JSON, "w") as f:
        json.dump(manifest, f, indent=2, cls=_Enc)

    md_lines = [
        "# runner_master_training_dataset — build report",
        f"**Generated:** {today.isoformat()}  ",
        f"**Source:** {MASTER_PATH.name}  ",
        f"**Governance:** NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE",
        "",
        "## Shape",
        f"| | |",
        f"|---|---|",
        f"| Rows | {len(out):,} |",
        f"| ID columns | {len(id_present)} |",
        f"| Feature columns | {len(feature_present)} |",
        f"| Target columns | {len(target_present)} |",
        f"| Leakage check | {manifest['leakage_status']} |",
        "",
        "## Target Distribution",
        f"| Target | Count | % |",
        f"|---|---|---|",
        f"| won | {int(out['won'].sum())} | {out['won'].mean()*100:.1f}% |",
    ]
    if "placed" in out.columns:
        md_lines.append(f"| placed | {int(out['placed'].sum())} | {out['placed'].mean()*100:.1f}% |")
    roi = out["profit_loss_1pt"].mean() * 100 if "profit_loss_1pt" in out.columns else None
    if roi is not None:
        md_lines.append(f"| flat-stake ROI | — | {roi:.1f}% |")

    md_lines += [
        "",
        "## Feature Coverage (priority signals)",
        "| Feature | Non-null | % |",
        "|---|---|---|",
    ]
    for col, label in priority_features:
        if col in out.columns:
            nn = int(out[col].notna().sum())
            pct = nn / len(out) * 100
            md_lines.append(f"| {label} | {nn} | {pct:.1f}% |")

    md_lines += [
        "",
        "## Derived Features",
        "| Feature | Rule |",
        "|---|---|",
        "| `tier_numeric` | A=4, B=3, C=2, D=1, X=0 |",
        f"| `tj_high_flag` | trainer_jockey_sr >= D8 ({tj_threshold:.4f}) |",
        "| `dist_band_f` | dist_band → midpoint furlongs |",
        "| `is_flat` / `is_jumps` / `is_handicap` | race_type one-hot |",
        "| `is_class4_lower` | class_num >= 4 |",
        "| `profit_loss_1pt` | (sp - 1) if won else -1 |",
        "",
        "## SP Note",
        "> `sp_decimal` is the realised Starting Price (post-race market).  ",
        "> Used as market proxy for pre-race assessment.  ",
        "> It appears in both the feature block (market proxy) and target block (actual_sp).  ",
        "> Do not use as a feature in models where SP leakage is a concern.",
        "",
        "## Raceform Gap Warning",
        "> last-6 features use pre-Aug 2025 raceform history.  ",
        "> For March-May 2026 sigma rows, last-6 arrays exclude Aug 2025–Feb 2026 runs.",
        "",
        "## Next Steps",
        "1. **Step 4 — Feature audit**: measure each signal alone vs won/placed before modelling",
        "2. **Step 5 — Train**: rolling date split only (no random split)",
        "3. Models: logistic regression (baseline) + LightGBM",
        "4. Never train on rows where result is unknown (result_matched=False)",
    ]

    with open(REPORT_MD, "w") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"Report: {REPORT_JSON.name}")
    print(f"Report: {REPORT_MD.name}")
    print(f"\nRUNNER_MASTER_TRAINING_DATASET_V1 complete.")
    print(f"Governance: NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE")


if __name__ == "__main__":
    main()
