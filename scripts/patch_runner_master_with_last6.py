#!/usr/bin/env python3
"""Patch runner_master_profile_latest.parquet with last-6 rating spine fields.

Joins:
  data/features/runner_master_profile_latest.parquet
  + data/features/horse_last6_rating_spine.parquet
  on (horse_norm, race_date)

Adds scalar fields (clean for modelling):
  last6_runs, or_slope_6, ts_slope_6, rpr_slope_6,
  or_drop_from_peak, ts_vs_or_gap,
  or_peak_6, ts_peak_recent, rpr_peak_recent,
  rating_rebound_flag, silent_improver_flag, exposed_regression_flag

Adds array fields (JSON strings, useful for diagnostics):
  last_6_or, last_6_ts, last_6_rpr, last_6_pos

Outputs:
  data/features/runner_master_profile_latest.parquet  (updated in-place)
  data/features/runner_master_profile_latest.json
  data/reports/runner_master_last6_patch_latest.json
  data/reports/runner_master_last6_patch_latest.md

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
SPINE_PATH   = ROOT / "data" / "features" / "horse_last6_rating_spine.parquet"
REPORT_JSON  = ROOT / "data" / "reports" / "runner_master_last6_patch_latest.json"
REPORT_MD    = ROOT / "data" / "reports" / "runner_master_last6_patch_latest.md"

_COUNTRY_RE = re.compile(r'\s*\([^)]*\)\s*$')

SCALAR_COLS = [
    "last6_runs",
    "or_slope_6",
    "ts_slope_6",
    "rpr_slope_6",
    "or_drop_from_peak",
    "ts_vs_or_gap",
    "or_peak_6",
    "ts_peak_recent",
    "rpr_peak_recent",
    "rating_rebound_flag",
    "silent_improver_flag",
    "exposed_regression_flag",
]

ARRAY_COLS = [
    "last_6_or",
    "last_6_ts",
    "last_6_rpr",
    "last_6_pos",
]

ALL_NEW_COLS = SCALAR_COLS + ARRAY_COLS


def normalize_name(name: str) -> str:
    return _COUNTRY_RE.sub('', str(name).strip()).strip().lower()


def null_rate(series: pd.Series) -> float:
    return round(series.isna().mean() * 100, 1)


def main():
    today = date.today()
    print(f"\npatch_runner_master_with_last6 — {today}")
    print("=" * 62)

    # ── Load ─────────────────────────────────────────────────────────────────
    print(f"\nLoading master:  {MASTER_PATH.name}")
    master = pd.read_parquet(MASTER_PATH)
    rows_before = len(master)
    cols_before = len(master.columns)
    print(f"  {rows_before:,} rows | {cols_before} columns")

    print(f"\nLoading spine:   {SPINE_PATH.name}")
    spine = pd.read_parquet(SPINE_PATH)
    print(f"  {len(spine):,} rows | {len(spine.columns)} columns")

    # ── Derive join keys ──────────────────────────────────────────────────────
    master["horse_norm"] = master["horse"].apply(normalize_name)

    # Align date columns to string 'YYYY-MM-DD' for safe merge
    master["_join_date"] = pd.to_datetime(master["date"]).dt.strftime("%Y-%m-%d")
    spine["_join_date"]  = pd.to_datetime(spine["race_date"]).dt.strftime("%Y-%m-%d")

    # ── Pre-join overlap check ────────────────────────────────────────────────
    master_keys = set(zip(master["horse_norm"], master["_join_date"]))
    spine_keys  = set(zip(spine["horse_norm"],  spine["_join_date"]))
    overlap     = master_keys & spine_keys
    not_in_spine = master_keys - spine_keys

    print(f"\n  Master unique (horse, date): {len(master_keys):,}")
    print(f"  Spine  unique (horse, date): {len(spine_keys):,}")
    print(f"  Overlap:                     {len(overlap):,} ({len(overlap)/len(master_keys)*100:.1f}%)")
    if not_in_spine:
        print(f"  WARNING: {len(not_in_spine)} master pairs not in spine → will get null last-6 values")
    else:
        print(f"  100% master rows will receive last-6 data")

    # ── Drop existing last-6 cols if already present (re-run safety) ─────────
    already_present = [c for c in ALL_NEW_COLS if c in master.columns]
    if already_present:
        print(f"\n  Dropping {len(already_present)} existing last-6 columns for clean re-join")
        master = master.drop(columns=already_present)
    master = master.drop(columns=["horse_norm"], errors="ignore")

    # ── Join ──────────────────────────────────────────────────────────────────
    print("\nJoining...")
    spine_keep = ["horse_norm", "_join_date"] + ALL_NEW_COLS
    spine_slim  = spine[spine_keep].copy()

    # Deduplicate spine on join key (take first — should already be unique)
    dupes = spine_slim.duplicated(subset=["horse_norm", "_join_date"], keep="first").sum()
    if dupes:
        print(f"  WARNING: {dupes} duplicate join keys in spine — keeping first")
        spine_slim = spine_slim.drop_duplicates(subset=["horse_norm", "_join_date"], keep="first")

    # Re-add horse_norm to master for join, then drop after
    master["horse_norm"] = master["horse"].apply(normalize_name)

    merged = master.merge(
        spine_slim,
        on=["horse_norm", "_join_date"],
        how="left",
        validate="m:1",
    )

    rows_after = len(merged)
    rows_lost  = rows_before - rows_after

    if rows_lost != 0:
        print(f"  CRITICAL: rows_lost={rows_lost} — aborting, master not saved")
        raise RuntimeError(f"Merge produced {rows_after} rows from {rows_before} — check join keys")

    print(f"  Rows before: {rows_before:,} | Rows after: {rows_after:,} | Lost: {rows_lost}")
    print(f"  Columns added: {len(ALL_NEW_COLS)}")

    # ── Clean up join keys ────────────────────────────────────────────────────
    merged = merged.drop(columns=["horse_norm", "_join_date"])

    # ── Coverage stats ────────────────────────────────────────────────────────
    print("\n--- Join Coverage ---")
    n_with_last6 = (merged["last6_runs"] > 0).sum() if "last6_runs" in merged.columns else 0
    n_no_last6   = (merged["last6_runs"] == 0).sum() if "last6_runs" in merged.columns else rows_after
    print(f"  Rows with last6_runs > 0:  {n_with_last6:,} ({n_with_last6/rows_after*100:.1f}%)")
    print(f"  Rows with last6_runs = 0:  {n_no_last6:,} ({n_no_last6/rows_after*100:.1f}%)")

    print("\n--- Null Rates by Added Field ---")
    for col in SCALAR_COLS:
        nr = null_rate(merged[col]) if col in merged.columns else 100.0
        print(f"  {col:<30}: {nr:.1f}%")

    print("\n--- Flag Counts ---")
    for flag in ["rating_rebound_flag", "silent_improver_flag", "exposed_regression_flag"]:
        n = int(merged[flag].sum()) if flag in merged.columns else 0
        pct = n / rows_after * 100
        print(f"  {flag:<30}: {n:4d} ({pct:.1f}%)")

    print("\n--- Slope Distributions (non-null) ---")
    for col in ["or_slope_6", "ts_slope_6", "rpr_slope_6"]:
        s = merged[col].dropna()
        if len(s):
            print(f"  {col}: n={len(s)} mean={s.mean():.2f} "
                  f"p25={s.quantile(0.25):.2f} p75={s.quantile(0.75):.2f}")

    # ── Save updated master ───────────────────────────────────────────────────
    print(f"\nSaving: {MASTER_PATH}")
    merged.to_parquet(MASTER_PATH, index=False)
    print(f"  Shape: {merged.shape}")

    # ── Save JSON manifest ────────────────────────────────────────────────────
    meta_path = MASTER_PATH.with_suffix(".json")
    try:
        with open(meta_path) as f:
            meta = json.load(f)
    except Exception:
        meta = {}

    meta.update({
        "last_patched":         today.isoformat(),
        "patch":                "runner_master_with_last6",
        "rows":                 rows_after,
        "columns":              len(merged.columns),
        "last6_cols_added":     ALL_NEW_COLS,
        "last6_coverage_pct":   round(n_with_last6 / rows_after * 100, 1),
        "rating_rebound_count": int(merged.get("rating_rebound_flag", pd.Series([False] * rows_after)).sum()),
        "silent_improver_count": int(merged.get("silent_improver_flag", pd.Series([False] * rows_after)).sum()),
        "exposed_regression_count": int(merged.get("exposed_regression_flag", pd.Series([False] * rows_after)).sum()),
    })
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  Manifest: {meta_path.name}")

    # ── Build report ──────────────────────────────────────────────────────────
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)

    null_rates_by_col = {
        col: null_rate(merged[col]) if col in merged.columns else 100.0
        for col in SCALAR_COLS
    }

    report = {
        "generated":             today.isoformat(),
        "patch":                 "runner_master_with_last6",
        "governance":            "NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE",
        "master_rows_before":    rows_before,
        "master_rows_after":     rows_after,
        "rows_lost":             rows_lost,
        "cols_before":           cols_before,
        "cols_after":            len(merged.columns),
        "new_cols":              ALL_NEW_COLS,
        "join_coverage": {
            "master_unique_pairs":    len(master_keys),
            "spine_unique_pairs":     len(spine_keys),
            "overlap":                len(overlap),
            "overlap_pct":            round(len(overlap) / len(master_keys) * 100, 1),
            "not_in_spine":           len(not_in_spine),
            "rows_with_last6_data":   n_with_last6,
            "rows_without_last6_data": n_no_last6,
            "last6_coverage_pct":     round(n_with_last6 / rows_after * 100, 1),
        },
        "null_rates": null_rates_by_col,
        "flag_counts": {
            "rating_rebound_flag":        int(merged.get("rating_rebound_flag", pd.Series(dtype=bool)).sum()),
            "silent_improver_flag":       int(merged.get("silent_improver_flag", pd.Series(dtype=bool)).sum()),
            "exposed_regression_flag":    int(merged.get("exposed_regression_flag", pd.Series(dtype=bool)).sum()),
        },
        "slope_stats": {
            col: {
                "n": int(merged[col].notna().sum()),
                "mean": round(float(merged[col].mean()), 3) if merged[col].notna().any() else None,
                "p25":  round(float(merged[col].quantile(0.25)), 3) if merged[col].notna().any() else None,
                "p75":  round(float(merged[col].quantile(0.75)), 3) if merged[col].notna().any() else None,
            }
            for col in ["or_slope_6", "ts_slope_6", "rpr_slope_6"]
            if col in merged.columns
        },
        "raceform_gap_warning": "Aug 2025 – Feb 2026 not covered. Last-6 uses pre-Aug 2025 history for March-May 2026 rows.",
    }

    class _NpEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, (np.bool_,)):
                return bool(obj)
            return super().default(obj)

    with open(REPORT_JSON, "w") as f:
        json.dump(report, f, indent=2, cls=_NpEncoder)

    # ── Markdown report ───────────────────────────────────────────────────────
    md_lines = [
        "# runner_master_profile — last-6 patch report",
        f"**Generated:** {today.isoformat()}  ",
        f"**Governance:** NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE",
        "",
        "## Join Summary",
        f"| | |",
        f"|---|---|",
        f"| Rows before | {rows_before:,} |",
        f"| Rows after  | {rows_after:,} |",
        f"| Rows lost   | **{rows_lost}** |",
        f"| Columns before | {cols_before} |",
        f"| Columns after  | {len(merged.columns)} |",
        f"| New columns    | {len(ALL_NEW_COLS)} |",
        "",
        "## Join Coverage",
        f"| | |",
        f"|---|---|",
        f"| Master unique (horse, date) | {len(master_keys):,} |",
        f"| Spine unique (horse, date)  | {len(spine_keys):,} |",
        f"| Overlap                     | {len(overlap):,} ({round(len(overlap)/len(master_keys)*100,1)}%) |",
        f"| Rows with last-6 data       | {n_with_last6:,} ({round(n_with_last6/rows_after*100,1)}%) |",
        f"| Rows with 0 runs            | {n_no_last6:,} ({round(n_no_last6/rows_after*100,1)}%) |",
        "",
        "## Flag Counts",
        "| Flag | Count | % of master |",
        "|---|---|---|",
    ]

    for flag, label in [
        ("rating_rebound_flag",      "rating_rebound_flag"),
        ("silent_improver_flag",     "silent_improver_flag"),
        ("exposed_regression_flag",  "exposed_regression_flag"),
    ]:
        n = int(merged[flag].sum()) if flag in merged.columns else 0
        md_lines.append(f"| {label} | {n} | {round(n/rows_after*100,1)}% |")

    md_lines += [
        "",
        "## Null Rates by Field",
        "| Field | Null % |",
        "|---|---|",
    ]
    for col, nr in null_rates_by_col.items():
        md_lines.append(f"| {col} | {nr}% |")

    md_lines += [
        "",
        "## Slope Distributions",
        "| Signal | n | mean | p25 | p75 |",
        "|---|---|---|---|---|",
    ]
    for col in ["or_slope_6", "ts_slope_6", "rpr_slope_6"]:
        s = merged[col].dropna() if col in merged.columns else pd.Series(dtype=float)
        if len(s):
            md_lines.append(
                f"| {col} | {len(s)} | {s.mean():.2f} | {s.quantile(0.25):.2f} | {s.quantile(0.75):.2f} |"
            )

    md_lines += [
        "",
        "## Raceform Gap Warning",
        "> Aug 2025 – Feb 2026 not covered by raceform_v17_features.parquet.",
        "> For March-May 2026 sigma rows, last-6 arrays reflect pre-Aug 2025 history only.",
        "",
        "## Next Steps",
        "1. Run feature audit — measure each last-6 signal alone against won/placed",
        "2. Build `data/training/runner_master_training_dataset_latest.parquet`",
        "3. Train only after audit confirms coverage and no leakage",
        "",
        "## Interpretation Guide",
        "| Field | What it means |",
        "|---|---|",
        "| `or_slope_6 < 0` | OR falling — horse being let off by handicapper |",
        "| `or_slope_6 > 0` | OR rising — horse improving, handicapper catching up |",
        "| `ts_slope_6 > 0` | TS improving — horse running better performance figures |",
        "| `or_drop_from_peak > 0` | Current OR below peak — handicap relief |",
        "| `ts_vs_or_gap > 0` | TS above OR — running beyond handicap ceiling |",
        "| `silent_improver_flag` | TS↑ while OR flat/↓ — hidden improver |",
        "| `rating_rebound_flag` | TS V-shape — dip then recovery |",
        "| `exposed_regression_flag` | Both RPR and TS declining |",
    ]

    with open(REPORT_MD, "w") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"\nReport: {REPORT_JSON.name}")
    print(f"Report: {REPORT_MD.name}")
    print(f"\npatch_runner_master_with_last6 complete.")
    print(f"Governance: NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE")


if __name__ == "__main__":
    main()
