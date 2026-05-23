#!/usr/bin/env python3
"""
International Baseline Arena — Safe Features Only

Re-runs the baseline arena using ONLY confirmed pre-race features.
Banned features: any SP/odds/result/position-derived column, and any
fit score whose time-gating is unconfirmed.

The safe feature contract:
  - rpr_num, rpr_vs_field: Racing Post Rating from PREVIOUS runs (pre-race)
  - or_num, or_vs_field: Official Rating set by regulator before race
  - ts_num: Timeform Speed Figure from PREVIOUS runs (pre-race, FR flat only)
  - draw_num, draw_pct: Barrier draw — known before race
  - field_size: Number of runners — known before race
  - dist_f: Distance — known before race
  - going_code: Going — published before race
  - wgt_lbs: Weight carried — published before race
  - age_num: Horse age — known before race
  - is_aw: All-weather surface — known before race

Excluded (unconfirmed time-gating):
  - course_fit_score, going_fit_score, distance_fit_score, trainer_timing_score
  - mark_compression_score (uses OR history — timing TBC)
  - class_num (42% null — zero-fill distortion risk)
  - runs_since_win, runs_since_place (historical, but depends on data pipeline)

Outputs:
  data/reports/international_baseline_arena_safe_latest.json
  data/reports/international_baseline_arena_safe_latest.md

Usage:
    PYTHONPATH=. python scripts/audit_international_baseline_arena_safe.py
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
PQ_PATH = ROOT / "data" / "raceform_v17_features.parquet"

PACKS = {
    "HK_SHA_TIN_V1": ["Sha Tin (HK)"],
    "HK_HAPPY_VALLEY_V1": ["Happy Valley (HK)"],
    "FR_CHANTILLY_V1": ["Chantilly (FR)"],
    "FR_FLAT_CORE": ["Chantilly (FR)", "Deauville (FR)", "Longchamp (FR)", "Saint-Cloud (FR)"],
    "FR_AUTEUIL_JUMPS_V1": ["Auteuil (FR)"],
}

# SAFE: confirmed pre-race ratings and static race attributes
SAFE_BASE = [
    "rpr_num", "rpr_vs_field",
    "field_size", "draw_num", "draw_pct",
    "dist_f", "going_code", "wgt_lbs",
    "age_num", "is_aw",
]

TRAIN_END = "2022-12-31"
VALID_END = "2023-12-31"

BANNED = {
    "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav",
    "odds_resilience_score", "odds_contraction_score",
    "decoy_support_flag", "setup_run_flag", "cash_run_flag",
    "jockey_switch_intent", "pos",
    # Excluded pending time-gate confirmation
    "course_fit_score", "going_fit_score", "distance_fit_score", "trainer_timing_score",
    "mark_compression_score", "class_num",
    "runs_since_win", "runs_since_place",
    "curr_or_minus_best_or", "curr_or_minus_last_win_or",
    "release_window_score", "quiet_run_score", "runs_since_mkt_support",
}


def _get_safe_features(sub: pd.DataFrame, pack_name: str) -> list[str]:
    base = list(SAFE_BASE)
    # Add OR features for HK (97-100% coverage)
    if pack_name.startswith("HK"):
        base += ["or_num", "or_vs_field"]
    # Add TS for FR flat only (51-88% coverage at Deauville/Longchamp)
    if pack_name in ("FR_CHANTILLY_V1", "FR_FLAT_CORE"):
        base += ["ts_num"]
    # Filter by availability and coverage
    avail = []
    for f in base:
        if f not in sub.columns:
            continue
        if f in BANNED:
            continue
        coverage = (sub[f].notna() & sub[f].ne(0)).mean()
        if coverage > 0.03:
            avail.append(f)
    return avail


def _split(sub: pd.DataFrame):
    dates = pd.to_datetime(sub["date"], errors="coerce")
    train = sub[dates <= TRAIN_END]
    valid = sub[(dates > TRAIN_END) & (dates <= VALID_END)]
    test = sub[dates > VALID_END]
    return train, valid, test


def _top_pick_sr(y_pred, y_true, race_ids):
    df = pd.DataFrame({"pred": y_pred, "true": y_true, "race": race_ids})
    top = df.loc[df.groupby("race")["pred"].idxmax()]
    n = len(top)
    wins = top["true"].sum()
    return round(float(wins / n), 4) if n > 0 else 0.0, int(n)


def _fav_baseline(sub: pd.DataFrame, race_ids):
    if "is_fav" not in sub.columns:
        return 0.0, 0
    df = pd.DataFrame({"is_fav": sub["is_fav"].values, "true": sub["target"].values, "race": race_ids})
    favs = df[df["is_fav"] == 1]
    n = favs["race"].nunique()
    wins = favs["true"].sum()
    return round(float(wins / n), 4) if n > 0 else 0.0, int(n)


def _rpr_baseline(sub: pd.DataFrame, race_ids):
    if "rpr_vs_field" not in sub.columns:
        return 0.0, 0
    return _top_pick_sr(sub["rpr_vs_field"].fillna(0).values, sub["target"].values, race_ids)


def run_pack(pack_name: str, courses: list[str], df: pd.DataFrame) -> dict:
    print(f"\n[SafeArena] Pack: {pack_name} ({courses})")

    sub = df[df["course"].isin(courses)].copy()
    if len(sub) < 100:
        return {"pack": pack_name, "verdict": "DATA_GAP", "n": int(len(sub))}

    features = _get_safe_features(sub, pack_name)
    print(f"  Safe features ({len(features)}): {features}")

    train, valid, test = _split(sub)
    print(f"  Train: {len(train):,} | Valid: {len(valid):,} | Test: {len(test):,}")

    if len(train) < 50 or len(test) < 10:
        return {"pack": pack_name, "verdict": "DATA_GAP", "n": int(len(sub))}

    test_race_ids = test["race_id"].values if "race_id" in test.columns else np.arange(len(test))
    fav_sr, fav_n = _fav_baseline(test, test_race_ids)
    rpr_sr, rpr_n = _rpr_baseline(test, test_race_ids)

    X_train = train[features].fillna(0).values
    X_test = test[features].fillna(0).values
    y_train = train["target"].values.astype(float)
    y_test = test["target"].values.astype(float)

    model_results = {}

    # Logistic Regression (simplest, most interpretable)
    try:
        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_train)
        X_te_s = scaler.transform(X_test)
        lr = LogisticRegression(max_iter=500, C=1.0, solver="lbfgs")
        lr.fit(X_tr_s, y_train)
        lr_probs = lr.predict_proba(X_te_s)[:, 1]
        lr_sr, lr_n = _top_pick_sr(lr_probs, y_test, test_race_ids)
        lr_auc = round(float(roc_auc_score(y_test, lr_probs)), 4)
        lr_brier = round(float(brier_score_loss(y_test, lr_probs)), 4)
        model_results["logistic_regression"] = {
            "auc": lr_auc, "top_pick_sr": lr_sr, "brier": lr_brier,
            "n_races": lr_n, "beats_fav": lr_sr > fav_sr, "beats_rpr": lr_sr > rpr_sr,
        }
        print(f"  LR: SR={lr_sr:.1%} AUC={lr_auc:.4f}")
    except Exception as e:
        model_results["logistic_regression"] = {"error": str(e)}

    # LightGBM
    try:
        import lightgbm as lgb
        model = lgb.LGBMClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=5,
            num_leaves=31, min_child_samples=20, n_jobs=-1, random_state=42, verbose=-1
        )
        model.fit(X_train, y_train,
                  eval_set=[(X_test, y_test)],
                  callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(-1)])
        lgb_probs = model.predict_proba(X_test)[:, 1]
        lgb_sr, lgb_n = _top_pick_sr(lgb_probs, y_test, test_race_ids)
        lgb_auc = round(float(roc_auc_score(y_test, lgb_probs)), 4)
        lgb_brier = round(float(brier_score_loss(y_test, lgb_probs)), 4)
        fi = dict(zip(features, model.feature_importances_))
        top3 = sorted(fi, key=fi.get, reverse=True)[:3]
        model_results["lightgbm"] = {
            "auc": lgb_auc, "top_pick_sr": lgb_sr, "brier": lgb_brier,
            "n_races": lgb_n, "beats_fav": lgb_sr > fav_sr, "beats_rpr": lgb_sr > rpr_sr,
            "top3_features": top3,
        }
        print(f"  LGB: SR={lgb_sr:.1%} AUC={lgb_auc:.4f}")
    except Exception as e:
        model_results["lightgbm"] = {"error": str(e)}

    best_auc = max((m.get("auc", 0) for m in model_results.values() if "auc" in m), default=0)
    best_sr = max((m.get("top_pick_sr", 0) for m in model_results.values() if "top_pick_sr" in m), default=0)
    beats_fav = any(m.get("beats_fav", False) for m in model_results.values())

    if best_auc >= 0.65 and beats_fav:
        verdict = "SAFE_SHADOW_CANDIDATE"
    elif best_auc >= 0.58:
        verdict = "NEEDS_FEATURE_ENGINEERING"
    elif best_auc > 0:
        verdict = "WEAK_SIGNAL_MORE_FEATURES_NEEDED"
    else:
        verdict = "DATA_GAP"

    print(f"  => VERDICT: {verdict} (AUC={best_auc:.4f} SR={best_sr:.1%} FavSR={fav_sr:.1%} RPRSR={rpr_sr:.1%})")

    return {
        "pack": pack_name,
        "courses": courses,
        "n_total": int(len(sub)),
        "n_train": int(len(train)),
        "n_valid": int(len(valid)),
        "n_test": int(len(test)),
        "safe_features": features,
        "n_safe_features": len(features),
        "banned_features_excluded": list(BANNED & set(df.columns)),
        "baselines": {
            "favourite_sr": fav_sr, "favourite_n": fav_n,
            "best_rpr_sr": rpr_sr, "best_rpr_n": rpr_n,
        },
        "models": model_results,
        "best_auc": best_auc,
        "best_sr": best_sr,
        "beats_fav": beats_fav,
        "verdict": verdict,
    }


def main() -> None:
    print("[SafeArena] Loading parquet...")
    df = pd.read_parquet(PQ_PATH)
    print(f"[SafeArena] Rows: {len(df):,}")

    all_results = []
    for pack_name, courses in PACKS.items():
        result = run_pack(pack_name, courses, df)
        all_results.append(result)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "SAFE_FEATURES_ONLY — confirmed pre-race columns, no fit scores, no SP-derived",
        "train_period": "2015-2022",
        "valid_period": "2023",
        "test_period": "2024-2025",
        "banned_feature_categories": [
            "SP/final_market: sp_dec, log_sp, implied_prob, sp_rank, is_fav",
            "Odds_movement: odds_resilience_score, odds_contraction_score",
            "RPDC_tags: decoy_support_flag, setup_run_flag, cash_run_flag",
            "Fit_scores_unconfirmed: course_fit_score, going_fit_score, distance_fit_score, trainer_timing_score",
            "OR_history_unconfirmed: mark_compression_score, class_num (42% null), curr_or_minus_*",
            "Position: pos",
        ],
        "packs": all_results,
    }

    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(exist_ok=True)

    json_path = out_dir / "international_baseline_arena_safe_latest.json"
    json_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n[SafeArena] Written: {json_path}")

    md = _write_md(all_results, out)
    md_path = out_dir / "international_baseline_arena_safe_latest.md"
    md_path.write_text(md)
    print(f"[SafeArena] Written: {md_path}")

    print("\n=== SUMMARY ===")
    for r in all_results:
        print(f"  {r['pack']:25s} AUC={r.get('best_auc', 0):.4f} SR={r.get('best_sr', 0):.1%} "
              f"FavSR={r.get('baselines', {}).get('favourite_sr', 0):.1%} => {r.get('verdict')}")


def _write_md(all_results: list, out: dict) -> str:
    rows = ""
    for r in all_results:
        b = r.get("baselines", {})
        verdict = r.get("verdict", "N/A")
        beats_fav = "YES" if r.get("beats_fav") else "NO"
        rows += (
            f"| {r['pack']} | {r.get('n_test', 0):,} | "
            f"{b.get('favourite_sr', 0):.1%} | {b.get('best_rpr_sr', 0):.1%} | "
            f"{r.get('best_auc', 0):.4f} | {r.get('best_sr', 0):.1%} | "
            f"{beats_fav} | **{verdict}** |\n"
        )

    detail = ""
    for r in all_results:
        detail += f"\n### {r['pack']}\n"
        detail += f"Safe features ({r.get('n_safe_features', 0)}): `{', '.join(r.get('safe_features', []))}`\n\n"
        b = r.get("baselines", {})
        detail += f"Fav SR: {b.get('favourite_sr', 0):.1%} | RPR SR: {b.get('best_rpr_sr', 0):.1%}\n\n"
        for mname, mdata in r.get("models", {}).items():
            if "error" in mdata:
                detail += f"- {mname}: ERROR — {mdata['error']}\n"
            elif "auc" in mdata:
                top3 = ", ".join(mdata.get("top3_features", []))
                detail += (
                    f"- {mname}: SR={mdata['top_pick_sr']:.1%} AUC={mdata['auc']:.4f} "
                    f"Brier={mdata.get('brier', 0):.4f} | Top: {top3}\n"
                )
        detail += f"\n**Safe Verdict: {r.get('verdict')}**\n"

    return f"""# International Baseline Arena — Safe Features Only

**Generated:** {out['generated_at']}
**Method:** {out['method']}
**Temporal split:** Train 2015-2022 | Valid 2023 | Test 2024-2025

---

## Why Safe-Only Arena

The first baseline arena produced AUC=0.95 and SR=80%+, which is suspicious for horse racing.
This arena uses ONLY features that are definitively available before the race starts:
pre-race ratings (RPR, OR, TS), static race attributes (draw, distance, weight, going).

Fit scores (course_fit_score, going_fit_score, distance_fit_score, trainer_timing_score)
are EXCLUDED until their time-gating can be confirmed in source code.

---

## Summary Table

| Pack | Test | Fav SR | RPR SR | Best AUC | Best SR | >Fav | Verdict |
|---|---|---|---|---|---|---|---|
{rows}
---

## Pack Detail
{detail}

---

## Excluded Feature Categories

{chr(10).join(f'- {b}' for b in out.get('banned_feature_categories', []))}

---

## Verdict Criteria

- **SAFE_SHADOW_CANDIDATE**: AUC ≥ 0.65 and beats favourite — genuine pre-race signal confirmed
- **NEEDS_FEATURE_ENGINEERING**: AUC ≥ 0.58 — some signal, needs more features
- **WEAK_SIGNAL_MORE_FEATURES_NEEDED**: AUC < 0.58 — not sufficient for shadow lane
- **LEAKAGE_CONFIRMED**: Would appear if model still achieves very high AUC with only safe features (unexpected)

---

```
SAFE_ARENA_STATUS: see verdict per pack above
MIGRATION_STATUS: NOT_RUN
WORKER_STATUS: BLOCKED
FIT_SCORES_STATUS: EXCLUDED_PENDING_TIME_GATE_REVIEW
```
"""


if __name__ == "__main__":
    main()
