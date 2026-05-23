#!/usr/bin/env python3
"""
Build HK Pre-Race Feature Pack V1

All features are strictly pre-race: only information that existed BEFORE
the race started is included. Same-race RPR/OR/TS are banned.

Features computed:
  Horse-level lagged (prior runs only):
    prev_rpr_num, last3_rpr_avg
    prev_or_num, last3_or_avg
    prev_finish_pos, last3_finish_avg
    days_since_last_run, starts_last_90_days
    course_prior_runs, course_prior_wr
    distance_prior_runs, distance_prior_wr
    prev_class_num, class_move_direction, class_drop_flag, class_rise_flag
    prior_class_win_rate, prior_class_place_rate

  Draw features (population-level, lagged by date):
    draw_bucket_num, draw_inside_flag, draw_outside_flag
    course_distance_draw_win_rate_lagged
    course_distance_draw_place_rate_lagged

  Race-level (from lagged runner values — no current-race data):
    field_avg_prev_rpr, field_std_prev_rpr
    field_avg_prev_or
    rpr_rank_lagged, or_rank_lagged
    rating_consensus_lagged
    race_competitiveness_pre

  Static race attributes (pre-race by definition):
    draw_num, draw_pct, class_num (race class set before running),
    field_size, dist_f, dist_band, going_code, wgt_lbs, age_num, is_aw

Permanent bans:
  rpr_num (same-race), or_num (same-race), ts_num (same-race)
  rpr_vs_field, or_vs_field (same-race relative)
  sp_dec, implied_prob, log_sp, sp_rank
  pos (same-race result), target used only as label
  is_fav, odds_*, decoy_*, setup_*, cash_run_flag

Courses: Sha Tin (HK), Happy Valley (HK)

Output:
  data/features/hk_prerace_features_v1.parquet
  data/reports/hk_prerace_features_v1.json
  data/reports/hk_prerace_features_v1.md

Usage:
    PYTHONPATH=. python scripts/build_hk_prerace_features.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PQ_PATH = ROOT / "data" / "raceform_v17_features.parquet"

HK_COURSES = ["Sha Tin (HK)", "Happy Valley (HK)"]

DIST_BAND_BREAKPOINTS = [0, 6, 8, 10, 12, 14, 100]
DIST_BAND_LABELS = ["5f-6f", "7f-8f", "9f-10f", "11f-12f", "13f-14f", "15f+"]

STATIC_PASS_THROUGH = [
    "race_id", "horse", "course", "date", "date_parsed", "target",
    "draw_num", "draw_pct", "class_num", "field_size", "dist_f",
    "going_code", "wgt_lbs", "age_num", "is_aw", "type",
]

BANNED_FEATURES = [
    "rpr_num", "or_num", "ts_num",
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


def _draw_bucket(draw_pct: float) -> int:
    if pd.isna(draw_pct):
        return 1  # mid as default
    if draw_pct <= 0.33:
        return 0  # inside
    if draw_pct >= 0.67:
        return 2  # outside
    return 1  # mid


def build_horse_level_lagged(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["pos_num"] = pd.to_numeric(df["pos"], errors="coerce")
    df["place_flag"] = ((df["pos_num"] <= 3) & df["pos_num"].notna()).astype(float)

    df = df.sort_values(["horse", "date_parsed"]).reset_index(drop=True)

    print("  [HK] Lagging RPR/OR...")
    for col, out_prefix in [("rpr_num", "rpr"), ("or_num", "or")]:
        g = df.groupby("horse")[col]
        df[f"prev_{out_prefix}_num"] = g.shift(1)
        df[f"last3_{out_prefix}_avg"] = g.transform(
            lambda x: x.shift(1).rolling(3, min_periods=1).mean()
        )

    print("  [HK] Lagging finish position...")
    g_pos = df.groupby("horse")["pos_num"]
    df["prev_finish_pos"] = g_pos.shift(1)
    df["last3_finish_avg"] = g_pos.transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )

    print("  [HK] days_since_last_run, starts_last_90...")
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

    print("  [HK] Course/distance prior records...")

    def _prior_records(group: pd.DataFrame, key_col: str, outcome_col: str = "target") -> tuple[pd.Series, pd.Series]:
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
            key_history[key].append(getattr(row, outcome_col))
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

    df["course_prior_runs"] = pd.concat(c_runs_list)
    df["course_prior_wr"] = pd.concat(c_wr_list)
    df["distance_prior_runs"] = pd.concat(d_runs_list)
    df["distance_prior_wr"] = pd.concat(d_wr_list)

    print("  [HK] Class trajectory features...")
    df["prev_class_num"] = df.groupby("horse")["class_num"].shift(1)
    df["class_move_direction"] = df["class_num"] - df["prev_class_num"]
    # In HK: class 1=elite, class 5=weakest. Higher class_num = easier class.
    # class_drop_flag: moved to HIGHER number = easier class
    df["class_drop_flag"] = (df["class_move_direction"] > 0).astype(float)
    # class_rise_flag: moved to LOWER number = harder class
    df["class_rise_flag"] = (df["class_move_direction"] < 0).astype(float)
    # When prev_class_num is NaN, flags are NaN (horse's first run)
    df.loc[df["prev_class_num"].isna(), ["class_drop_flag", "class_rise_flag"]] = np.nan

    print("  [HK] Prior class win/place rates...")
    cwr_list, cpr_list = [], []
    for _, group in df.groupby("horse"):
        class_wins: dict = {}
        class_places: dict = {}
        cwr, cpr = [], []
        for row in group.itertuples():
            cls = row.class_num
            if pd.isna(cls):
                cwr.append(np.nan)
                cpr.append(np.nan)
            else:
                hist_w = class_wins.get(cls, [])
                hist_p = class_places.get(cls, [])
                n = len(hist_w)
                cwr.append(sum(hist_w) / n if n > 0 else np.nan)
                cpr.append(sum(hist_p) / n if n > 0 else np.nan)
            # Update history with this race's result
            if not pd.isna(cls):
                class_wins.setdefault(cls, []).append(row.target)
                place = 1 if (not pd.isna(row.pos_num) and row.pos_num <= 3) else 0
                class_places.setdefault(cls, []).append(place)
        cwr_list.append(pd.Series(cwr, index=group.index))
        cpr_list.append(pd.Series(cpr, index=group.index))

    df["prior_class_win_rate"] = pd.concat(cwr_list)
    df["prior_class_place_rate"] = pd.concat(cpr_list)

    return df


def build_draw_stats_lagged(df: pd.DataFrame) -> pd.DataFrame:
    """
    Population-level lagged draw win/place rates per (course, dist_band, draw_bucket).
    For each race date D, only results from dates < D are used.
    """
    df["place_flag"] = ((df["pos_num"] <= 3) & df["pos_num"].notna()).astype(float)

    daily = (
        df.groupby(["date_parsed", "course", "dist_band", "draw_bucket"])
        .agg(
            n_wins=("target", "sum"),
            n_places=("place_flag", "sum"),
            n_total=("target", "count"),
        )
        .reset_index()
    )
    daily = daily.sort_values(["course", "dist_band", "draw_bucket", "date_parsed"])

    grp_cols = ["course", "dist_band", "draw_bucket"]
    for col in ["n_wins", "n_places", "n_total"]:
        daily[f"cum_{col}"] = daily.groupby(grp_cols)[col].cumsum()
        # lag: subtract current date's contribution = prior dates only
        daily[f"cumlag_{col}"] = daily[f"cum_{col}"] - daily[col]

    MIN_SAMPLE = 10
    daily["draw_win_rate_lagged"] = np.where(
        daily["cumlag_n_total"] >= MIN_SAMPLE,
        daily["cumlag_n_wins"] / daily["cumlag_n_total"].clip(lower=1),
        np.nan,
    )
    daily["draw_place_rate_lagged"] = np.where(
        daily["cumlag_n_total"] >= MIN_SAMPLE,
        daily["cumlag_n_places"] / daily["cumlag_n_total"].clip(lower=1),
        np.nan,
    )

    result = df.merge(
        daily[["date_parsed", "course", "dist_band", "draw_bucket",
               "draw_win_rate_lagged", "draw_place_rate_lagged"]],
        on=["date_parsed", "course", "dist_band", "draw_bucket"],
        how="left",
    )
    return result


def build_race_level_features(df: pd.DataFrame) -> pd.DataFrame:
    """Race-level aggregate features from lagged runner values. No current-race data used."""
    df["field_avg_prev_rpr"] = df.groupby("race_id")["prev_rpr_num"].transform("mean")
    df["field_std_prev_rpr"] = df.groupby("race_id")["prev_rpr_num"].transform("std")
    df["field_avg_prev_or"] = df.groupby("race_id")["prev_or_num"].transform("mean")

    # Rank of lagged RPR/OR within the field (1 = highest = best)
    df["rpr_rank_lagged"] = (
        df.groupby("race_id")["prev_rpr_num"]
        .rank(ascending=False, method="min", na_option="bottom")
    )
    df["or_rank_lagged"] = (
        df.groupby("race_id")["prev_or_num"]
        .rank(ascending=False, method="min", na_option="bottom")
    )

    # When both ranking systems agree on a horse's quality, signal is stronger
    # Lower score = both systems rank the horse higher = better consensus
    df["rating_consensus_lagged"] = -(df["rpr_rank_lagged"] + df["or_rank_lagged"]) / 2

    # Pre-race field quality proxy (avg prior OR across field, scaled)
    df["race_competitiveness_pre"] = df["field_avg_prev_or"] / 10.0

    return df


def main() -> None:
    print("[HK PreRace] Loading parquet...")
    raw = pd.read_parquet(PQ_PATH)
    print(f"[HK PreRace] Full parquet: {len(raw):,} rows")

    df = raw[raw["course"].isin(HK_COURSES)].copy()
    df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
    df["dist_band"] = df["dist_f"].apply(_dist_band)

    # Draw bucket features (pre-race)
    df["draw_bucket"] = df["draw_pct"].apply(_draw_bucket)
    df["draw_inside_flag"] = (df["draw_bucket"] == 0).astype(float)
    df["draw_outside_flag"] = (df["draw_bucket"] == 2).astype(float)

    print(f"[HK PreRace] HK rows: {len(df):,}")

    print("[HK PreRace] Building horse-level lagged features...")
    df = build_horse_level_lagged(df)

    print("[HK PreRace] Building draw stats lagged...")
    df = build_draw_stats_lagged(df)

    print("[HK PreRace] Building race-level features...")
    df = build_race_level_features(df)

    LAGGED_COLS = [
        "prev_rpr_num", "last3_rpr_avg",
        "prev_or_num", "last3_or_avg",
        "prev_finish_pos", "last3_finish_avg",
        "days_since_last_run", "starts_last_90",
        "course_prior_runs", "course_prior_wr",
        "distance_prior_runs", "distance_prior_wr",
        "prev_class_num", "class_move_direction",
        "class_drop_flag", "class_rise_flag",
        "prior_class_win_rate", "prior_class_place_rate",
        "draw_inside_flag", "draw_outside_flag",
        "draw_win_rate_lagged", "draw_place_rate_lagged",
        "field_avg_prev_rpr", "field_std_prev_rpr",
        "field_avg_prev_or",
        "rpr_rank_lagged", "or_rank_lagged",
        "rating_consensus_lagged",
        "race_competitiveness_pre",
    ]

    static_cols = [c for c in STATIC_PASS_THROUGH if c in df.columns]
    available_lagged = [c for c in LAGGED_COLS if c in df.columns]
    output_cols = static_cols + available_lagged

    out_df = df[output_cols].copy()

    out_dir = ROOT / "data" / "features"
    out_dir.mkdir(exist_ok=True)
    pq_out = out_dir / "hk_prerace_features_v1.parquet"
    out_df.to_parquet(pq_out, index=False)
    print(f"[HK PreRace] Written: {pq_out} ({len(out_df):,} rows)")

    # Coverage report
    coverage = {}
    for col in available_lagged:
        cov = out_df[col].notna().mean()
        coverage[col] = round(float(cov), 4)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(PQ_PATH),
        "hk_courses": HK_COURSES,
        "total_rows": int(len(out_df)),
        "total_cols": int(len(output_cols)),
        "lagged_feature_coverage": coverage,
        "banned_features": BANNED_FEATURES,
        "provenance_guarantee": (
            "All features use prior-run data only. Same-race RPR/OR/TS are banned. "
            "Draw stats are computed from races strictly before current race date. "
            "Class trajectory uses previous run's class, not current race class as a rating."
        ),
    }

    report_dir = ROOT / "data" / "reports"
    report_dir.mkdir(exist_ok=True)
    json_path = report_dir / "hk_prerace_features_v1.json"
    json_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"[HK PreRace] Report: {json_path}")

    md = _write_md(report, coverage)
    md_path = report_dir / "hk_prerace_features_v1.md"
    md_path.write_text(md)
    print(f"[HK PreRace] Report: {md_path}")

    print("\n[HK PreRace] Coverage summary:")
    for col, cov in coverage.items():
        flag = "LOW" if cov < 0.50 else ""
        print(f"  {col:<40s} {cov:.2%}  {flag}")


def _write_md(report: dict, coverage: dict) -> str:
    cov_rows = "\n".join(f"| {c} | {v:.2%} |" for c, v in coverage.items())
    banned_str = "\n".join(f"- {b}" for b in report["banned_features"])
    return f"""# HK Pre-Race Features V1

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

## Banned Features (Same-Race / Post-Race)

{banned_str}

---

```
HK_PRERACE_FEATURES_V1_STATUS: BUILT
SAME_RACE_RPR_OR_TS: BANNED
DRAW_STATS: LAGGED_BY_DATE
CLASS_TRAJECTORY: LAGGED_BY_RUN
OUTPUT: data/features/hk_prerace_features_v1.parquet
```
"""


if __name__ == "__main__":
    main()
