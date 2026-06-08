#!/usr/bin/env python3
"""
International Pre-Race Feature Safety Audit

For every feature in the HK and FR pre-race parquets, checks:
  - source column in original parquet
  - lag rule applied
  - whether any current-race value is used
  - null/zero rate
  - winner-max-rate (dominance test for leakage suspicion)
  - verdict: PRE_RACE_SAFE / DROP / REVIEW_REQUIRED

Winner-max-rate thresholds:
  > 0.70 → LEAKAGE_SUSPECTED → DROP
  0.55–0.70 → REVIEW_REQUIRED
  < 0.55 → PRE_RACE_SAFE

Outputs:
  data/reports/intl_prerace_feature_safety_latest.json
  data/reports/intl_prerace_feature_safety_latest.md

Usage:
    PYTHONPATH=. python scripts/audit_intl_prerace_feature_safety.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

HK_PQ = ROOT / "data" / "features" / "hk_prerace_features_v1.parquet"
FR_PQ = ROOT / "data" / "features" / "fr_prerace_features_v1.parquet"
ORIG_PQ = ROOT / "data" / "raceform_v17_features.parquet"

# Feature manifest: name → (source_cols, lag_rule, uses_current_race, pack)
FEATURE_MANIFEST = {
    # ── HK horse-level lagged ──────────────────────────────────────────────
    "prev_rpr_num": ("rpr_num", "shift(1) within horse", False, "HK"),
    "last3_rpr_avg": ("rpr_num", "shift(1).rolling(3).mean()", False, "HK"),
    "prev_or_num": ("or_num", "shift(1) within horse", False, "HK"),
    "last3_or_avg": ("or_num", "shift(1).rolling(3).mean()", False, "HK"),
    "prev_finish_pos": ("pos", "shift(1) within horse — prior run pos_num", False, "HK"),
    "last3_finish_avg": ("pos", "shift(1).rolling(3).mean()", False, "HK"),
    "days_since_last_run": ("date_parsed", "days to prior run date", False, "HK"),
    "starts_last_90": ("date_parsed", "count prior runs in 90-day window", False, "HK"),
    "course_prior_runs": ("course+target", "running count of prior runs at course", False, "HK"),
    "course_prior_wr": ("course+target", "running win rate at course (prior runs)", False, "HK"),
    "distance_prior_runs": ("dist_f+target", "running count at distance band", False, "HK"),
    "distance_prior_wr": ("dist_f+target", "running win rate at distance band", False, "HK"),
    "prev_class_num": ("class_num", "shift(1) within horse", False, "HK"),
    "class_move_direction": ("class_num", "class_num - prev_class_num", False, "HK"),
    "class_drop_flag": ("class_num", "class_move_direction > 0 (easier class)", False, "HK"),
    "class_rise_flag": ("class_num", "class_move_direction < 0 (harder class)", False, "HK"),
    "prior_class_win_rate": ("class_num+target", "running win rate at current class (prior)", False, "HK"),
    "prior_class_place_rate": ("class_num+pos", "running place rate at current class (prior)", False, "HK"),
    # ── HK draw features ──────────────────────────────────────────────────
    "draw_inside_flag": ("draw_pct", "draw_pct <= 0.33 (static race attr)", False, "HK"),
    "draw_outside_flag": ("draw_pct", "draw_pct >= 0.67 (static race attr)", False, "HK"),
    "draw_win_rate_lagged": ("draw_bucket+course+dist_band+target", "cumsum up to prior dates only", False, "HK"),
    "draw_place_rate_lagged": ("draw_bucket+course+dist_band+pos", "cumsum up to prior dates only", False, "HK"),
    # ── HK race-level ─────────────────────────────────────────────────────
    "field_avg_prev_rpr": ("prev_rpr_num", "mean prev_rpr across race field", False, "HK"),
    "field_std_prev_rpr": ("prev_rpr_num", "std prev_rpr across race field", False, "HK"),
    "field_avg_prev_or": ("prev_or_num", "mean prev_or across race field", False, "HK"),
    "rpr_rank_lagged": ("prev_rpr_num", "rank within race by prior RPR", False, "HK"),
    "or_rank_lagged": ("prev_or_num", "rank within race by prior OR", False, "HK"),
    "rating_consensus_lagged": ("prev_rpr_num+prev_or_num", "-(rpr_rank+or_rank)/2", False, "HK"),
    "race_competitiveness_pre": ("prev_or_num", "field_avg_prev_or / 10", False, "HK"),
    # ── FR horse-level lagged ─────────────────────────────────────────────
    "lagged_rpr_last1": ("rpr_num", "shift(1) within horse — prior run RPR", False, "FR"),
    "lagged_rpr_last3_avg": ("rpr_num", "shift(1).rolling(3).mean()", False, "FR"),
    "lagged_rpr_last3_max": ("rpr_num", "shift(1).rolling(3).max()", False, "FR"),
    "lagged_ts_last1": ("ts_num", "shift(1) within horse — prior run TS", False, "FR"),
    "lagged_ts_last3_avg": ("ts_num", "shift(1).rolling(3).mean()", False, "FR"),
    "prev_finish_pos_fr": ("pos", "shift(1) within horse — prior run pos_num", False, "FR"),
    "last3_finish_avg_fr": ("pos", "shift(1).rolling(3).mean()", False, "FR"),
    # ── FR race context ───────────────────────────────────────────────────
    "going_is_fast": ("going_code", "going_code <= 0 (pre-race going assessment)", False, "FR"),
    "going_is_good": ("going_code", "going_code == 1", False, "FR"),
    "going_is_soft": ("going_code", "going_code >= 2", False, "FR"),
    "is_hurdle": ("type", "race type = Hurdle (pre-race)", False, "FR"),
    "is_chase": ("type", "race type = Chase (pre-race)", False, "FR"),
    "is_flat_code": ("type", "race type = Flat/NH Flat (pre-race)", False, "FR"),
    # ── FR placeholders ───────────────────────────────────────────────────
    "penetrometer_available": ("N/A", "PLACEHOLDER — PMU future enrichment", False, "FR"),
    "quintet_plus_available": ("N/A", "PLACEHOLDER — PMU future enrichment", False, "FR"),
    "class_proxy_available": ("N/A", "PLACEHOLDER — France Galop future enrichment", False, "FR"),
    # ── FR race-level ─────────────────────────────────────────────────────
    "field_avg_prev_rpr_fr": ("lagged_rpr_last1", "mean across race field", False, "FR"),
    "field_std_prev_rpr_fr": ("lagged_rpr_last1", "std across race field", False, "FR"),
    "rpr_rank_lagged_fr": ("lagged_rpr_last1", "rank within race by prior RPR", False, "FR"),
    "race_competitiveness_pre_fr": ("lagged_rpr_last1", "field_avg_prev_rpr / 10", False, "FR"),
    # ── Known banned features (should not appear in output) ───────────────
    "rpr_num": ("rpr_num", "SAME_RACE — BANNED", True, "ALL"),
    "or_num": ("or_num", "SAME_RACE — BANNED", True, "ALL"),
    "ts_num": ("ts_num", "SAME_RACE — BANNED", True, "ALL"),
    "rpr_vs_field": ("rpr_vs_field", "SAME_RACE — BANNED", True, "ALL"),
    "sp_dec": ("sp_dec", "POST_RACE — BANNED", True, "ALL"),
    "implied_prob": ("implied_prob", "POST_RACE — BANNED", True, "ALL"),
    "is_fav": ("is_fav", "MARKET — BANNED", True, "ALL"),
    "pos": ("pos", "POST_RACE_RESULT — BANNED", True, "ALL"),
}

LEAKAGE_THRESHOLD = 0.70
REVIEW_THRESHOLD = 0.55
MIN_SAMPLE_FOR_DOMINANCE = 50


def _winner_max_rate(df: pd.DataFrame, col: str) -> dict:
    if col not in df.columns:
        return {"status": "NOT_IN_PARQUET"}
    coverage = df[col].notna().mean()
    if coverage < 0.05:
        return {"coverage": round(float(coverage), 4), "status": "LOW_COVERAGE"}

    # Check if feature is a race-level constant (same value for all runners in a race).
    # Race-level constants (going, race type, field averages) produce winner_max=100% trivially
    # because ties are broken arbitrarily — NOT leakage.
    race_within_std = df.groupby("race_id")[col].std()
    mean_within_std = race_within_std.fillna(0).mean()
    if mean_within_std < 0.01:
        return {
            "coverage": round(float(coverage), 4),
            "status": "RACE_LEVEL_CONSTANT",
            "verdict": "PRE_RACE_SAFE",
            "reason": (
                "Feature is constant within each race — dominance test N/A. "
                "Verify source is pre-race. Flagged safe if derived from race attributes or lagged values."
            ),
        }

    max_count, total = 0, 0
    for _, race in df.groupby("race_id"):
        if race["target"].sum() != 1:
            continue
        vals = race[col].fillna(-np.inf)
        if vals.eq(-np.inf).all():
            continue
        winner_val = race.loc[race["target"] == 1, col].fillna(-np.inf).values[0]
        if winner_val == -np.inf:
            continue
        winner_rank = vals.rank(ascending=False, method="min")[race["target"] == 1].values[0]
        max_count += int(winner_rank <= 1)
        total += 1

    if total < MIN_SAMPLE_FOR_DOMINANCE:
        return {"status": "INSUFFICIENT_RACES", "total_races": total}

    winner_max_pct = max_count / total

    # Binary flags: high winner_max can be an artifact when most runners share the same flag.
    # Check: what fraction of races have zero variance on this feature (all same value)?
    zero_var_races = int((race_within_std.fillna(0) < 0.01).sum())
    zero_var_pct = zero_var_races / max(len(race_within_std), 1)
    flag_note = f" ({zero_var_pct:.0%} of races have zero within-race variance)" if zero_var_pct > 0.3 else ""

    if winner_max_pct > LEAKAGE_THRESHOLD:
        verdict = "DROP"
        reason = f"winner_max={winner_max_pct:.2%} > {LEAKAGE_THRESHOLD:.0%} — leakage suspected{flag_note}"
    elif winner_max_pct > REVIEW_THRESHOLD:
        verdict = "REVIEW_REQUIRED"
        reason = f"winner_max={winner_max_pct:.2%} — timestamp uncertain{flag_note}"
    else:
        verdict = "PRE_RACE_SAFE"
        reason = f"winner_max={winner_max_pct:.2%} — consistent with pre-race signal"

    return {
        "coverage": round(float(coverage), 4),
        "total_races": int(total),
        "winner_max_pct": round(float(winner_max_pct), 4),
        "zero_var_race_pct": round(float(zero_var_pct), 4),
        "verdict": verdict,
        "reason": reason,
    }


def audit_parquet(df: pd.DataFrame, pack_label: str, feature_cols: list[str]) -> list[dict]:
    results = []
    for col in feature_cols:
        manifest_entry = FEATURE_MANIFEST.get(col, {})
        source = manifest_entry[0] if manifest_entry else "UNKNOWN"
        lag_rule = manifest_entry[1] if manifest_entry else "UNKNOWN"
        uses_current = manifest_entry[2] if manifest_entry else None

        null_rate = df[col].isna().mean() if col in df.columns else 1.0
        zero_rate = (df[col] == 0).mean() if col in df.columns else 0.0

        if uses_current is True:
            verdict = "DROP"
            reason = "Uses current-race value — banned"
            dominance = {"status": "SKIPPED_BANNED"}
        elif col in ("penetrometer_available", "quintet_plus_available", "class_proxy_available"):
            verdict = "FUTURE_ENRICHMENT"
            reason = "Placeholder — data source not yet available"
            dominance = {"status": "PLACEHOLDER"}
        else:
            dominance = _winner_max_rate(df, col) if col in df.columns else {"status": "NOT_IN_PARQUET"}
            verdict = dominance.get("verdict", "REVIEW_REQUIRED")

        results.append({
            "feature": col,
            "pack": pack_label,
            "source_col": source,
            "lag_rule": lag_rule,
            "uses_current_race": uses_current,
            "null_rate": round(float(null_rate), 4),
            "zero_rate": round(float(zero_rate), 4),
            "dominance": dominance,
            "verdict": verdict,
        })

    return results


def main() -> None:
    print("[SafetyAudit] Loading feature parquets...")
    hk_df = pd.read_parquet(HK_PQ) if HK_PQ.exists() else None
    fr_df = pd.read_parquet(FR_PQ) if FR_PQ.exists() else None

    if hk_df is None:
        print("[SafetyAudit] ERROR: HK feature parquet missing. Run build_hk_prerace_features.py first.")
        return
    if fr_df is None:
        print("[SafetyAudit] ERROR: FR feature parquet missing. Run build_fr_prerace_features.py first.")
        return

    print(f"[SafetyAudit] HK rows: {len(hk_df):,}  |  FR rows: {len(fr_df):,}")

    # Feature columns to audit (exclude static identifiers)
    STATIC = {"race_id", "horse", "course", "date", "date_parsed", "target",
               "draw_num", "draw_pct", "field_size", "dist_f", "going_code",
               "wgt_lbs", "age_num", "is_aw", "type", "class_num"}

    hk_feature_cols = [c for c in hk_df.columns if c not in STATIC]
    fr_feature_cols = [c for c in fr_df.columns if c not in STATIC]

    print(f"[SafetyAudit] Auditing {len(hk_feature_cols)} HK features...")
    hk_results = audit_parquet(hk_df, "HK", hk_feature_cols)

    print(f"[SafetyAudit] Auditing {len(fr_feature_cols)} FR features...")
    fr_results = audit_parquet(fr_df, "FR", fr_feature_cols)

    all_results = hk_results + fr_results

    # Summary counts
    verdict_counts: dict[str, int] = {}
    for r in all_results:
        v = r["verdict"]
        verdict_counts[v] = verdict_counts.get(v, 0) + 1

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hk_features_audited": len(hk_feature_cols),
        "fr_features_audited": len(fr_feature_cols),
        "verdict_counts": verdict_counts,
        "features": all_results,
    }

    report_dir = ROOT / "data" / "reports"
    report_dir.mkdir(exist_ok=True)

    json_path = report_dir / "intl_prerace_feature_safety_latest.json"
    json_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"[SafetyAudit] Written: {json_path}")

    md = _write_md(out, all_results, verdict_counts)
    md_path = report_dir / "intl_prerace_feature_safety_latest.md"
    md_path.write_text(md)
    print(f"[SafetyAudit] Written: {md_path}")

    print("\n=== VERDICT SUMMARY ===")
    for v, count in sorted(verdict_counts.items()):
        print(f"  {v:<25s}: {count}")

    drops = [r for r in all_results if r["verdict"] == "DROP"]
    reviews = [r for r in all_results if r["verdict"] == "REVIEW_REQUIRED"]
    if drops:
        print(f"\n[!] DROP features ({len(drops)}):")
        for r in drops:
            wmr = r["dominance"].get("winner_max_pct", "?")
            wmr_str = f"{wmr:.2%}" if isinstance(wmr, float) else str(wmr)
            print(f"    {r['feature']:<40s} winner_max={wmr_str}  {r['dominance'].get('reason', '')}")
    if reviews:
        print(f"\n[~] REVIEW_REQUIRED features ({len(reviews)}):")
        for r in reviews:
            wmr = r["dominance"].get("winner_max_pct", "?")
            wmr_str = f"{wmr:.2%}" if isinstance(wmr, float) else str(wmr)
            print(f"    {r['feature']:<40s} winner_max={wmr_str}")


def _write_md(out: dict, results: list, verdict_counts: dict) -> str:
    summary_rows = "\n".join(f"| {v} | {c} |" for v, c in sorted(verdict_counts.items()))

    detail_rows = ""
    for r in results:
        dom = r["dominance"]
        wmr = dom.get("winner_max_pct", "N/A")
        wmr_str = f"{wmr:.2%}" if isinstance(wmr, float) else str(wmr)
        verdict_str = f"**{r['verdict']}**" if r["verdict"] in ("DROP", "REVIEW_REQUIRED") else r["verdict"]
        detail_rows += (
            f"| {r['pack']} | {r['feature']} | {r['null_rate']:.1%} "
            f"| {wmr_str} | {verdict_str} |\n"
        )

    return f"""# International Pre-Race Feature Safety Audit

**Generated:** {out['generated_at']}

---

## Verdict Summary

| Verdict | Count |
|---|---|
{summary_rows}

---

## Feature Detail

| Pack | Feature | Null Rate | Winner-Max | Verdict |
|---|---|---|---|---|
{detail_rows}
---

## Dominance Test

Winner-max rate thresholds (same as rating provenance audit):
- > 70%: DROP (leakage suspected)
- 55–70%: REVIEW_REQUIRED
- < 55%: PRE_RACE_SAFE

---

```
SAFETY_AUDIT_STATUS: COMPLETE
LEAKAGE_THRESHOLD: 0.70
REVIEW_THRESHOLD: 0.55
```
"""


if __name__ == "__main__":
    main()
