#!/usr/bin/env python3
"""
International Market Signal Feature Builder V1

Merges SP-based market features from the source parquet into the HK/FR
pre-race V1 feature sets, producing V2 parquets for the arena V2 gate test.

Starting Price is set before the race begins — it is pre-race information.
It aggregates bookmaker/tote consensus including trainer health, paddock
intel, and morning money flows that form-history alone cannot replicate.

Features added (all pre-race / race-start):
  sp_dec             Starting price (decimal)
  log_sp             log(sp_dec)
  implied_prob       1 / sp_dec  (market-implied win probability)
  sp_rank            Rank within race by SP ascending (1 = favourite)
  is_fav             Binary: this horse has the lowest SP in the race
  market_prob_ratio  implied_prob / mean(implied_prob in race)  >1 = underpriced
  form_mkt_diverge   rpr_rank_lagged − sp_rank  (positive = form > market rating)

Outputs:
  data/features/hk_prerace_features_v2.parquet
  data/features/fr_prerace_features_v2.parquet

Usage:
    PYTHONPATH=. python scripts/build_intl_market_signal_features.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SOURCE_PQ = ROOT / "data" / "raceform_v17_features.parquet"
HK_V1 = ROOT / "data" / "features" / "hk_prerace_features_v1.parquet"
FR_V1 = ROOT / "data" / "features" / "fr_prerace_features_v1.parquet"
HK_V2 = ROOT / "data" / "features" / "hk_prerace_features_v2.parquet"
FR_V2 = ROOT / "data" / "features" / "fr_prerace_features_v2.parquet"

HK_COURSES = ["Sha Tin (HK)", "Happy Valley (HK)"]
FR_COURSES = ["Chantilly (FR)", "Deauville (FR)", "Longchamp (FR)", "Saint-Cloud (FR)", "Auteuil (FR)"]

MARKET_COLS_SOURCE = ["race_id", "horse", "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav"]


def _coverage(series: pd.Series, label: str) -> None:
    pct = series.notna().mean() * 100
    print(f"    {label:<28s}: {pct:.1f}% coverage")


def build_market_layer(source_sub: pd.DataFrame, v1: pd.DataFrame, label: str) -> pd.DataFrame:
    mkt = source_sub[MARKET_COLS_SOURCE].copy()

    # Compute market_prob_ratio within each race
    race_avg = source_sub.groupby("race_id")["implied_prob"].transform("mean")
    mkt = mkt.copy()
    mkt["market_prob_ratio"] = (source_sub["implied_prob"] / race_avg.replace(0, np.nan)).values

    merged = v1.merge(mkt, on=["race_id", "horse"], how="left")

    # form_mkt_diverge: positive = form rates horse higher than market does
    # rpr_rank_lagged: lower number = better form rank (1 = top form)
    # sp_rank: lower number = better market position (1 = favourite)
    # diverge > 0: horse is market-overrated relative to form (form ranks lower)
    # diverge < 0: horse is market-underrated relative to form (form ranks higher, market misses)
    if "rpr_rank_lagged" in merged.columns and "sp_rank" in merged.columns:
        merged["form_mkt_diverge"] = merged["rpr_rank_lagged"] - merged["sp_rank"]
    else:
        merged["form_mkt_diverge"] = np.nan

    print(f"\n  [{label}] Market feature coverage:")
    for col in ["sp_dec", "implied_prob", "sp_rank", "is_fav", "market_prob_ratio", "form_mkt_diverge"]:
        _coverage(merged[col], col)

    return merged


def main() -> None:
    print("[MktSignal] Loading source parquet...")
    source = pd.read_parquet(SOURCE_PQ, columns=[
        "race_id", "horse", "course",
        "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav",
    ])
    print(f"[MktSignal] Source: {len(source):,} rows")

    hk_src = source[source["course"].isin(HK_COURSES)].copy()
    fr_src = source[source["course"].isin(FR_COURSES)].copy()
    print(f"[MktSignal] HK: {len(hk_src):,} rows  |  FR: {len(fr_src):,} rows")

    hk_v1 = pd.read_parquet(HK_V1)
    fr_v1 = pd.read_parquet(FR_V1)
    print(f"[MktSignal] V1 loaded: HK={len(hk_v1):,}  FR={len(fr_v1):,}")

    hk_v2 = build_market_layer(hk_src, hk_v1, "HK")
    fr_v2 = build_market_layer(fr_src, fr_v1, "FR")

    hk_v2.to_parquet(HK_V2, index=False)
    print(f"\n[MktSignal] Written: {HK_V2}  ({len(hk_v2):,} rows, {len(hk_v2.columns)} cols)")

    fr_v2.to_parquet(FR_V2, index=False)
    print(f"[MktSignal] Written: {FR_V2}  ({len(fr_v2):,} rows, {len(fr_v2.columns)} cols)")

    print("\n[MktSignal] V2 parquets complete. Run arena V2 to test gate.")


if __name__ == "__main__":
    main()
