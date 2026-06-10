#!/usr/bin/env python3
"""
Historical Tier-A Economics Replay — READ-ONLY, leakage-honest
===============================================================
Asset: data/raceform_v17_features.parquet (1.70M runner rows, 2015–2025).

VERDICT BUILT INTO THIS SCRIPT (do not soften it):
  EXACT_REPLAY = BLOCKED_LEAKAGE, twice over:
    1. IN-SAMPLE — models/sqpe_v17/metadata.json: source =
       data/raceform_clean.parquet, train_rows 1,447,607 (85% of this file).
       Scoring the model on its own training set proves memorisation.
    2. MARKET LEAKAGE — sqpe_v17's feature list includes sp_dec, log_sp,
       implied_prob, sp_rank, is_fav: the FINAL STARTING PRICE is a model
       input. A model that consumes SP cannot demonstrate edge against SP.
       (This also explains the suspicious AUC 0.94 and is a train/serve
       skew: live scoring fills these fields from morning forecast odds.)

  Therefore the legitimate decade replay is PROXY_REPLAY: market-structure
  baselines that bound what any selector must beat, computed per year.
  The REAL historical Tier-A validation requires the walk-forward retrain
  harness (model training — operator approval required; not this script).

Usage:
    PYTHONPATH=. python scripts/ops/replay_historical_tier_a_economics.py

Outputs:
    data/current/historical_tier_a_replay.json
    data/reports/historical_tier_a_replay.md
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "data" / "raceform_v17_features.parquet"


def econ(df: pd.DataFrame) -> dict:
    """Flat 1pt at SP economics for a selection set (one row per bet)."""
    n = len(df)
    if n == 0:
        return {"n": 0}
    wins = int((df["target"] == 1).sum())
    pl = float(np.where(df["target"] == 1, df["sp_dec"] - 1, -1.0).sum())
    sp = df["sp_dec"]
    return {
        "n": n,
        "wins": wins,
        "strike_rate": round(wins / n, 4),
        "avg_sp": round(float(sp.mean()), 2),
        "median_sp": round(float(sp.median()), 2),
        "flat_1pt_pl": round(pl, 1),
        "roi_pct": round(pl / n * 100, 2),
    }


def main() -> int:
    df = pd.read_parquet(PARQUET)
    df = df[(df["sp_dec"] > 1.0) & df["target"].notna()].copy()
    df["year"] = df["date"].astype(str).str[:4]

    profile = {
        "rows_total": int(len(df)),
        "date_range": [str(df["date"].min()), str(df["date"].max())],
        "races": int(df["race_id"].nunique()),
        "years": sorted(df["year"].unique().tolist()),
        "target_definition": "target==1 means won (per v17 training build)",
        "sp_provenance": "historical official SP (raceform archive) — settlement price, safe for ROI",
        "implied_prob_available": True,
    }

    leakage = {
        "exact_replay": "BLOCKED_LEAKAGE",
        "reasons": [
            "IN_SAMPLE: sqpe_v17 metadata source=raceform_clean.parquet, train_rows=1,447,607 (~85% of this file)",
            "MARKET_INPUT: model features include sp_dec/log_sp/implied_prob/sp_rank/is_fav — final SP is a model input; edge-vs-SP is circular",
            "TRAIN_SERVE_SKEW: live scoring fills sp fields from morning forecast odds, training used realized SP",
        ],
        "excluded_columns_post_race": ["pos", "target", "sp_dec*, log_sp*, implied_prob*, sp_rank*, is_fav* (*known only at the off)"],
        "legitimate_path": "walk-forward retrain harness with pre-race-only features (requires operator approval to train)",
    }

    # ── PROXY_REPLAY: market-structure baselines, per year ────────────────────
    # P0 all runners (the market's overround tax), P1 favourite, P2 favourite
    # with ratings edge (or & rpr above field mean) — a crude Tier-A-shaped
    # structural filter using PRE-RACE-knowable ratings + the market position.
    fav = df[df["is_fav"] == 1]
    fav_edge = fav[(fav["or_vs_field"] > 0) & (fav["rpr_vs_field"] > 0)]

    proxies = {
        "P0_all_runners": econ(df),
        "P1_favourite": econ(fav),
        "P2_favourite_with_ratings_edge": econ(fav_edge),
    }
    yearly = {}
    for y, g in df.groupby("year"):
        gf = g[g["is_fav"] == 1]
        gfe = gf[(gf["or_vs_field"] > 0) & (gf["rpr_vs_field"] > 0)]
        yearly[y] = {
            "P1_favourite": econ(gf),
            "P2_fav_ratings_edge": econ(gfe),
        }

    # Slices for P2 (the closest structural cousin of a Tier-A shape)
    def slice_econ(frame, col, bins=None, labels=None):
        out = {}
        if bins is not None:
            cats = pd.cut(frame[col], bins=bins, labels=labels)
            for lab, g in frame.groupby(cats, observed=True):
                out[str(lab)] = econ(g)
        else:
            for lab, g in frame.groupby(col):
                out[str(lab)] = econ(g)
        return out

    slices = {
        "by_class": slice_econ(fav_edge, "class_num"),
        "by_surface": {"AW": econ(fav_edge[fav_edge["is_aw"] == 1]), "Turf": econ(fav_edge[fav_edge["is_aw"] == 0])},
        "by_odds_band": slice_econ(fav_edge, "sp_dec", bins=[1, 2, 3, 5, 8, 1000], labels=["<2", "2-3", "3-5", "5-8", "8+"]),
        "by_field_size": slice_econ(fav_edge, "field_size", bins=[0, 7, 11, 16, 50], labels=["<=7", "8-11", "12-16", "17+"]),
    }

    p2_years = {y: v["P2_fav_ratings_edge"].get("roi_pct") for y, v in yearly.items() if v["P2_fav_ratings_edge"].get("n", 0) > 200}
    rois = [v for v in p2_years.values() if v is not None]
    stability = {
        "p2_yearly_roi": p2_years,
        "best_year": max(p2_years, key=lambda k: p2_years[k]) if p2_years else None,
        "worst_year": min(p2_years, key=lambda k: p2_years[k]) if p2_years else None,
        "positive_years": sum(1 for v in rois if v > 0),
        "total_years": len(rois),
    }

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "read_only_confirmed": True,
        "asset_profile": profile,
        "leakage_assessment": leakage,
        "exact_replay": {"status": "BLOCKED_LEAKAGE — see leakage_assessment"},
        "proxy_replay": {
            "definition": "Market-structure baselines. P2 ≠ VELO Tier A — it bounds what Tier A must beat and shows the decade's structure.",
            "overall": proxies,
            "yearly": yearly,
            "p2_slices": slices,
            "stability": stability,
        },
        "live_tier_a_reference": {
            "source": "data/current/sigma_roi_clv.json layer A by_tier",
            "n": 365, "sr": 0.3836, "roi_pct": 4.27,
            "note": "live realized economics, NOT replayed here",
        },
        "conclusion": (
            "The decade replay CANNOT validate Tier A with the current model (leakage). "
            "It CAN and does establish the baselines Tier A must beat, by year/class/"
            "surface/odds-band. The walk-forward harness is the path to real validation."
        ),
    }

    out = ROOT / "data/current/historical_tier_a_replay.json"
    out.write_text(json.dumps(report, indent=2))
    lines = ["# Historical Tier-A Replay — leakage-honest", "",
             f"Generated {report['generated_at']} · READ-ONLY", "",
             f"**EXACT_REPLAY: BLOCKED_LEAKAGE** — {'; '.join(leakage['reasons'][:2])}", "",
             "## Decade baselines (flat 1pt at SP)", "",
             "| Proxy | n | SR | avg SP | P&L | ROI |", "|---|---|---|---|---|---|"]
    for k, v in proxies.items():
        lines.append(f"| {k} | {v['n']:,} | {v['strike_rate']:.1%} | {v['avg_sp']} | {v['flat_1pt_pl']:,} | {v['roi_pct']}% |")
    lines += ["", "## P2 (fav + ratings edge) by year",
              "| Year | n | SR | ROI |", "|---|---|---|---|"]
    for y in sorted(yearly):
        v = yearly[y]["P2_fav_ratings_edge"]
        if v.get("n", 0) > 200:
            lines.append(f"| {y} | {v['n']:,} | {v['strike_rate']:.1%} | {v['roi_pct']}% |")
    lines += ["", f"**Stability:** positive years {stability['positive_years']}/{stability['total_years']} · best {stability['best_year']} · worst {stability['worst_year']}",
              "", f"**Conclusion:** {report['conclusion']}"]
    (ROOT / "data/reports/historical_tier_a_replay.md").write_text("\n".join(lines))

    print(f"-> {out}")
    for k, v in proxies.items():
        print(f"  {k}: n={v['n']:,} SR={v['strike_rate']:.1%} ROI={v['roi_pct']}%")
    print(f"  P2 positive years: {stability['positive_years']}/{stability['total_years']} (best {stability['best_year']}, worst {stability['worst_year']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
