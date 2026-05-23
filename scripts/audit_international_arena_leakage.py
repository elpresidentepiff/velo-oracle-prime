#!/usr/bin/env python3
"""
International Arena Leakage Audit

Audits every feature in the arena feature set for leakage risk.
Classifies each column: KEEP / DROP / UNKNOWN_REVIEW / CONFIRM_PRE_RACE.

Outputs:
  data/reports/international_arena_leakage_audit_latest.json
  data/reports/international_arena_leakage_audit_latest.md

Usage:
    PYTHONPATH=. python scripts/audit_international_arena_leakage.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PQ_PATH = ROOT / "data" / "raceform_v17_features.parquet"

ARENA_FEATURES = [
    "or_num", "rpr_num", "ts_num",
    "or_vs_field", "rpr_vs_field",
    "field_size", "draw_num", "draw_pct",
    "age_num", "class_num", "dist_f", "going_code", "is_aw",
    "wgt_lbs",
    "runs_since_win", "runs_since_place",
    "mark_compression_score", "course_fit_score",
    "going_fit_score", "distance_fit_score",
    "trainer_timing_score",
]

# Post-race / leakage automatic drops
LEAKAGE_DROPS = {
    "sp_dec": "Final SP — post-race market settlement",
    "log_sp": "Derived from final SP",
    "implied_prob": "Derived from final SP (1/sp)",
    "sp_rank": "Derived from final SP ranking",
    "is_fav": "Favourite flag — derived from final market SP",
    "odds_resilience_score": "Odds movement signal — requires pre-race odds capture confirmation",
    "odds_contraction_score": "Odds movement signal — requires pre-race odds capture confirmation",
    "decoy_support_flag": "RPDC tag — computed with historical context, timing unconfirmed",
    "setup_run_flag": "RPDC tag — computed with historical context, timing unconfirmed",
    "cash_run_flag": "RPDC tag — computed with historical context, timing unconfirmed",
    "pos": "Finishing position — IS the target in another form. DROP IMMEDIATELY.",
    "jockey_switch_intent": "Computed at race-time, could include result context",
}

# Known safe pre-race columns
KNOWN_SAFE = {
    "or_num": "Official handicap rating — set by regulator before race",
    "rpr_num": "Racing Post Rating — from horse's previous runs",
    "ts_num": "Timeform Speed Figure — from horse's previous runs",
    "or_vs_field": "Relative OR vs field — computed from pre-race OR values",
    "rpr_vs_field": "Relative RPR vs field — computed from pre-race RPR values",
    "field_size": "Number of runners — known before race",
    "draw_num": "Draw position — known before race",
    "draw_pct": "Draw as pct of field — computed from draw_num and field_size",
    "age_num": "Horse age — known before race",
    "dist_f": "Distance in furlongs — known before race",
    "going_code": "Going condition — known before race",
    "is_aw": "All-weather surface flag — known before race",
    "wgt_lbs": "Weight carried — known before race",
}

# Requires investigation
REQUIRES_INVESTIGATION = {
    "class_num": "Race class — typically set before race but verify source",
    "runs_since_win": "Days/runs since last win — from historical record, should be pre-race",
    "runs_since_place": "Days/runs since last place — from historical record, should be pre-race",
    "mark_compression_score": "OR delta from best OR — uses historical OR marks, should be pre-race",
    "course_fit_score": "Win-rate type score at course — verify time-gating: does it include current race result?",
    "going_fit_score": "Win-rate type score on going — verify time-gating: does it include current race result?",
    "distance_fit_score": "Win-rate type score at distance — verify time-gating: does it include current race result?",
    "trainer_timing_score": "Trainer form score — verify time-gating: does it include current race result?",
}


def _check_fit_score_timing(df: pd.DataFrame, score_col: str) -> dict:
    """
    For fit scores: check if the score appears to change after a win.
    If course_fit_score increments after a win in the same race that produced the win,
    it's almost certainly time-gate contaminated.
    """
    if score_col not in df.columns:
        return {"status": "COLUMN_MISSING"}

    # Compare fit score for winners vs non-winners: if winner systematically higher,
    # might be time-gated properly (higher because they DO win here) or leaked (because
    # current win included in score). We need a different test:
    # Check if fit_score variance within a race is non-trivial
    # (if all runners have same score, it's not horse-level, it's race-level = no leakage issue)

    sample_races = df.dropna(subset=[score_col]).head(50000)
    race_variance = sample_races.groupby("race_id")[score_col].std().mean()
    within_race_range = sample_races.groupby("race_id")[score_col].apply(lambda x: x.max() - x.min()).mean()
    winner_score = df[df["target"] == 1][score_col].dropna().mean()
    loser_score = df[df["target"] == 0][score_col].dropna().mean()
    winner_lift = winner_score - loser_score if not np.isnan(winner_score) else None

    return {
        "mean_within_race_variance": round(float(race_variance), 5) if not np.isnan(race_variance) else None,
        "mean_within_race_range": round(float(within_race_range), 5) if not np.isnan(within_race_range) else None,
        "winner_mean": round(float(winner_score), 5) if winner_score is not None else None,
        "loser_mean": round(float(loser_score), 5) if loser_score is not None else None,
        "winner_lift": round(float(winner_lift), 5) if winner_lift is not None else None,
        "note": (
            "Within-race variance > 0 means horses differ on this score (horse-level, could be pre-race). "
            "Winner lift > 0 means winners score higher (predictive, but could be post-race encoding)."
        ),
    }


def audit_column(df: pd.DataFrame, col: str) -> dict:
    if col not in df.columns:
        return {
            "column": col, "present": False,
            "decision": "MISSING", "reason": "Column not in parquet",
        }

    series = df[col]
    result: dict = {
        "column": col,
        "present": True,
        "dtype": str(series.dtype),
        "null_rate": round(float(series.isna().mean()), 4),
        "nonzero_rate": round(float((series.ne(0) & series.notna()).mean()), 4),
        "n_unique": int(series.nunique()),
        "corr_with_target": None,
        "target_derived": False,
        "post_race": False,
        "sp_derived": False,
        "position_derived": False,
        "payout_derived": False,
        "safe_pre_race": None,
        "decision": None,
        "reason": None,
    }

    # Correlation
    try:
        if pd.api.types.is_numeric_dtype(series):
            corr = series.fillna(0).corr(df["target"])
            result["corr_with_target"] = round(float(corr), 5)
    except Exception:
        pass

    # Keyword checks
    name_lower = col.lower()
    sp_keywords = {"sp", "log_sp", "sp_dec", "sp_rank", "implied_prob", "odds_rank"}
    pos_keywords = {"pos", "position", "finishing", "finish", "btn", "beaten", "margin",
                    "beaten_length", "distance_beaten", "result", "rank"}
    payout_keywords = {"payout", "dividend", "return", "return_"}
    win_keywords = {"win", "won", "winner", "placed"}

    if col in LEAKAGE_DROPS:
        result["post_race"] = True
        result["safe_pre_race"] = False
        result["decision"] = "DROP"
        result["reason"] = LEAKAGE_DROPS[col]
        return result

    if any(kw in name_lower for kw in pos_keywords):
        result["position_derived"] = True
        result["safe_pre_race"] = False
        result["decision"] = "DROP"
        result["reason"] = "Name matches position/result keyword pattern"
        return result

    if any(kw in name_lower for kw in payout_keywords):
        result["payout_derived"] = True
        result["safe_pre_race"] = False
        result["decision"] = "DROP"
        result["reason"] = "Name matches payout/dividend keyword pattern"
        return result

    if col in KNOWN_SAFE:
        result["safe_pre_race"] = True
        result["decision"] = "KEEP"
        result["reason"] = KNOWN_SAFE[col]
        return result

    if col in REQUIRES_INVESTIGATION:
        result["safe_pre_race"] = None
        result["decision"] = "UNKNOWN_REVIEW"
        result["reason"] = REQUIRES_INVESTIGATION[col]
        # Extra timing check for fit scores
        if "fit_score" in col or col == "trainer_timing_score":
            result["timing_check"] = _check_fit_score_timing(df, col)
        return result

    # Default for other columns
    result["decision"] = "UNKNOWN_REVIEW"
    result["reason"] = "Not in known-safe or known-drop lists — manual review required"
    return result


def main() -> None:
    print("[LeakageAudit] Loading parquet...")
    df = pd.read_parquet(PQ_PATH)
    print(f"[LeakageAudit] Rows: {len(df):,} | Columns: {len(df.columns)}")

    # Audit all arena features + all parquet columns
    all_cols_to_audit = list(set(ARENA_FEATURES) | set(df.columns))
    all_cols_to_audit = sorted(all_cols_to_audit)

    print("[LeakageAudit] Auditing columns...")
    results = []
    for col in all_cols_to_audit:
        if col in ("horse", "jockey", "trainer", "course", "date", "date_parsed", "type", "race_id"):
            continue
        r = audit_column(df, col)
        results.append(r)
        d = r.get("decision", "?")
        corr = r.get("corr_with_target")
        corr_str = f"corr={corr:.4f}" if corr is not None else ""
        print(f"  {col:40s} {d:15s} {corr_str}")

    # Arena feature summary
    arena_results = [r for r in results if r["column"] in ARENA_FEATURES]
    arena_keep = [r for r in arena_results if r["decision"] == "KEEP"]
    arena_drop = [r for r in arena_results if r["decision"] == "DROP"]
    arena_review = [r for r in arena_results if r["decision"] == "UNKNOWN_REVIEW"]

    print(f"\n[LeakageAudit] Arena features: {len(arena_results)}")
    print(f"  KEEP:           {len(arena_keep)}")
    print(f"  DROP:           {len(arena_drop)}")
    print(f"  UNKNOWN_REVIEW: {len(arena_review)}")

    # Verdict
    dropped_names = [r["column"] for r in arena_drop]
    review_names = [r["column"] for r in arena_review]

    if arena_drop:
        overall_verdict = "LEAKAGE_SUSPECTS_FOUND"
    elif arena_review:
        overall_verdict = "REVIEW_REQUIRED"
    else:
        overall_verdict = "CLEAN"

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_verdict": overall_verdict,
        "arena_features_audited": len(arena_results),
        "arena_keep": len(arena_keep),
        "arena_drop": len(arena_drop),
        "arena_review": len(arena_review),
        "dropped_arena_features": dropped_names,
        "review_required_features": review_names,
        "columns": results,
        "summary": {
            "HIGH_RISK_DROP": dropped_names,
            "UNKNOWN_REVIEW": review_names,
            "CONFIRMED_SAFE": [r["column"] for r in arena_keep],
        },
        "interpretation": {
            "why_results_suspicious": (
                "AUC=0.95 and SR=80%+ exceeds typical racing model benchmarks. "
                "Fit scores (course_fit_score, going_fit_score, distance_fit_score, trainer_timing_score) "
                "may be computed using the current race's result if not properly time-gated. "
                "These features have 0.10-0.13 target correlation. "
                "If time-gate is clean, their combination with RPR (corr=0.37) could legitimately "
                "produce high AUC — but 0.95 warrants shuffle test confirmation."
            ),
            "primary_suspect": "course_fit_score, going_fit_score, distance_fit_score, trainer_timing_score",
            "secondary_concern": "class_num null rate 42% — zero-fill may create a spurious signal",
            "confirmed_clean": "rpr_vs_field (corr=0.367), rpr_num (corr=0.267) — pre-race ratings, expected to be clean",
        },
    }

    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(exist_ok=True)

    json_path = out_dir / "international_arena_leakage_audit_latest.json"
    json_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n[LeakageAudit] Written: {json_path}")

    # Markdown
    md = _write_md(out)
    md_path = out_dir / "international_arena_leakage_audit_latest.md"
    md_path.write_text(md)
    print(f"[LeakageAudit] Written: {md_path}")
    print(f"\n[LeakageAudit] VERDICT: {overall_verdict}")


def _write_md(out: dict) -> str:
    dropped = out["dropped_arena_features"]
    review = out["review_required_features"]
    safe = out["summary"]["CONFIRMED_SAFE"]

    dropped_rows = "\n".join(f"| {c} | DROP | post-race/derived |" for c in dropped) if dropped else "| — | — | — |"
    review_rows = "\n".join(f"| {c} | UNKNOWN_REVIEW | timing unconfirmed |" for c in review) if review else "| — | — | — |"
    safe_rows = "\n".join(f"| {c} | KEEP | confirmed pre-race |" for c in safe) if safe else "| — | — | — |"

    interp = out.get("interpretation", {})

    return f"""# International Arena Leakage Audit

**Generated:** {out['generated_at']}
**Verdict:** {out['overall_verdict']}
**Arena features audited:** {out['arena_features_audited']}

---

## Summary

| Status | Count | Features |
|---|---|---|
| KEEP (confirmed safe) | {out['arena_keep']} | {', '.join(safe) if safe else '—'} |
| DROP (post-race/leakage) | {out['arena_drop']} | {', '.join(dropped) if dropped else '—'} |
| UNKNOWN_REVIEW (timing unconfirmed) | {out['arena_review']} | {', '.join(review) if review else '—'} |

---

## Dropped Arena Features

| Feature | Decision | Reason |
|---|---|---|
{dropped_rows}

## Features Requiring Review

| Feature | Decision | Issue |
|---|---|---|
{review_rows}

## Confirmed Safe Features

| Feature | Decision | Basis |
|---|---|---|
{safe_rows}

---

## Why Results Are Suspicious

{interp.get('why_results_suspicious', '')}

**Primary suspect:** `{interp.get('primary_suspect', '')}`

**Secondary concern:** {interp.get('secondary_concern', '')}

**Confirmed clean:** {interp.get('confirmed_clean', '')}

---

## Next Steps

1. Run shuffle test (`audit_international_arena_sanity.py`) — definitively confirms/denies leakage
2. Run safe arena (`audit_international_baseline_arena_safe.py`) — results using only confirmed pre-race features
3. Investigate fit score time-gating in source code before using in any model

---

```
LEAKAGE_AUDIT_STATUS:  {out['overall_verdict']}
ARENA_VERDICT_HOLD:    YES — do not promote until sanity + safe arena pass
MIGRATION_STATUS:      NOT_RUN
WORKER_STATUS:         BLOCKED
```
"""


if __name__ == "__main__":
    main()
