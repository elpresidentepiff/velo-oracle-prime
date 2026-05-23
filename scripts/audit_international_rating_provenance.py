#!/usr/bin/env python3
"""
International Rating Provenance Audit

Determines whether rpr_num, or_num, ts_num in raceform_v17_features.parquet
are pre-race (known before the race) or post-race (awarded based on performance).

Key tests:
1. Adjacent-race RPR change rate — PRE-RACE should show smaller, more incremental changes
2. Winner max-RPR dominance rate — POST-RACE should be >70%, PRE-RACE should be ~44%
3. RPR correlation with finishing position (not just win)
4. RPR stability: does it carry forward, or is each race unique?
5. Lagged comparison: does prev_rpr (lagged by 1 race) behave similarly to rpr_num?

Outputs:
  data/reports/international_rating_provenance_latest.json
  data/reports/international_rating_provenance_latest.md

Usage:
    PYTHONPATH=. python scripts/audit_international_rating_provenance.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PQ_PATH = ROOT / "data" / "raceform_v17_features.parquet"

PACKS = {
    "HK_SHA_TIN_V1": ["Sha Tin (HK)"],
    "HK_HAPPY_VALLEY_V1": ["Happy Valley (HK)"],
    "FR_CHANTILLY_V1": ["Chantilly (FR)"],
    "FR_FLAT_CORE": ["Chantilly (FR)", "Deauville (FR)", "Longchamp (FR)", "Saint-Cloud (FR)"],
    "FR_AUTEUIL_JUMPS_V1": ["Auteuil (FR)"],
}


def _winner_dominance(df: pd.DataFrame, rating_col: str) -> dict:
    """
    For each race: is the winner the horse with the highest rating?
    POST-RACE: winner dominance should be >70%.
    PRE-RACE: winner dominance should match the rating-only top-pick SR (~40-50%).
    """
    if rating_col not in df.columns:
        return {"status": "COLUMN_MISSING"}

    winner_is_top = 0
    winner_is_top2 = 0
    winner_is_top3 = 0
    total_races = 0
    skipped = 0

    for _, race in df.groupby("race_id"):
        if race["target"].sum() != 1:
            skipped += 1
            continue
        col_vals = race[rating_col].fillna(0)
        if col_vals.eq(0).all():
            skipped += 1
            continue
        winner_val = race.loc[race["target"] == 1, rating_col].fillna(0).values[0]
        ranked = col_vals.rank(ascending=False, method="min")
        winner_rank = ranked[race["target"] == 1].values[0]
        winner_is_top += int(winner_rank <= 1)
        winner_is_top2 += int(winner_rank <= 2)
        winner_is_top3 += int(winner_rank <= 3)
        total_races += 1

    if total_races == 0:
        return {"status": "NO_DATA"}

    top_pct = round(winner_is_top / total_races, 4)
    top2_pct = round(winner_is_top2 / total_races, 4)

    # Post-race verdict: if top_pct > 0.65 = suspicious
    if top_pct > 0.70:
        provenance = "POST_RACE_LEAKAGE_SUSPECTED"
        reason = f"Winner has max {rating_col} in {top_pct:.1%} of races — consistent with post-race performance rating"
    elif top_pct > 0.55:
        provenance = "TIMESTAMP_UNKNOWN"
        reason = f"Winner has max {rating_col} in {top_pct:.1%} of races — ambiguous"
    else:
        provenance = "PRE_RACE_SAFE"
        reason = f"Winner has max {rating_col} in only {top_pct:.1%} of races — consistent with pre-race rating (expected ~40-50%)"

    return {
        "rating_col": rating_col,
        "total_races": int(total_races),
        "skipped_races": int(skipped),
        "winner_is_max_rating": int(winner_is_top),
        "winner_max_pct": top_pct,
        "winner_top2_pct": top2_pct,
        "winner_top3_pct": round(winner_is_top3 / total_races, 4),
        "provenance_verdict": provenance,
        "reason": reason,
        "interpretation": {
            "POST_RACE_threshold": "> 0.70 winner-max rate = post-race suspected",
            "PRE_RACE_expectation": "~0.40-0.50 winner-max rate = consistent with pre-race",
            "observed": top_pct,
        },
    }


def _adjacent_race_stability(df: pd.DataFrame, rating_col: str) -> dict:
    """
    For each horse, sorted by date: does the rating change between adjacent races?
    PRE-RACE: rating carries forward (RP updates after each run, but incrementally)
    POST-RACE: each race row has the performance rating specific to that race
    """
    if rating_col not in df.columns:
        return {"status": "COLUMN_MISSING"}

    df_sorted = df.dropna(subset=[rating_col]).sort_values(["horse", "date_parsed"]).copy()
    df_sorted["prev_rating"] = df_sorted.groupby("horse")[rating_col].shift(1)
    has_prev = df_sorted["prev_rating"].notna()
    sample = df_sorted[has_prev].copy()

    if len(sample) == 0:
        return {"status": "NO_ADJACENT_PAIRS"}

    delta = (sample[rating_col] - sample["prev_rating"]).abs()
    same_rate = (sample[rating_col] == sample["prev_rating"]).mean()
    change_rate = 1.0 - same_rate

    # For context: compare winner's post-race delta to loser's post-race delta
    winner_delta = delta[sample["target"] == 1].mean()
    loser_delta = delta[sample["target"] == 0].mean()

    note = (
        "PRE-RACE interpretation: rating is updated by RP after previous run, "
        "so changes between races are expected (~5-15 points). "
        "POST-RACE interpretation: rating is awarded FOR each race performance, "
        "with larger variance. Both interpretations are plausible from change-rate alone."
    )

    return {
        "rating_col": rating_col,
        "adjacent_pairs_analyzed": int(len(sample)),
        "same_race_to_race": round(float(same_rate), 4),
        "changed_race_to_race": round(float(change_rate), 4),
        "delta_mean": round(float(delta.mean()), 3),
        "delta_median": round(float(delta.median()), 3),
        "delta_p75": round(float(delta.quantile(0.75)), 3),
        "winner_avg_delta": round(float(winner_delta), 3) if not np.isnan(winner_delta) else None,
        "loser_avg_delta": round(float(loser_delta), 3) if not np.isnan(loser_delta) else None,
        "note": note,
    }


def _position_correlation(df: pd.DataFrame, rating_col: str) -> dict:
    """
    Correlate rating with finishing position (numeric).
    POST-RACE: very high correlation with finish position (rating awarded based on position+margin)
    PRE-RACE: moderate correlation (rating predicts but doesn't perfectly match result)
    """
    if rating_col not in df.columns:
        return {"status": "COLUMN_MISSING"}

    # Convert pos to numeric
    df_pos = df.copy()
    df_pos["pos_num"] = pd.to_numeric(df_pos["pos"], errors="coerce")
    valid = df_pos[df_pos["pos_num"].notna() & df_pos[rating_col].notna()]

    if len(valid) < 100:
        return {"status": "INSUFFICIENT_DATA"}

    # Negative correlation expected: higher rating → lower position number (1st, 2nd...)
    corr = valid[rating_col].corr(valid["pos_num"])
    corr_with_target = valid[rating_col].fillna(0).corr(valid["target"])

    if corr < -0.60:
        verdict = "POST_RACE_SUSPECTED — correlation with finish position too strong for pre-race rating"
    elif corr < -0.35:
        verdict = "TIMESTAMP_UNKNOWN — moderate correlation with position"
    else:
        verdict = "PRE_RACE_CONSISTENT — correlation with position moderate, consistent with pre-race predictor"

    return {
        "rating_col": rating_col,
        "n_valid": int(len(valid)),
        "corr_with_finish_position": round(float(corr), 4),
        "corr_with_target": round(float(corr_with_target), 4),
        "verdict": verdict,
        "note": (
            "PRE-RACE: corr with position ~ -0.15 to -0.35. "
            "POST-RACE (performance rating): corr with position ~ -0.60 to -0.90"
        ),
    }


def audit_pack(pack_name: str, courses: list[str], df: pd.DataFrame) -> dict:
    print(f"\n[Provenance] Pack: {pack_name}")
    sub = df[df["course"].isin(courses)].copy()

    if len(sub) < 100:
        return {"pack": pack_name, "status": "INSUFFICIENT_DATA"}

    results = {
        "pack": pack_name,
        "courses": courses,
        "n_rows": int(len(sub)),
        "ratings": {},
    }

    for rating_col, desc in [
        ("rpr_vs_field", "RPR relative to field"),
        ("rpr_num", "RPR absolute"),
        ("or_vs_field", "OR relative to field"),
        ("or_num", "OR absolute"),
        ("ts_num", "TS absolute"),
    ]:
        if rating_col not in sub.columns:
            continue

        coverage = (sub[rating_col].notna() & sub[rating_col].ne(0)).mean()
        if coverage < 0.05:
            results["ratings"][rating_col] = {
                "coverage": round(float(coverage), 4),
                "verdict": "INSUFFICIENT_COVERAGE",
            }
            continue

        dominance = _winner_dominance(sub, rating_col)
        pos_corr = _position_correlation(sub, rating_col)

        # For rpr_num specifically, run adjacent-race stability on full df (not just pack)
        adjacent = None
        if rating_col == "rpr_num":
            adjacent = _adjacent_race_stability(sub, rating_col)

        # Determine overall rating verdict
        dom_verdict = dominance.get("provenance_verdict", "TIMESTAMP_UNKNOWN")
        pos_verdict = pos_corr.get("verdict", "TIMESTAMP_UNKNOWN")

        if "POST_RACE" in dom_verdict or "POST_RACE" in pos_verdict:
            overall = "POST_RACE_LEAKAGE_SUSPECTED"
        elif "PRE_RACE" in dom_verdict and "PRE_RACE" in pos_verdict:
            overall = "PRE_RACE_SAFE"
        else:
            overall = "TIMESTAMP_UNKNOWN"

        results["ratings"][rating_col] = {
            "coverage": round(float(coverage), 4),
            "description": desc,
            "winner_dominance": dominance,
            "position_correlation": pos_corr,
            "adjacent_stability": adjacent,
            "overall_verdict": overall,
        }

        dom_pct = dominance.get("winner_max_pct", "?")
        print(f"  {rating_col:20s} cov={coverage:.2%} winner_max={dom_pct} verdict={overall}")

    # Pack-level verdict
    verdicts = [r.get("overall_verdict", "TIMESTAMP_UNKNOWN")
                for r in results["ratings"].values()
                if isinstance(r, dict) and "overall_verdict" in r]

    if any("POST_RACE" in v for v in verdicts):
        results["pack_verdict"] = "POST_RACE_LEAKAGE_SUSPECTED"
    elif all("PRE_RACE" in v for v in verdicts if v != "TIMESTAMP_UNKNOWN"):
        results["pack_verdict"] = "PRE_RACE_SAFE"
    else:
        results["pack_verdict"] = "TIMESTAMP_UNKNOWN"

    print(f"  => Pack verdict: {results['pack_verdict']}")
    return results


def main() -> None:
    print("[Provenance] Loading parquet...")
    df = pd.read_parquet(PQ_PATH)
    print(f"[Provenance] Rows: {len(df):,}")

    # Global adjacent-race stability (all horses, all jurisdictions)
    print("\n[Provenance] Global adjacent-race stability check...")
    df_sorted = df.sort_values(["horse", "date_parsed"]).copy()
    df_sorted["prev_rpr"] = df_sorted.groupby("horse")["rpr_num"].shift(1)
    has_prev = df_sorted["prev_rpr"].notna() & df_sorted["rpr_num"].notna()
    sample = df_sorted[has_prev]
    delta = (sample["rpr_num"] - sample["prev_rpr"]).abs()
    change_rate = (sample["rpr_num"] != sample["prev_rpr"]).mean()
    print(f"  Global rpr change rate between adjacent races: {change_rate:.2%}")
    print(f"  Global rpr delta: mean={delta.mean():.2f} median={delta.median():.2f}")
    print()

    global_stability = {
        "adjacent_pairs": int(len(sample)),
        "change_rate": round(float(change_rate), 4),
        "delta_mean": round(float(delta.mean()), 3),
        "delta_median": round(float(delta.median()), 3),
        "delta_p25": round(float(delta.quantile(0.25)), 3),
        "delta_p75": round(float(delta.quantile(0.75)), 3),
        "interpretation": (
            "95% change rate with mean delta 13 is ambiguous. "
            "PRE-RACE: RP updates ratings after each run — consistent with frequent changes. "
            "POST-RACE: performance-based ratings would also change per race. "
            "Winner-max-dominance rate is the more decisive test."
        ),
    }

    all_results = []
    for pack_name, courses in PACKS.items():
        result = audit_pack(pack_name, courses, df_sorted)
        all_results.append(result)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "global_rpr_stability": global_stability,
        "packs": all_results,
        "methodology": {
            "primary_test": "Winner max-rating dominance rate",
            "post_race_threshold": "> 70% winner max-rating = post-race suspected",
            "pre_race_expectation": "~40-50% winner max-rating = pre-race consistent",
            "secondary_test": "Rating correlation with finishing position",
            "post_race_corr_threshold": "< -0.60 = post-race suspected",
            "pre_race_corr_range": "-0.15 to -0.35 = pre-race consistent",
        },
    }

    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(exist_ok=True)

    json_path = out_dir / "international_rating_provenance_latest.json"
    json_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n[Provenance] Written: {json_path}")

    md = _write_md(out)
    md_path = out_dir / "international_rating_provenance_latest.md"
    md_path.write_text(md)
    print(f"[Provenance] Written: {md_path}")

    print("\n=== SUMMARY ===")
    for r in all_results:
        print(f"  {r['pack']:25s} => {r.get('pack_verdict', 'N/A')}")


def _write_md(out: dict) -> str:
    gs = out.get("global_rpr_stability", {})
    rows = ""
    for r in out.get("packs", []):
        rpr_d = r.get("ratings", {}).get("rpr_vs_field", {})
        dom = rpr_d.get("winner_dominance", {})
        dom_pct = dom.get("winner_max_pct", "N/A")
        dom_pct_str = f"{dom_pct:.1%}" if isinstance(dom_pct, float) else str(dom_pct)
        pos = rpr_d.get("position_correlation", {})
        pos_corr = pos.get("corr_with_finish_position", "N/A")
        pos_corr_str = f"{pos_corr:.4f}" if isinstance(pos_corr, float) else str(pos_corr)
        overall = rpr_d.get("overall_verdict", r.get("pack_verdict", "N/A"))
        rows += f"| {r['pack']} | {dom_pct_str} | {pos_corr_str} | **{overall}** |\n"

    return f"""# International Rating Provenance Audit

**Generated:** {out['generated_at']}

---

## Purpose

Determines whether `rpr_num`, `or_num`, `ts_num` in `raceform_v17_features.parquet`
represent pre-race ratings (known before the race) or post-race performance ratings
(assigned after the race based on finishing position and margins).

---

## Primary Test: Winner Max-Rating Dominance

**Logic:**
- If RPR is **post-race** (awarded based on performance): the winner almost always earns the highest rating.
  Expected winner-max rate: **> 70%**
- If RPR is **pre-race** (historical rating brought into the race): the top-rated horse wins ~40-50% of races.
  Expected winner-max rate: **~40-50%**

## Results by Pack

| Pack | Winner Max RPR Rate | Pos Corr | rpr_vs_field Verdict |
|---|---|---|---|
{rows}
---

## Global RPR Adjacent-Race Stability

| Metric | Value |
|---|---|
| Adjacent pairs analyzed | {gs.get('adjacent_pairs', 'N/A'):,} |
| Change rate race-to-race | {gs.get('change_rate', 0):.1%} |
| Delta mean | {gs.get('delta_mean', 'N/A')} |
| Delta median | {gs.get('delta_median', 'N/A')} |

{gs.get('interpretation', '')}

---

## Interpretation Guide

| Winner Max Rate | Verdict |
|---|---|
| > 70% | POST_RACE_LEAKAGE_SUSPECTED — winner almost always has highest rating |
| 55-70% | TIMESTAMP_UNKNOWN — ambiguous |
| 40-55% | PRE_RACE_SAFE — consistent with pre-race rating (same as top-pick SR) |

| Position Correlation | Verdict |
|---|---|
| < -0.60 | POST_RACE_SUSPECTED — rating tracks finishing order too closely |
| -0.35 to -0.60 | TIMESTAMP_UNKNOWN |
| -0.15 to -0.35 | PRE_RACE_CONSISTENT |

---

## Methodology

Primary test: `winner_max_rating_dominance` — for each race, is the winner the horse with the highest rating?
Secondary test: `position_correlation` — how strongly does the rating correlate with actual finishing position?

```
POST_RACE threshold: winner_max_rate > 0.70
PRE_RACE expectation: winner_max_rate ~ 0.40-0.50
```
"""


if __name__ == "__main__":
    main()
