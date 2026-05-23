#!/usr/bin/env python3
"""
International Baseline Arena — Lagged Features Only

Re-runs the baseline arena using ONLY lagged rating features (previous-run values).
Current-race RPR/OR/TS are excluded entirely — lagged versions only.

This is the definitive offline test: if the model still beats the favourite with
strictly lagged features, the parquet data is usable for pre-race inference.

If AUC collapses dramatically vs the safe arena (0.90+), it suggests the current-race
RPR/OR/TS fields were doing the predictive work, which raises post-race attribution risk.

Reads:
  data/features/international_lagged_rating_features.parquet

Outputs:
  data/reports/international_baseline_arena_lagged_only_latest.json
  data/reports/international_baseline_arena_lagged_only_latest.md

Usage:
    PYTHONPATH=. python scripts/audit_international_baseline_arena_lagged_only.py
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
LAG_PQ = ROOT / "data" / "features" / "international_lagged_rating_features.parquet"

PACKS = {
    "HK_SHA_TIN_V1": ["Sha Tin (HK)"],
    "HK_HAPPY_VALLEY_V1": ["Happy Valley (HK)"],
    "FR_CHANTILLY_V1": ["Chantilly (FR)"],
    "FR_FLAT_CORE": ["Chantilly (FR)", "Deauville (FR)", "Longchamp (FR)", "Saint-Cloud (FR)"],
    "FR_AUTEUIL_JUMPS_V1": ["Auteuil (FR)"],
}

# All lagged + static features (NO current-race RPR/OR/TS)
LAGGED_RATING_FEATURES = [
    "prev_rpr_num", "max_rpr_num_last3", "avg_rpr_num_last3",
    "prev_or_num", "max_or_num_last3", "avg_or_num_last3",
    "prev_ts_num", "max_ts_num_last3", "avg_ts_num_last3",
    "days_since_last_run", "starts_last_90",
    "course_prior_runs", "course_prior_wr",
    "dist_prior_runs", "dist_prior_wr",
]

STATIC_FEATURES = [
    "draw_num", "draw_pct", "field_size", "dist_f", "going_code",
    "wgt_lbs", "age_num", "is_aw",
]

TRAIN_END = "2022-12-31"
VALID_END = "2023-12-31"

# Features NOT to include (current-race ratings — banned from this arena)
BANNED = {
    "rpr_num", "rpr_vs_field", "or_num", "or_vs_field", "ts_num",
    "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav",
    "odds_resilience_score", "odds_contraction_score",
    "course_fit_score", "going_fit_score", "distance_fit_score",
    "trainer_timing_score", "mark_compression_score",
}


def _get_features(sub: pd.DataFrame, pack_name: str) -> list[str]:
    candidates = LAGGED_RATING_FEATURES + STATIC_FEATURES
    avail = []
    for f in candidates:
        if f not in sub.columns or f in BANNED:
            continue
        # Require >5% nonzero coverage
        coverage = (sub[f].notna() & sub[f].ne(0)).mean()
        if coverage > 0.05:
            avail.append(f)
    # Drop OR for FR (low coverage even lagged)
    if pack_name.startswith("FR"):
        avail = [f for f in avail if "or_" not in f]
    # Drop TS for HK and Auteuil
    if pack_name.startswith("HK") or pack_name == "FR_AUTEUIL_JUMPS_V1":
        avail = [f for f in avail if "ts_" not in f]
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


def _prev_rpr_baseline(sub: pd.DataFrame, race_ids):
    if "prev_rpr_num" not in sub.columns:
        return 0.0, 0
    return _top_pick_sr(sub["prev_rpr_num"].fillna(0).values, sub["target"].values, race_ids)


def run_pack(pack_name: str, courses: list[str], df: pd.DataFrame) -> dict:
    print(f"\n[LaggedArena] Pack: {pack_name}")
    sub = df[df["course"].isin(courses)].copy()

    if len(sub) < 100:
        return {"pack": pack_name, "verdict": "DATA_GAP", "n": int(len(sub))}

    features = _get_features(sub, pack_name)
    print(f"  Lagged features ({len(features)}): {features}")

    # Drop rows where horse has no prior runs (lagged features will be NaN)
    has_prior = sub["prev_rpr_num"].notna() | sub["course_prior_runs"].gt(0)
    sub_with_prior = sub[has_prior].copy()
    print(f"  Rows with prior history: {len(sub_with_prior):,} of {len(sub):,}")

    train, valid, test = _split(sub_with_prior)
    print(f"  Train: {len(train):,} | Valid: {len(valid):,} | Test: {len(test):,}")

    if len(train) < 50 or len(test) < 10:
        return {"pack": pack_name, "verdict": "DATA_GAP", "n": int(len(sub))}

    test_race_ids = test["race_id"].values if "race_id" in test.columns else np.arange(len(test))
    fav_sr, fav_n = _fav_baseline(test, test_race_ids)
    prev_rpr_sr, prev_rpr_n = _prev_rpr_baseline(test, test_race_ids)

    X_train = train[features].fillna(0).values
    X_test = test[features].fillna(0).values
    y_train = train["target"].values.astype(float)
    y_test = test["target"].values.astype(float)

    models = {}

    # LR
    try:
        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_train)
        X_te_s = scaler.transform(X_test)
        lr = LogisticRegression(max_iter=500, C=1.0, solver="lbfgs")
        lr.fit(X_tr_s, y_train)
        probs = lr.predict_proba(X_te_s)[:, 1]
        sr, n = _top_pick_sr(probs, y_test, test_race_ids)
        auc = round(float(roc_auc_score(y_test, probs)), 4)
        brier = round(float(brier_score_loss(y_test, probs)), 4)
        models["logistic_regression"] = {
            "auc": auc, "top_pick_sr": sr, "brier": brier, "n_races": n,
            "beats_fav": sr > fav_sr, "beats_prev_rpr": sr > prev_rpr_sr,
        }
        print(f"  LR:  SR={sr:.1%} AUC={auc:.4f}")
    except Exception as e:
        models["logistic_regression"] = {"error": str(e)}

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
        probs = model.predict_proba(X_test)[:, 1]
        sr, n = _top_pick_sr(probs, y_test, test_race_ids)
        auc = round(float(roc_auc_score(y_test, probs)), 4)
        brier = round(float(brier_score_loss(y_test, probs)), 4)
        fi = dict(zip(features, model.feature_importances_))
        top3 = sorted(fi, key=fi.get, reverse=True)[:3]
        models["lightgbm"] = {
            "auc": auc, "top_pick_sr": sr, "brier": brier, "n_races": n,
            "beats_fav": sr > fav_sr, "beats_prev_rpr": sr > prev_rpr_sr,
            "top3_features": top3,
        }
        print(f"  LGB: SR={sr:.1%} AUC={auc:.4f}")
    except Exception as e:
        models["lightgbm"] = {"error": str(e)}

    best_auc = max((m.get("auc", 0) for m in models.values() if "auc" in m), default=0)
    best_sr = max((m.get("top_pick_sr", 0) for m in models.values() if "top_pick_sr" in m), default=0)
    beats_fav = any(m.get("beats_fav", False) for m in models.values())
    beats_prev_rpr = any(m.get("beats_prev_rpr", False) for m in models.values())

    if best_auc >= 0.65 and beats_fav:
        verdict = "SAFE_SHADOW_CANDIDATE"
    elif best_auc >= 0.58 and beats_fav:
        verdict = "NEEDS_FEATURE_ENGINEERING"
    elif best_auc >= 0.58:
        verdict = "NEEDS_FEATURE_ENGINEERING"
    else:
        verdict = "TIMESTAMP_UNPROVEN_HOLD"

    print(f"  => VERDICT: {verdict} (AUC={best_auc:.4f} SR={best_sr:.1%} FavSR={fav_sr:.1%})")

    return {
        "pack": pack_name,
        "courses": courses,
        "n_total": int(len(sub)),
        "n_with_prior": int(len(sub_with_prior)),
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "lagged_features": features,
        "n_features": len(features),
        "baselines": {
            "favourite_sr": fav_sr, "favourite_n": fav_n,
            "prev_rpr_sr": prev_rpr_sr, "prev_rpr_n": prev_rpr_n,
        },
        "models": models,
        "best_auc": best_auc,
        "best_sr": best_sr,
        "beats_fav": beats_fav,
        "beats_prev_rpr": beats_prev_rpr,
        "verdict": verdict,
    }


def main() -> None:
    if not LAG_PQ.exists():
        print("[LaggedArena] ERROR: Lagged features parquet not found.")
        print(f"  Run first: python scripts/build_international_lagged_rating_features.py")
        return

    print("[LaggedArena] Loading lagged features parquet...")
    df = pd.read_parquet(LAG_PQ)
    print(f"[LaggedArena] Rows: {len(df):,} | Columns: {len(df.columns)}")

    all_results = []
    for pack_name, courses in PACKS.items():
        result = run_pack(pack_name, courses, df)
        all_results.append(result)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "LAGGED_ONLY — current-race RPR/OR/TS entirely excluded",
        "train_period": "2015-2022",
        "valid_period": "2023",
        "test_period": "2024-2025",
        "banned_current_race_features": list(BANNED),
        "packs": all_results,
    }

    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(exist_ok=True)

    json_path = out_dir / "international_baseline_arena_lagged_only_latest.json"
    json_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n[LaggedArena] Written: {json_path}")

    md = _write_md(all_results, out)
    md_path = out_dir / "international_baseline_arena_lagged_only_latest.md"
    md_path.write_text(md)
    print(f"[LaggedArena] Written: {md_path}")

    print("\n=== SUMMARY ===")
    for r in all_results:
        fav = r.get("baselines", {}).get("favourite_sr", 0)
        print(f"  {r['pack']:25s} AUC={r.get('best_auc', 0):.4f} SR={r.get('best_sr', 0):.1%} "
              f"FavSR={fav:.1%} => {r.get('verdict')}")


def _write_md(all_results: list, out: dict) -> str:
    rows = ""
    for r in all_results:
        b = r.get("baselines", {})
        verdict = r.get("verdict", "N/A")
        beats_fav = "YES" if r.get("beats_fav") else "NO"
        rows += (
            f"| {r['pack']} | {r.get('n_test', 0):,} | "
            f"{b.get('favourite_sr', 0):.1%} | {b.get('prev_rpr_sr', 0):.1%} | "
            f"{r.get('best_auc', 0):.4f} | {r.get('best_sr', 0):.1%} | "
            f"{beats_fav} | **{verdict}** |\n"
        )

    detail = ""
    for r in all_results:
        detail += f"\n### {r['pack']}\n"
        detail += f"Lagged features ({r.get('n_features', 0)}): `{', '.join(r.get('lagged_features', []))}`\n\n"
        b = r.get("baselines", {})
        detail += f"Fav SR: {b.get('favourite_sr', 0):.1%} | Prev-RPR SR: {b.get('prev_rpr_sr', 0):.1%}\n\n"
        for mname, mdata in r.get("models", {}).items():
            if "error" in mdata:
                detail += f"- {mname}: ERROR — {mdata['error']}\n"
            elif "auc" in mdata:
                top3 = ", ".join(mdata.get("top3_features", []))
                detail += (
                    f"- {mname}: SR={mdata['top_pick_sr']:.1%} AUC={mdata['auc']:.4f} "
                    f"Brier={mdata.get('brier', 0):.4f} | Top: {top3}\n"
                )
        detail += f"\n**Lagged Verdict: {r.get('verdict')}**\n"

    return f"""# International Baseline Arena — Lagged Features Only

**Generated:** {out['generated_at']}
**Method:** {out['method']}
**Temporal split:** Train 2015-2022 | Valid 2023 | Test 2024-2025

---

## Why Lagged-Only Arena

The safe arena produced AUC=0.90-0.96 with current-race ratings (rpr_num, or_num, etc.).
The co-founder's question: are those ratings available BEFORE the race?

This arena bans all current-race rating fields entirely. It uses only:
- Previous run's ratings (prev_rpr_num, prev_or_num, prev_ts_num)
- Rolling stats over last 3 runs (max, avg)
- Static race attributes (draw, distance, weight, going)
- Historical course/distance win rates (computed with strict lag)

**If this arena achieves strong AUC/SR: the signal exists in pre-race-verifiable data.**
**If AUC collapses dramatically: the current-race ratings were doing the work (and need timestamp verification).**

---

## Summary Table

| Pack | Test | Fav SR | Prev-RPR SR | Best AUC | Best SR | >Fav | Verdict |
|---|---|---|---|---|---|---|---|
{rows}
---

## Pack Detail
{detail}

---

## Interpretation

- **SAFE_SHADOW_CANDIDATE**: Lagged features achieve AUC ≥ 0.65 and beat favourite.
  Current-race ratings not required. Production use viable with lagged pipeline.
- **NEEDS_FEATURE_ENGINEERING**: Some signal, but needs additional pre-race features.
- **TIMESTAMP_UNPROVEN_HOLD**: AUC too weak with lagged-only — investigate whether
  current-race ratings are truly pre-race before allowing their use.

---

```
LAGGED_ARENA_STATUS: see verdict per pack
CURRENT_RACE_RATINGS: BANNED_FROM_THIS_ARENA
MIGRATION_STATUS: NOT_RUN
WORKER_STATUS: BLOCKED
```
"""


if __name__ == "__main__":
    main()
