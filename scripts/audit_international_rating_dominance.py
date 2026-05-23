#!/usr/bin/env python3
"""
International Rating Dominance Audit

Per-pack: computes winner max-rating rate for RPR, OR, TS.
Compares to random expected rate and favourite SR baseline.

Post-race leakage threshold: winner max-rating > 70%
Pre-race expectation: winner max-rating ~= top-pick SR (~40-50%)

Outputs:
  data/reports/international_rating_dominance_latest.json
  data/reports/international_rating_dominance_latest.md

Usage:
    PYTHONPATH=. python scripts/audit_international_rating_dominance.py
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

RATING_COLS = ["rpr_vs_field", "rpr_num", "or_vs_field", "or_num", "ts_num"]


def _compute_dominance(sub: pd.DataFrame, col: str) -> dict | None:
    if col not in sub.columns:
        return None

    coverage = (sub[col].notna() & sub[col].ne(0)).mean()
    if coverage < 0.10:
        return {"coverage": round(float(coverage), 4), "status": "LOW_COVERAGE"}

    max_count = 0
    top2_count = 0
    top3_count = 0
    total = 0
    avg_field = []

    for _, race in sub.groupby("race_id"):
        if race["target"].sum() != 1:
            continue
        vals = race[col].fillna(-999)
        if vals.eq(-999).all():
            continue
        winner_val = race.loc[race["target"] == 1, col].fillna(-999).values[0]
        if winner_val == -999:
            continue
        rank = vals.rank(ascending=False, method="min")
        winner_rank = rank[race["target"] == 1].values[0]
        max_count += int(winner_rank <= 1)
        top2_count += int(winner_rank <= 2)
        top3_count += int(winner_rank <= 3)
        total += 1
        avg_field.append(len(race))

    if total == 0:
        return {"status": "NO_VALID_RACES"}

    avg_field_size = float(np.mean(avg_field))
    random_expected = 1.0 / avg_field_size
    max_pct = max_count / total
    top2_pct = top2_count / total

    if max_pct > 0.70:
        verdict = "POST_RACE_LEAKAGE_SUSPECTED"
    elif max_pct > 0.55:
        verdict = "TIMESTAMP_UNKNOWN"
    else:
        verdict = "PRE_RACE_SAFE"

    return {
        "rating_col": col,
        "coverage": round(float(coverage), 4),
        "total_races": int(total),
        "avg_field_size": round(avg_field_size, 2),
        "random_expected": round(random_expected, 4),
        "winner_max_pct": round(max_pct, 4),
        "winner_top2_pct": round(top2_pct, 4),
        "winner_top3_pct": round(top3_count / total, 4),
        "lift_vs_random": round(max_pct - random_expected, 4),
        "verdict": verdict,
        "interpretation": (
            f"Winner has max {col} in {max_pct:.1%} of races. "
            f"Random expected: {random_expected:.1%}. "
            f"POST-RACE threshold: >70%. PRE-RACE expectation: ~40-50%."
        ),
    }


def _fav_baseline(sub: pd.DataFrame) -> dict:
    total = 0
    wins = 0
    for _, race in sub.groupby("race_id"):
        if race["target"].sum() != 1:
            continue
        if "is_fav" not in race.columns:
            continue
        favs = race[race["is_fav"] == 1]
        if len(favs) == 0:
            continue
        wins += favs["target"].sum()
        total += 1
    return {
        "total_races": int(total),
        "fav_sr": round(float(wins / total), 4) if total > 0 else None,
    }


def run_pack(pack_name: str, courses: list[str], df: pd.DataFrame) -> dict:
    print(f"\n[Dominance] Pack: {pack_name}")
    sub = df[df["course"].isin(courses)].copy()

    if len(sub) < 100:
        return {"pack": pack_name, "status": "INSUFFICIENT_DATA"}

    fav = _fav_baseline(sub)
    print(f"  Favourite SR: {fav.get('fav_sr', 0):.2%} (baseline)")

    dominance = {}
    for col in RATING_COLS:
        result = _compute_dominance(sub, col)
        if result is None:
            continue
        dominance[col] = result
        if isinstance(result, dict) and "winner_max_pct" in result:
            v = result["verdict"]
            pct = result["winner_max_pct"]
            print(f"  {col:20s}: winner_max={pct:.2%}  verdict={v}")

    # Overall verdict
    field_verdicts = [d.get("verdict", "TIMESTAMP_UNKNOWN") for d in dominance.values()
                      if isinstance(d, dict) and "verdict" in d]

    if any("POST_RACE" in v for v in field_verdicts):
        pack_verdict = "POST_RACE_LEAKAGE_SUSPECTED"
    elif all("PRE_RACE" in v for v in field_verdicts if v != "TIMESTAMP_UNKNOWN"):
        pack_verdict = "PRE_RACE_SAFE"
    else:
        pack_verdict = "TIMESTAMP_UNKNOWN"

    print(f"  => Pack dominance verdict: {pack_verdict}")

    return {
        "pack": pack_name,
        "courses": courses,
        "n_rows": int(len(sub)),
        "fav_baseline": fav,
        "dominance": dominance,
        "pack_verdict": pack_verdict,
    }


def main() -> None:
    print("[Dominance] Loading parquet...")
    df = pd.read_parquet(PQ_PATH)
    print(f"[Dominance] Rows: {len(df):,}")

    all_results = []
    for pack_name, courses in PACKS.items():
        result = run_pack(pack_name, courses, df)
        all_results.append(result)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "packs": all_results,
        "leakage_threshold": {
            "post_race_winner_max": "> 0.70",
            "pre_race_expected": "~0.40-0.50",
            "source": "If RPR is post-race performance rating, winner earns highest RPR in that race > 70% of the time",
        },
    }

    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(exist_ok=True)

    json_path = out_dir / "international_rating_dominance_latest.json"
    json_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n[Dominance] Written: {json_path}")

    md = _write_md(all_results, out)
    md_path = out_dir / "international_rating_dominance_latest.md"
    md_path.write_text(md)
    print(f"[Dominance] Written: {md_path}")

    print("\n=== SUMMARY ===")
    for r in all_results:
        verdict = r.get("pack_verdict", "N/A")
        rpr_dom = r.get("dominance", {}).get("rpr_vs_field", {})
        rpr_pct = rpr_dom.get("winner_max_pct", "?")
        rpr_pct_str = f"{rpr_pct:.2%}" if isinstance(rpr_pct, float) else str(rpr_pct)
        fav = r.get("fav_baseline", {}).get("fav_sr", "?")
        fav_str = f"{fav:.2%}" if isinstance(fav, float) else str(fav)
        print(f"  {r['pack']:25s} rpr_max={rpr_pct_str} fav={fav_str} => {verdict}")


def _write_md(all_results: list, out: dict) -> str:
    rows = ""
    for r in all_results:
        dom = r.get("dominance", {})
        fav = r.get("fav_baseline", {}).get("fav_sr", None)

        def _pct(d, key):
            v = d.get(key)
            return f"{v:.2%}" if isinstance(v, float) else "N/A"

        rpr_vs = dom.get("rpr_vs_field", {})
        or_vs = dom.get("or_vs_field", {})
        ts = dom.get("ts_num", {})
        verdict = r.get("pack_verdict", "N/A")

        rows += (
            f"| {r['pack']} "
            f"| {_pct(rpr_vs, 'winner_max_pct')} "
            f"| {_pct(or_vs, 'winner_max_pct')} "
            f"| {_pct(ts, 'winner_max_pct')} "
            f"| {f'{fav:.2%}' if isinstance(fav, float) else 'N/A'} "
            f"| **{verdict}** |\n"
        )

    threshold = out.get("leakage_threshold", {})

    return f"""# International Rating Dominance Audit

**Generated:** {out['generated_at']}

---

## Test Logic

If a rating is **post-race** (awarded based on performance in THIS race):
- The winner earns the highest rating in that race
- Winner max-rating rate: **> 70%**

If a rating is **pre-race** (the rating the horse brought INTO the race):
- Top-rated horse wins at roughly its historical rate (~40-50%)
- Winner max-rating rate: **~40-50% (approximately equal to top-pick SR)**

| Threshold | Verdict |
|---|---|
| Winner max-rating > 70% | POST_RACE_LEAKAGE_SUSPECTED |
| Winner max-rating 55-70% | TIMESTAMP_UNKNOWN |
| Winner max-rating 40-55% | PRE_RACE_SAFE |

---

## Results

| Pack | RPR winner-max | OR winner-max | TS winner-max | Fav SR | Verdict |
|---|---|---|---|---|---|
{rows}
---

## Expected Values

- **Post-race RPR**: winner max rate > 70-80% (RPR is awarded based on winning performance)
- **Pre-race RPR (historical)**: winner max rate ~= RPR-only top-pick SR (~40-50%)
- **Random**: winner max rate = 1 / avg_field_size (~8-10%)

---

```
DOMINANCE_AUDIT_STATUS: see per-pack above
POST_RACE_THRESHOLD: {threshold.get('post_race_winner_max')}
PRE_RACE_EXPECTED: {threshold.get('pre_race_expected')}
```
"""


if __name__ == "__main__":
    main()
