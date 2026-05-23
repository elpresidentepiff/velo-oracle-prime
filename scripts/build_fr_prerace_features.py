#!/usr/bin/env python3
"""
Build FR Pre-Race Feature Pack V1

All features are strictly pre-race. Same-race RPR/TS are banned (POST_RACE_LEAKAGE_CONFIRMED).
OR is 0% coverage in FR — not used.

Penetrometer and Quinté+ are not available in the current parquet.
Placeholder columns are written with status=0 to document the future enrichment gap.

Features computed:
  Horse-level lagged (prior runs only):
    lagged_rpr_last1, lagged_rpr_last3_avg, lagged_rpr_last3_max
    lagged_ts_last1, lagged_ts_last3_avg     (only from PRIOR runs — not current race)
    prev_finish_pos, last3_finish_avg
    days_since_last_run, starts_last_90
    prior_course_runs, prior_course_win_rate
    prior_distance_runs, prior_distance_win_rate

  Race context (pre-race by definition):
    going_bucket (numeric going bucketed: fast/good/soft)
    going_is_fast, going_is_good, going_is_soft
    dist_band (distance band)
    is_hurdle, is_chase, is_flat_code

  Placeholders (future PMU/France Galop enrichment):
    penetrometer_available (0 = not yet in parquet)
    quintet_plus_available (0 = not yet in parquet)
    class_proxy_available (0 = class_num 0% in FR)

  Race-level (from lagged runner values):
    field_avg_prev_rpr, field_std_prev_rpr
    rpr_rank_lagged
    race_competitiveness_pre

  Static race attributes (pre-race):
    draw_num, draw_pct, field_size, dist_f, going_code, wgt_lbs, age_num, is_aw

Permanent bans:
  rpr_num (same-race — POST_RACE_LEAKAGE_CONFIRMED for FR)
  ts_num (same-race — POST_RACE_LEAKAGE_CONFIRMED for FR)
  or_num (0% coverage)
  rpr_vs_field, or_vs_field, ts_vs_field
  sp_dec, implied_prob, log_sp, sp_rank
  pos (same-race result)
  is_fav, odds_*, decoy_*, setup_*, cash_run_flag

Courses: Chantilly (FR), Deauville (FR), Longchamp (FR), Saint-Cloud (FR), Auteuil (FR)

Output:
  data/features/fr_prerace_features_v1.parquet
  data/reports/fr_prerace_features_v1.json
  data/reports/fr_prerace_features_v1.md

Usage:
    PYTHONPATH=. python scripts/build_fr_prerace_features.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PQ_PATH = ROOT / "data" / "raceform_v17_features.parquet"

FR_COURSES = [
    "Chantilly (FR)", "Deauville (FR)", "Longchamp (FR)",
    "Saint-Cloud (FR)", "Auteuil (FR)",
]

DIST_BAND_BREAKPOINTS = [0, 6, 8, 10, 12, 14, 100]
DIST_BAND_LABELS = ["5f-6f", "7f-8f", "9f-10f", "11f-12f", "13f-14f", "15f+"]

STATIC_PASS_THROUGH = [
    "race_id", "horse", "course", "date", "date_parsed", "target",
    "draw_num", "draw_pct", "field_size", "dist_f",
    "going_code", "wgt_lbs", "age_num", "is_aw", "type",
]

BANNED_FEATURES = [
    "rpr_num", "ts_num",
    "or_num",
    "rpr_vs_field", "or_vs_field",
    "sp_dec", "implied_prob", "log_sp", "sp_rank",
    "pos",
    "is_fav",
    "odds_contraction_score", "odds_resilience_score",
    "decoy_support_flag", "setup_run_flag", "cash_run_flag",
    "jockey_switch_intent",
]


def _dist_band(dist_f: float) -> str:
    if pd.isna(dist_f):
        return "unknown"
    for i in range(len(DIST_BAND_BREAKPOINTS) - 1):
        if DIST_BAND_BREAKPOINTS[i] <= dist_f < DIST_BAND_BREAKPOINTS[i + 1]:
            return DIST_BAND_LABELS[i]
    return "15f+"


def _going_bucket(going_code: float) -> str:
    if pd.isna(going_code):
        return "unknown"
    if going_code <= 0.0:
        return "fast"    # firm / good-to-firm
    if going_code == 1.0:
        return "good"
    return "soft"        # good-to-soft / soft / heavy


def build_horse_level_lagged(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["pos_num"] = pd.to_numeric(df["pos"], errors="coerce")
    df["place_flag"] = ((df["pos_num"] <= 3) & df["pos_num"].notna()).astype(float)

    df = df.sort_values(["horse", "date_parsed"]).reset_index(drop=True)

    print("  [FR] Lagging RPR (prior runs only — same-race RPR is post-race for FR)...")
    g_rpr = df.groupby("horse")["rpr_num"]
    df["lagged_rpr_last1"] = g_rpr.shift(1)
    df["lagged_rpr_last3_avg"] = g_rpr.transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )
    df["lagged_rpr_last3_max"] = g_rpr.transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).max()
    )

    print("  [FR] Lagging TS (prior runs only — same-race TS is post-race for FR)...")
    g_ts = df.groupby("horse")["ts_num"]
    df["lagged_ts_last1"] = g_ts.shift(1)
    df["lagged_ts_last3_avg"] = g_ts.transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )

    print("  [FR] Lagging finish position...")
    g_pos = df.groupby("horse")["pos_num"]
    df["prev_finish_pos"] = g_pos.shift(1)
    df["last3_finish_avg"] = g_pos.transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )

    print("  [FR] days_since_last_run, starts_last_90...")
    df["_prev_date"] = df.groupby("horse")["date_parsed"].shift(1)
    df["days_since_last_run"] = (df["date_parsed"] - df["_prev_date"]).dt.days
    df.drop(columns=["_prev_date"], inplace=True)

    def _starts_last_90(group: pd.DataFrame) -> pd.Series:
        result = []
        dates = group["date_parsed"].values
        for i, d in enumerate(dates):
            cutoff = d - pd.Timedelta(days=90)
            count = int(np.sum(dates[:i] >= cutoff))
            result.append(count)
        return pd.Series(result, index=group.index)

    df["starts_last_90"] = df.groupby("horse", group_keys=False).apply(_starts_last_90)

    print("  [FR] Course/distance prior records...")

    def _prior_records(group: pd.DataFrame, key_col: str) -> tuple[pd.Series, pd.Series]:
        key_history: dict = {}
        prior_runs, prior_wr = [], []
        for row in group.itertuples():
            key = getattr(row, key_col, None)
            if key not in key_history:
                key_history[key] = []
            hist = key_history[key]
            runs = len(hist)
            wr = sum(hist) / max(runs, 1)
            prior_runs.append(runs)
            prior_wr.append(wr if runs > 0 else np.nan)
            key_history[key].append(row.target)
        return (
            pd.Series(prior_runs, index=group.index),
            pd.Series(prior_wr, index=group.index),
        )

    c_runs_list, c_wr_list, d_runs_list, d_wr_list = [], [], [], []
    for _, group in df.groupby("horse"):
        c_r, c_w = _prior_records(group, "course")
        d_r, d_w = _prior_records(group, "dist_band")
        c_runs_list.append(c_r)
        c_wr_list.append(c_w)
        d_runs_list.append(d_r)
        d_wr_list.append(d_w)

    df["prior_course_runs"] = pd.concat(c_runs_list)
    df["prior_course_win_rate"] = pd.concat(c_wr_list)
    df["prior_distance_runs"] = pd.concat(d_runs_list)
    df["prior_distance_win_rate"] = pd.concat(d_wr_list)

    return df


def build_race_level_features(df: pd.DataFrame) -> pd.DataFrame:
    """Race-level features from lagged values only."""
    df["field_avg_prev_rpr"] = df.groupby("race_id")["lagged_rpr_last1"].transform("mean")
    df["field_std_prev_rpr"] = df.groupby("race_id")["lagged_rpr_last1"].transform("std")

    df["rpr_rank_lagged"] = (
        df.groupby("race_id")["lagged_rpr_last1"]
        .rank(ascending=False, method="min", na_option="bottom")
    )

    # Field quality proxy: avg of prior RPR across all runners in race
    # (pre-race: uses each runner's RPR from their last prior run)
    df["race_competitiveness_pre"] = df["field_avg_prev_rpr"] / 10.0

    return df


def main() -> None:
    print("[FR PreRace] Loading parquet...")
    raw = pd.read_parquet(PQ_PATH)
    print(f"[FR PreRace] Full parquet: {len(raw):,} rows")

    df = raw[raw["course"].isin(FR_COURSES)].copy()
    df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
    df["dist_band"] = df["dist_f"].apply(_dist_band)

    # Going bucket (pre-race — going is assessed before racing)
    df["going_bucket"] = df["going_code"].apply(_going_bucket)
    df["going_is_fast"] = (df["going_bucket"] == "fast").astype(float)
    df["going_is_good"] = (df["going_bucket"] == "good").astype(float)
    df["going_is_soft"] = (df["going_bucket"] == "soft").astype(float)

    # Race type codes (pre-race — type of race is declared before running)
    df["is_hurdle"] = (df["type"] == "Hurdle").astype(float)
    df["is_chase"] = (df["type"] == "Chase").astype(float)
    df["is_flat_code"] = (df["type"].isin(["Flat", "NH Flat"])).astype(float)

    # Future enrichment placeholders — data sources not yet available in parquet
    df["penetrometer_available"] = 0  # PMU numeric going — future enrichment
    df["quintet_plus_available"] = 0  # Quinté+ race flag — future enrichment
    df["class_proxy_available"] = 0   # France Galop Valeur rating — future enrichment

    print(f"[FR PreRace] FR rows: {len(df):,}")

    print("[FR PreRace] Building horse-level lagged features...")
    df = build_horse_level_lagged(df)

    print("[FR PreRace] Building race-level features...")
    df = build_race_level_features(df)

    LAGGED_COLS = [
        "lagged_rpr_last1", "lagged_rpr_last3_avg", "lagged_rpr_last3_max",
        "lagged_ts_last1", "lagged_ts_last3_avg",
        "prev_finish_pos", "last3_finish_avg",
        "days_since_last_run", "starts_last_90",
        "prior_course_runs", "prior_course_win_rate",
        "prior_distance_runs", "prior_distance_win_rate",
        "going_is_fast", "going_is_good", "going_is_soft",
        "is_hurdle", "is_chase", "is_flat_code",
        "penetrometer_available", "quintet_plus_available", "class_proxy_available",
        "field_avg_prev_rpr", "field_std_prev_rpr",
        "rpr_rank_lagged",
        "race_competitiveness_pre",
    ]

    static_cols = [c for c in STATIC_PASS_THROUGH if c in df.columns]
    available_lagged = [c for c in LAGGED_COLS if c in df.columns]
    output_cols = static_cols + available_lagged

    out_df = df[output_cols].copy()

    out_dir = ROOT / "data" / "features"
    out_dir.mkdir(exist_ok=True)
    pq_out = out_dir / "fr_prerace_features_v1.parquet"
    out_df.to_parquet(pq_out, index=False)
    print(f"[FR PreRace] Written: {pq_out} ({len(out_df):,} rows)")

    coverage = {}
    for col in available_lagged:
        cov = out_df[col].notna().mean()
        coverage[col] = round(float(cov), 4)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(PQ_PATH),
        "fr_courses": FR_COURSES,
        "total_rows": int(len(out_df)),
        "total_cols": int(len(output_cols)),
        "lagged_feature_coverage": coverage,
        "banned_features": BANNED_FEATURES,
        "future_enrichment_gaps": {
            "penetrometer": "PMU API (online.turfinfo.api.pmu.fr) — numeric going score. Not in parquet.",
            "quintet_plus": "PMU API — Quinté+ race flag. Not in parquet.",
            "class_proxy": "France Galop Valeur rating — 0% coverage in current parquet.",
        },
        "provenance_guarantee": (
            "All RPR/TS features use prior-run data only. Same-race RPR/TS are POST_RACE_LEAKAGE_CONFIRMED "
            "for FR (winner_max_rate 70-77%). Going, distance, race type are pre-race race attributes. "
            "Class_num is 0% in FR — future enrichment required from France Galop or PMU."
        ),
    }

    report_dir = ROOT / "data" / "reports"
    report_dir.mkdir(exist_ok=True)
    json_path = report_dir / "fr_prerace_features_v1.json"
    json_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"[FR PreRace] Report: {json_path}")

    md = _write_md(report, coverage)
    md_path = report_dir / "fr_prerace_features_v1.md"
    md_path.write_text(md)
    print(f"[FR PreRace] Report: {md_path}")

    print("\n[FR PreRace] Coverage summary:")
    for col, cov in coverage.items():
        flag = "LOW" if cov < 0.40 else ("PLACEHOLDER" if cov == 0.0 else "")
        print(f"  {col:<40s} {cov:.2%}  {flag}")


def _write_md(report: dict, coverage: dict) -> str:
    cov_rows = "\n".join(f"| {c} | {v:.2%} |" for c, v in coverage.items())
    banned_str = "\n".join(f"- {b}" for b in report["banned_features"])
    gaps = "\n".join(f"- **{k}**: {v}" for k, v in report["future_enrichment_gaps"].items())
    return f"""# FR Pre-Race Features V1

**Generated:** {report['generated_at']}
**Rows:** {report['total_rows']:,}
**Columns:** {report['total_cols']}

---

## Provenance Guarantee

{report['provenance_guarantee']}

---

## Feature Coverage

| Feature | Coverage |
|---|---|
{cov_rows}

---

## Banned Features (Post-Race Leakage Confirmed)

{banned_str}

---

## Future Enrichment Gaps (Placeholders)

{gaps}

---

```
FR_PRERACE_FEATURES_V1_STATUS: BUILT
SAME_RACE_RPR_TS: BANNED (POST_RACE_LEAKAGE_CONFIRMED)
OR: EXCLUDED (0% coverage in FR)
PENETROMETER: PLACEHOLDER (future PMU enrichment)
QUINTET_PLUS: PLACEHOLDER (future PMU enrichment)
OUTPUT: data/features/fr_prerace_features_v1.parquet
```
"""


if __name__ == "__main__":
    main()
