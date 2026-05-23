#!/usr/bin/env python3
"""
Build International Lagged Rating Features

For each race row, compute lagged (previous-run only) versions of rating features.
This eliminates any risk of current-race RPR/OR/TS being post-race.

Hard rule: for race N of a horse, only races 0 to N-1 are used to compute features.

Lagged features built:
  prev_rpr          — rpr_num from horse's most recent previous run
  max_rpr_last3     — max rpr_num over last 3 runs (excluding current)
  avg_rpr_last3     — avg rpr_num over last 3 runs
  prev_or           — or_num from previous run
  max_or_last3      — max or_num over last 3 runs
  avg_or_last3      — avg or_num over last 3 runs
  prev_ts           — ts_num from previous run
  max_ts_last3      — max ts_num over last 3 runs
  avg_ts_last3      — avg ts_num over last 3 runs
  days_since_last_run — days between current and previous race
  starts_last_90    — number of starts in previous 90 days
  course_prior_runs — total prior runs at this course
  course_prior_wr   — prior win rate at this course
  dist_prior_runs   — total prior runs at this distance band
  dist_prior_wr     — prior win rate at this distance band

Static features passed through (pre-race, no lag needed):
  draw_num, draw_pct, field_size, dist_f, going_code, wgt_lbs, age_num, is_aw,
  class_num (when available), course, date, race_id, horse, target, is_fav

Outputs:
  data/features/international_lagged_rating_features.parquet
  data/reports/international_lagged_rating_features_latest.json
  data/reports/international_lagged_rating_features_latest.md

Usage:
    PYTHONPATH=. python scripts/build_international_lagged_rating_features.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PQ_PATH = ROOT / "data" / "raceform_v17_features.parquet"

RATING_COLS = ["rpr_num", "or_num", "ts_num"]

STATIC_PASS_THROUGH = [
    "race_id", "horse", "course", "date", "date_parsed", "target",
    "draw_num", "draw_pct", "field_size", "dist_f", "going_code",
    "wgt_lbs", "age_num", "is_aw", "class_num", "is_fav",
    "type",
]

DIST_BAND_BREAKPOINTS = [0, 6, 8, 10, 12, 14, 100]
DIST_BAND_LABELS = ["5f-6f", "7f-8f", "9f-10f", "11f-12f", "13f-14f", "15f+"]


def _dist_band(dist_f: float) -> str:
    for i in range(len(DIST_BAND_BREAKPOINTS) - 1):
        if DIST_BAND_BREAKPOINTS[i] <= dist_f < DIST_BAND_BREAKPOINTS[i + 1]:
            return DIST_BAND_LABELS[i]
    return "15f+"


def build_lagged_features(df: pd.DataFrame) -> pd.DataFrame:
    print("[Lagged] Sorting by horse + date...")
    df = df.copy()
    df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(["horse", "date_parsed"]).reset_index(drop=True)

    print("[Lagged] Building lagged rating features...")
    for col in RATING_COLS:
        if col not in df.columns:
            continue
        g = df.groupby("horse")[col]
        df[f"prev_{col}"] = g.shift(1)
        df[f"max_{col}_last3"] = g.transform(lambda x: x.shift(1).rolling(3, min_periods=1).max())
        df[f"avg_{col}_last3"] = g.transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())

    print("[Lagged] Building days_since_last_run...")
    df["_prev_date"] = df.groupby("horse")["date_parsed"].shift(1)
    df["days_since_last_run"] = (df["date_parsed"] - df["_prev_date"]).dt.days
    df.drop(columns=["_prev_date"], inplace=True)

    print("[Lagged] Building starts_last_90...")
    def _starts_last_90(group: pd.DataFrame) -> pd.Series:
        result = []
        dates = group["date_parsed"].values
        for i, d in enumerate(dates):
            cutoff = d - pd.Timedelta(days=90)
            prior_dates = dates[:i]
            count = int(np.sum(prior_dates >= cutoff))
            result.append(count)
        return pd.Series(result, index=group.index)

    df["starts_last_90"] = df.groupby("horse", group_keys=False).apply(_starts_last_90)

    print("[Lagged] Building course prior records...")
    df["dist_band"] = df["dist_f"].apply(lambda x: _dist_band(x) if pd.notna(x) else "unknown")

    def _prior_records(group: pd.DataFrame, key_col: str) -> tuple[pd.Series, pd.Series]:
        prior_runs = []
        prior_wins = []
        key_history: dict[str, list] = {}
        for i, row in enumerate(group.itertuples()):
            key = getattr(row, key_col, None)
            if key not in key_history:
                key_history[key] = []
            runs = len(key_history[key])
            wins = sum(key_history[key])
            prior_runs.append(runs)
            prior_wins.append(wins)
            key_history[key].append(row.target)
        return (
            pd.Series(prior_runs, index=group.index),
            pd.Series([w / max(r, 1) for w, r in zip(prior_wins, prior_runs)], index=group.index),
        )

    course_runs_list = []
    course_wr_list = []
    dist_runs_list = []
    dist_wr_list = []

    for horse_name, group in df.groupby("horse"):
        c_runs, c_wr = _prior_records(group, "course")
        d_runs, d_wr = _prior_records(group, "dist_band")
        course_runs_list.append(c_runs)
        course_wr_list.append(c_wr)
        dist_runs_list.append(d_runs)
        dist_wr_list.append(d_wr)

    df["course_prior_runs"] = pd.concat(course_runs_list)
    df["course_prior_wr"] = pd.concat(course_wr_list)
    df["dist_prior_runs"] = pd.concat(dist_runs_list)
    df["dist_prior_wr"] = pd.concat(dist_wr_list)

    return df


def main() -> None:
    print("[Lagged] Loading parquet...")
    df = pd.read_parquet(PQ_PATH)
    print(f"[Lagged] Rows: {len(df):,}")

    df_lagged = build_lagged_features(df)

    # Select output columns
    lagged_feature_cols = [
        "prev_rpr_num", "max_rpr_num_last3", "avg_rpr_num_last3",
        "prev_or_num", "max_or_num_last3", "avg_or_num_last3",
        "prev_ts_num", "max_ts_num_last3", "avg_ts_num_last3",
        "days_since_last_run", "starts_last_90",
        "course_prior_runs", "course_prior_wr",
        "dist_prior_runs", "dist_prior_wr",
    ]

    static_cols = [c for c in STATIC_PASS_THROUGH if c in df_lagged.columns]
    output_cols = static_cols + [c for c in lagged_feature_cols if c in df_lagged.columns]

    out_df = df_lagged[output_cols].copy()

    print(f"\n[Lagged] Output rows: {len(out_df):,}")
    print(f"[Lagged] Output columns: {len(output_cols)}")

    out_dir = ROOT / "data" / "features"
    out_dir.mkdir(exist_ok=True)

    pq_path = out_dir / "international_lagged_rating_features.parquet"
    out_df.to_parquet(pq_path, index=False)
    print(f"[Lagged] Written: {pq_path}")

    # Report
    lag_coverage = {}
    for col in lagged_feature_cols:
        if col in out_df.columns:
            cov = (out_df[col].notna() & out_df[col].ne(0)).mean()
            lag_coverage[col] = round(float(cov), 4)

    out_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_rows": int(len(out_df)),
        "total_cols": int(len(output_cols)),
        "lagged_feature_coverage": lag_coverage,
        "method": (
            "For each horse sorted by date, lagged features use only races 0..N-1. "
            "Current-race RPR/OR/TS excluded. Static race attributes passed through."
        ),
    }

    report_dir = ROOT / "data" / "reports"
    report_dir.mkdir(exist_ok=True)

    json_path = report_dir / "international_lagged_rating_features_latest.json"
    json_path.write_text(json.dumps(out_report, indent=2, default=str))
    print(f"[Lagged] Report: {json_path}")

    md = _write_md(out_report, lag_coverage)
    md_path = report_dir / "international_lagged_rating_features_latest.md"
    md_path.write_text(md)
    print(f"[Lagged] Report: {md_path}")

    print("\n[Lagged] Coverage summary:")
    for col, cov in lag_coverage.items():
        print(f"  {col:35s}: {cov:.2%}")


def _write_md(out: dict, coverage: dict) -> str:
    cov_rows = "\n".join(f"| {c} | {v:.2%} |" for c, v in coverage.items())
    return f"""# International Lagged Rating Features

**Generated:** {out['generated_at']}
**Rows:** {out['total_rows']:,}
**Columns:** {out['total_cols']}

---

## Method

{out['method']}

Lagged features use ONLY previous-run data. For race N of a horse:
- `prev_rpr_num` = the rpr_num value from the horse's most recent prior race
- `max_rpr_num_last3` = max rpr_num over the 3 runs before this race
- `avg_rpr_num_last3` = avg rpr_num over the 3 runs before this race
- Same for `or_num` and `ts_num`
- `course_prior_wr` = win rate at this course in ALL prior runs (strict lag)
- `dist_prior_wr` = win rate at this distance band in ALL prior runs (strict lag)

**The current race's rpr_num, or_num, ts_num are NOT used.**

---

## Feature Coverage

| Feature | Coverage |
|---|---|
{cov_rows}

---

```
LAGGED_FEATURES_STATUS: BUILT
CURRENT_RACE_RATINGS: EXCLUDED
OUTPUT: data/features/international_lagged_rating_features.parquet
```
"""


if __name__ == "__main__":
    main()
