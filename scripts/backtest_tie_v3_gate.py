#!/usr/bin/env python3
"""
TIE v3 Gate Backtest
====================
Measures upgrade and EW cohorts SEPARATELY.

The previous version called gate.evaluate() without current_tier, so the
upgrade path (current_tier in C/D) never fired and only EW fires were counted.
This version bypasses evaluate() and tests each cohort independently.

Cohort definitions:
  Upgrade cohort  — signal_count >= MIN_SIGNALS_FOR_UPGRADE (any runner)
                    Baseline: all runners with signal_count < MIN_SIGNALS_FOR_UPGRADE
  EW cohort       — signal_count >= MIN_SIGNALS_FOR_EW_FLAG AND sp_dec > 8
                    Baseline: all longshots (sp_dec > 8) regardless of signal count

Usage:
    python scripts/backtest_tie_v3_gate.py
    python scripts/backtest_tie_v3_gate.py --year 2024
    python scripts/backtest_tie_v3_gate.py --year 2025
    python scripts/backtest_tie_v3_gate.py --sample 200000
"""

import argparse
from collections import Counter
from pathlib import Path
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from src.intelligence.tie_v3_gate import (
    TIEv3Gate,
    MIN_SIGNALS_FOR_UPGRADE,
    MIN_SIGNALS_FOR_EW_FLAG,
    LONGSHOT_SP_THRESHOLD,
)


def row_to_features(row: pd.Series) -> dict:
    return {
        "days_since_run":       row.get("days_since_run"),
        "class_delta":          row.get("class_delta"),
        "runs_since_win":       row.get("runs_since_win"),
        "runs_since_place":     row.get("runs_since_place"),
        "trainer_timing_score": row.get("trainer_timing_score"),
        "sp_dec":               row.get("sp_dec"),
        "sp_rank":              row.get("sp_rank"),
        "is_fav":               bool(row.get("is_fav", 0)),
    }


def is_placed(pos_val) -> bool:
    try:
        return int(float(str(pos_val).strip())) <= 3
    except Exception:
        return False


def is_winner(pos_val) -> bool:
    try:
        return int(float(str(pos_val).strip())) == 1
    except Exception:
        return False


def pct(val: float) -> str:
    return f"{val * 100:.1f}%"


def ratio(a: float, b: float) -> str:
    if b > 0:
        return f"{a / b:.2f}x"
    return "n/a"


def cohort_stats(df_cohort: pd.DataFrame, df_base: pd.DataFrame, label: str) -> None:
    n_cohort = len(df_cohort)
    n_base = len(df_base)
    if n_cohort == 0:
        print(f"  {label}: 0 runners (no fires)")
        return

    c_win   = df_cohort["won"].mean()
    c_place = df_cohort["placed"].mean()
    b_win   = df_base["won"].mean() if n_base > 0 else 0.0
    b_place = df_base["placed"].mean() if n_base > 0 else 0.0
    fire_rate = n_cohort / (n_cohort + n_base)

    print(f"  {'Metric':<30} {'Baseline':>10} {'Cohort':>10} {'Uplift':>10}")
    print(f"  {'-'*62}")
    print(f"  {'Runners':<30} {n_base:>10,} {n_cohort:>10,}")
    print(f"  {'Fire rate (cohort/total)':<30} {'':>10} {pct(fire_rate):>10}")
    print(f"  {'Place rate (pos<=3)':<30} {pct(b_place):>10} {pct(c_place):>10} {ratio(c_place, b_place):>10}")
    print(f"  {'Win rate':<30} {pct(b_win):>10} {pct(c_win):>10} {ratio(c_win, b_win):>10}")

    place_ratio = c_place / b_place if b_place > 0 else float("nan")
    if place_ratio >= 1.3:
        verdict = f"LIFT ({place_ratio:.2f}x >= 1.3x target)"
    elif place_ratio >= 1.1:
        verdict = f"MARGINAL ({place_ratio:.2f}x — tune thresholds)"
    else:
        verdict = f"NO LIFT ({place_ratio:.2f}x)"
    print(f"\n  VERDICT: {verdict}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", default="data/raceform_v17_features.parquet")
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--year", type=int, default=None,
                        help="Filter to a single year (e.g. 2024)")
    args = parser.parse_args()

    path = Path(args.parquet)
    if not path.exists():
        print(f"ERROR: {path} not found")
        return

    print(f"\nLoading {path} ...")
    df = pd.read_parquet(path)
    print(f"  {len(df):,} rows")

    # Compute days_since_run / class_delta if missing
    if "days_since_run" not in df.columns or "class_delta" not in df.columns:
        print("Computing days_since_run / class_delta ...")
        if not pd.api.types.is_datetime64_any_dtype(df["date_parsed"]):
            df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
        df = df.sort_values(["horse", "date_parsed"]).reset_index(drop=True)
        prev_date  = df.groupby("horse")["date_parsed"].shift(1)
        prev_class = df.groupby("horse")["class_num"].shift(1)
        df["days_since_run"] = (df["date_parsed"] - prev_date).dt.days.clip(1, 365).fillna(14.0)
        df["class_delta"]    = (df["class_num"] - prev_class).clip(-6, 6).fillna(0.0)

    # Keep only rows with numeric finishing positions
    numeric_pos = pd.to_numeric(df["pos"].astype(str).str.strip(), errors="coerce")
    df = df[numeric_pos.notna()].copy()
    df["pos_num"] = numeric_pos[df.index]
    print(f"  {len(df):,} rows after non-runner filter")

    if args.year:
        if not pd.api.types.is_datetime64_any_dtype(df["date_parsed"]):
            df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
        df = df[df["date_parsed"].dt.year == args.year].copy()
        print(f"  {len(df):,} rows for year {args.year}")

    if args.sample:
        df = df.sample(n=min(args.sample, len(df)), random_state=42).copy()
        print(f"  Sampled to {len(df):,} rows")

    # ── Score every runner (signal count only, no current_tier dependency) ──
    print(f"\nScoring {len(df):,} runners ...")
    gate = TIEv3Gate()
    records = []
    for _, row in df.iterrows():
        feats = row_to_features(row)
        # Evaluate without current_tier so we get the raw signal count
        # Tier upgrade eligibility is handled by cohort split below
        res = gate.evaluate(feats, current_tier=None)
        sp  = feats.get("sp_dec") or 0.0
        records.append({
            "signal_count": res.signal_count,
            "signals":      "|".join(res.signals_found),
            "sp_dec":       sp,
            "is_fav":       feats.get("is_fav", False),
            "placed":       is_placed(row["pos"]),
            "won":          is_winner(row["pos"]),
        })

    rdf = pd.DataFrame(records)
    n_total = len(rdf)

    # ─────────────────────────────────────────────────────────────────────────
    # COHORT 1 — Upgrade cohort
    #   All runners with signal_count >= MIN_SIGNALS_FOR_UPGRADE
    #   Baseline: runners with signal_count < MIN_SIGNALS_FOR_UPGRADE
    # ─────────────────────────────────────────────────────────────────────────
    upgrade_mask    = rdf["signal_count"] >= MIN_SIGNALS_FOR_UPGRADE
    upgrade_cohort  = rdf[upgrade_mask]
    upgrade_baseline = rdf[~upgrade_mask]

    # ─────────────────────────────────────────────────────────────────────────
    # COHORT 2 — EW cohort
    #   Longshots (sp_dec > LONGSHOT_SP_THRESHOLD) with signal_count >= MIN_SIGNALS_FOR_EW_FLAG
    #   Baseline: all longshots regardless of signal count
    # ─────────────────────────────────────────────────────────────────────────
    longshot_mask   = rdf["sp_dec"] > LONGSHOT_SP_THRESHOLD
    ew_mask         = longshot_mask & (rdf["signal_count"] >= MIN_SIGNALS_FOR_EW_FLAG) & ~rdf["is_fav"]
    ew_cohort       = rdf[ew_mask]
    ew_baseline     = rdf[longshot_mask]

    year_label = f" ({args.year})" if args.year else ""

    print(f"\n{'='*62}")
    print(f"  TIE v3 Gate Backtest{year_label}")
    print(f"  Upgrade threshold : >= {MIN_SIGNALS_FOR_UPGRADE} signals (any runner)")
    print(f"  EW threshold      : >= {MIN_SIGNALS_FOR_EW_FLAG} signals + SP > {LONGSHOT_SP_THRESHOLD:.0f}")
    print(f"  Total runners     : {n_total:,}")
    print(f"{'='*62}")

    print(f"\n--- COHORT 1: Upgrade (signal_count >= {MIN_SIGNALS_FOR_UPGRADE}) ---")
    cohort_stats(upgrade_cohort, upgrade_baseline, "Upgrade")

    print(f"\n--- COHORT 2: EW Flag (signal_count >= {MIN_SIGNALS_FOR_EW_FLAG}, SP > {LONGSHOT_SP_THRESHOLD:.0f}) ---")
    cohort_stats(ew_cohort, ew_baseline, "EW")

    # -- Signal count distribution ------------------------------------------
    print(f"\n--- Signal count distribution ---")
    print(f"  {'Signals':<10} {'Count':>9} {'%Total':>8} {'Place%':>8}  Notes")
    print(f"  {'-'*55}")
    for n in range(0, 8):
        mask = rdf["signal_count"] == n
        cnt  = mask.sum()
        if cnt == 0:
            continue
        pct_total = cnt / n_total * 100
        place_r   = rdf[mask]["placed"].mean() * 100
        notes = []
        if n >= MIN_SIGNALS_FOR_UPGRADE:
            notes.append("UPGRADE fires")
        if n >= MIN_SIGNALS_FOR_EW_FLAG:
            notes.append("EW eligible")
        print(f"  {n:<10} {cnt:>9,} {pct_total:>7.1f}% {place_r:>7.1f}%  {', '.join(notes)}")

    # -- Signal frequency ---------------------------------------------------
    print(f"\n--- Signal frequency (% of all runners, place% when present) ---")
    all_signals: list[str] = []
    for sigs in rdf["signals"]:
        all_signals.extend(s for s in sigs.split("|") if s)
    sig_counts = Counter(all_signals)
    print(f"  {'Signal':<34} {'Count':>8} {'%All':>7} {'Place%':>8}")
    print(f"  {'-'*60}")
    for sig, cnt in sorted(sig_counts.items(), key=lambda x: -x[1]):
        pct_all  = cnt / n_total * 100
        rows_sig = rdf[rdf["signals"].str.contains(sig, na=False)]
        sig_pl   = rows_sig["placed"].mean() * 100 if len(rows_sig) > 0 else 0.0
        print(f"  {sig:<34} {cnt:>8,} {pct_all:>6.1f}% {sig_pl:>7.1f}%")

    print(f"\n{'='*62}\n")


if __name__ == "__main__":
    main()
