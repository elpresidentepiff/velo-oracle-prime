#!/usr/bin/env python3
"""
TIE v3 Gate Backtest
====================
Evaluates the rule-based TIE v3 gate against PLACE outcomes, NOT top-1.

Measures:
  Gate precision     — when gate fires, what % of horses placed (pos <= 3)?
  Base rate          — what % of all horses placed (for comparison)?
  Precision ratio    — gate precision / base rate (want >= 1.3x)
  EW precision       — when EW flag fires on longshots (SP > 8), what % placed?
  Tier upgrade lift  — win/place rate on gate-upgraded runners vs non-upgraded

The backtest uses the same raceform parquet as SQPE training.
No lookahead: gate only sees features available before the race.

Usage:
    python scripts/backtest_tie_v3_gate.py
    python scripts/backtest_tie_v3_gate.py --sample 200000
    python scripts/backtest_tie_v3_gate.py --year 2024   # test-year only
"""

import argparse
from pathlib import Path
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from src.intelligence.tie_v3_gate import TIEv3Gate, MIN_SIGNALS_FOR_UPGRADE, MIN_SIGNALS_FOR_EW_FLAG


# ─── Build feature dicts from parquet row ─────────────────────────────────────
def row_to_features(row: pd.Series) -> dict:
    """Map parquet columns to TIEv3Gate feature dict."""
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


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", default="data/raceform_v17_features.parquet")
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--year", type=int, default=None,
                        help="Only evaluate rows from this year (e.g. 2024)")
    args = parser.parse_args()

    path = Path(args.parquet)
    if not path.exists():
        print(f"ERROR: {path} not found")
        return

    print(f"\nLoading {path} ...")
    df = pd.read_parquet(path)
    print(f"  {len(df):,} rows")

    # Need days_since_run and class_delta — compute if missing
    if "days_since_run" not in df.columns or "class_delta" not in df.columns:
        print("Computing days_since_run / class_delta ...")
        if not pd.api.types.is_datetime64_any_dtype(df["date_parsed"]):
            df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
        df = df.sort_values(["horse", "date_parsed"]).reset_index(drop=True)
        prev_date  = df.groupby("horse")["date_parsed"].shift(1)
        prev_class = df.groupby("horse")["class_num"].shift(1)
        df["days_since_run"] = (df["date_parsed"] - prev_date).dt.days.clip(1, 365).fillna(14.0)
        df["class_delta"]    = (df["class_num"] - prev_class).clip(-6, 6).fillna(0.0)

    # Filter to numeric positions only
    numeric_pos = pd.to_numeric(df["pos"].astype(str).str.strip(), errors="coerce")
    df = df[numeric_pos.notna()].copy()
    df["pos_num"] = numeric_pos[df.index]
    print(f"  {len(df):,} rows after non-runner filter")

    # Year filter
    if args.year:
        if not pd.api.types.is_datetime64_any_dtype(df["date_parsed"]):
            df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
        df = df[df["date_parsed"].dt.year == args.year].copy()
        print(f"  {len(df):,} rows for year {args.year}")

    if args.sample:
        df = df.sample(n=min(args.sample, len(df)), random_state=42).copy()
        print(f"  Sampled to {len(df):,} rows")

    # ── Run gate on every row ──────────────────────────────────────────────────
    print(f"\nEvaluating TIE v3 gate on {len(df):,} runners ...")
    gate = TIEv3Gate()
    results = []
    for _, row in df.iterrows():
        feats = row_to_features(row)
        res = gate.evaluate(feats)
        results.append({
            "fires":        res.fires,
            "signal_count": res.signal_count,
            "ew_flag":      res.ew_flag,
            "signals":      "|".join(res.signals_found),
            "placed":       is_placed(row["pos"]),
            "won":          is_winner(row["pos"]),
            "sp_dec":       row.get("sp_dec", np.nan),
        })

    rdf = pd.DataFrame(results)

    # ── Metrics ───────────────────────────────────────────────────────────────
    n_total       = len(rdf)
    n_fired       = rdf["fires"].sum()
    n_ew_fired    = rdf["ew_flag"].sum()
    base_place    = rdf["placed"].mean()
    base_win      = rdf["won"].mean()

    gate_place    = rdf[rdf["fires"]]["placed"].mean() if n_fired > 0 else float("nan")
    gate_win      = rdf[rdf["fires"]]["won"].mean()    if n_fired > 0 else float("nan")
    ew_place      = rdf[rdf["ew_flag"]]["placed"].mean() if n_ew_fired > 0 else float("nan")
    ew_win        = rdf[rdf["ew_flag"]]["won"].mean()    if n_ew_fired > 0 else float("nan")

    precision_ratio = gate_place / base_place if base_place > 0 else float("nan")
    ew_precision_ratio = ew_place / base_place if base_place > 0 else float("nan")

    fire_rate = n_fired / n_total

    print(f"\n{'='*60}")
    print(f"  TIE v3 Gate Backtest")
    print(f"  Upgrade threshold : >= {MIN_SIGNALS_FOR_UPGRADE} signals")
    print(f"  EW threshold      : >= {MIN_SIGNALS_FOR_EW_FLAG} signals + SP > 8")
    print(f"{'='*60}")
    print(f"  Runners total     : {n_total:,}")
    print(f"  Gate fires        : {n_fired:,}  ({fire_rate*100:.1f}% of runners)")
    print(f"  EW flags          : {n_ew_fired:,}")
    print(f"")
    print(f"  {'Metric':<28} {'Base':>8} {'Gate':>8} {'Ratio':>8}")
    print(f"  {'-'*54}")
    print(f"  {'Place rate (pos<=3)':<28} {base_place*100:>7.1f}% {gate_place*100:>7.1f}% {precision_ratio:>8.2f}x")
    print(f"  {'Win rate':<28} {base_win*100:>7.1f}% {gate_win*100:>7.1f}% {gate_win/base_win:>8.2f}x")
    print(f"  {'EW place rate (SP>8)':<28} {base_place*100:>7.1f}% {ew_place*100:>7.1f}% {ew_precision_ratio:>8.2f}x")
    print(f"{'='*60}")

    if precision_ratio >= 1.3:
        print(f"\n  VERDICT: LIFT — precision ratio {precision_ratio:.2f}x >= 1.3x target")
    elif precision_ratio >= 1.1:
        print(f"\n  VERDICT: MARGINAL — precision ratio {precision_ratio:.2f}x (tune thresholds)")
    else:
        print(f"\n  VERDICT: NO LIFT — precision ratio {precision_ratio:.2f}x (revise signals)")

    # ── Signal breakdown ──────────────────────────────────────────────────────
    print(f"\n  Signal frequency (% of all runners):")
    all_signals = []
    for sigs in rdf["signals"]:
        all_signals.extend(sigs.split("|") if sigs else [])
    from collections import Counter
    sig_counts = Counter(all_signals)
    for sig, cnt in sorted(sig_counts.items(), key=lambda x: -x[1]):
        pct = cnt / n_total * 100
        # place rate when this specific signal fires
        rows_with_sig = rdf[rdf["signals"].str.contains(sig, na=False)]
        sig_place = rows_with_sig["placed"].mean() * 100 if len(rows_with_sig) > 0 else 0
        print(f"    {sig:<32} {cnt:>7,}  ({pct:>4.1f}%)  place%={sig_place:.1f}%")

    # ── Count distribution ─────────────────────────────────────────────────────
    print(f"\n  Signal count distribution:")
    for n in range(0, 7):
        cnt = (rdf["signal_count"] == n).sum()
        pct = cnt / n_total * 100
        place = rdf[rdf["signal_count"] == n]["placed"].mean() * 100 if cnt > 0 else 0
        marker = " <-- gate fires" if n >= MIN_SIGNALS_FOR_UPGRADE else ""
        print(f"    {n} signals: {cnt:>7,}  ({pct:>4.1f}%)  place%={place:.1f}%{marker}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
