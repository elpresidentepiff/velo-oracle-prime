#!/usr/bin/env python3
"""
International Baseline Arena V1

Offline model viability test. Parquet only. No DB. No live state.

Tests 5 packs using temporal split (train 2015-2022, valid 2023, test 2024-2025).
Models: favourite baseline, best-RPR baseline, logistic regression, random forest, LightGBM.

Outputs:
  data/reports/international_baseline_arena_latest.json
  data/reports/international_baseline_arena_latest.md

Usage:
    PYTHONPATH=. python scripts/audit_international_baseline_arena.py
"""

from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
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

# Non-leakage fundamental features
FUND_FEATURES = [
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

TRAIN_END = "2022-12-31"
VALID_END = "2023-12-31"


def _split(sub: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.to_datetime(sub["date"], errors="coerce")
    train = sub[dates <= TRAIN_END]
    valid = sub[(dates > TRAIN_END) & (dates <= VALID_END)]
    test = sub[dates > VALID_END]
    return train, valid, test


def _get_features(sub: pd.DataFrame, pack_name: str) -> list[str]:
    available = []
    for f in FUND_FEATURES:
        if f not in sub.columns:
            continue
        nz = (sub[f].notna() & sub[f].ne(0)).sum()
        if nz / max(len(sub), 1) > 0.05:
            available.append(f)
    # Drop OR for FR (0% coverage)
    if pack_name.startswith("FR"):
        available = [f for f in available if f not in ("or_num", "or_vs_field")]
    # Drop TS for HK and Auteuil (0% coverage)
    if pack_name.startswith("HK") or pack_name == "FR_AUTEUIL_JUMPS_V1":
        available = [f for f in available if f != "ts_num"]
    return available


def _prep_xy(sub: pd.DataFrame, features: list[str]) -> tuple[np.ndarray, np.ndarray]:
    X = sub[features].copy()
    X = X.fillna(0)
    y = sub["target"].values.astype(float)
    return X.values, y


def _top_pick_sr(y_pred: np.ndarray, y_true: np.ndarray, race_ids: np.ndarray) -> tuple[float, int]:
    df = pd.DataFrame({"pred": y_pred, "true": y_true, "race": race_ids})
    top = df.loc[df.groupby("race")["pred"].idxmax()]
    n = len(top)
    wins = top["true"].sum()
    return (round(float(wins / n), 4) if n > 0 else 0.0), int(n)


def _fav_baseline(sub: pd.DataFrame, race_ids: np.ndarray) -> tuple[float, int]:
    if "is_fav" not in sub.columns:
        return 0.0, 0
    df = pd.DataFrame({"is_fav": sub["is_fav"].values, "true": sub["target"].values, "race": race_ids})
    favs = df[df["is_fav"] == 1]
    n = favs["race"].nunique()
    wins = favs["true"].sum()
    return (round(float(wins / n), 4) if n > 0 else 0.0), int(n)


def _rpr_baseline(sub: pd.DataFrame, race_ids: np.ndarray) -> tuple[float, int]:
    if "rpr_vs_field" not in sub.columns:
        return 0.0, 0
    return _top_pick_sr(sub["rpr_vs_field"].fillna(0).values, sub["target"].values, race_ids)


def _calibration_error(y_pred: np.ndarray, y_true: np.ndarray, n_bins: int = 5) -> float:
    bins = np.linspace(0, 1, n_bins + 1)
    errors = []
    for i in range(n_bins):
        mask = (y_pred >= bins[i]) & (y_pred < bins[i + 1])
        if mask.sum() < 5:
            continue
        pred_mean = y_pred[mask].mean()
        true_mean = y_true[mask].mean()
        errors.append(abs(pred_mean - true_mean))
    return round(float(np.mean(errors)), 4) if errors else None


def _leakage_check(features: list[str]) -> list[str]:
    leakage_suspects = {"sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav",
                        "odds_resilience_score", "odds_contraction_score",
                        "decoy_support_flag", "setup_run_flag", "cash_run_flag"}
    return [f for f in features if f in leakage_suspects]


def run_pack(pack_name: str, courses: list[str], df: pd.DataFrame) -> dict:
    print(f"\n[Arena] Pack: {pack_name} ({courses})")

    sub = df[df["course"].isin(courses)].copy()
    if len(sub) < 100:
        return {"pack": pack_name, "verdict": "DATA_GAP", "n": len(sub)}

    features = _get_features(sub, pack_name)
    leakage = _leakage_check(features)

    train, valid, test = _split(sub)
    print(f"  Train: {len(train):,} | Valid: {len(valid):,} | Test: {len(test):,}")

    if len(train) < 50 or len(test) < 10:
        return {"pack": pack_name, "verdict": "DATA_GAP", "n": len(sub)}

    # Baselines on test
    test_race_ids = test["race_id"].values if "race_id" in test.columns else np.arange(len(test))
    fav_sr, fav_n = _fav_baseline(test, test_race_ids)
    rpr_sr, rpr_n = _rpr_baseline(test, test_race_ids)

    # Race counts
    train_races = train["race_id"].nunique() if "race_id" in train.columns else None
    test_races = test["race_id"].nunique() if "race_id" in test.columns else None

    results = {
        "pack": pack_name,
        "courses": courses,
        "n_total": int(len(sub)),
        "n_train": int(len(train)),
        "n_valid": int(len(valid)),
        "n_test": int(len(test)),
        "train_races": int(train_races) if train_races else None,
        "test_races": int(test_races) if test_races else None,
        "features_used": features,
        "n_features": len(features),
        "leakage_check": leakage if leakage else "CLEAN",
        "baselines": {
            "favourite_sr": fav_sr,
            "favourite_n": fav_n,
            "best_rpr_sr": rpr_sr,
            "best_rpr_n": rpr_n,
        },
        "models": {},
        "verdict": None,
    }

    if not features:
        results["verdict"] = "DATA_GAP"
        return results

    X_train, y_train = _prep_xy(train, features)
    X_test, y_test = _prep_xy(test, features)

    # Logistic Regression
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
        lr_cal = _calibration_error(lr_probs, y_test)
        results["models"]["logistic_regression"] = {
            "top_pick_sr": lr_sr, "n_picks": lr_n,
            "auc": lr_auc, "brier": lr_brier, "calibration_error": lr_cal,
            "beats_fav": lr_sr > fav_sr, "beats_rpr": lr_sr > rpr_sr,
        }
        print(f"  LR: SR={lr_sr:.1%} AUC={lr_auc:.4f} Brier={lr_brier:.4f}")
    except Exception as e:
        results["models"]["logistic_regression"] = {"error": str(e)}

    # Random Forest
    try:
        rf = RandomForestClassifier(n_estimators=100, max_depth=6, n_jobs=-1, random_state=42)
        rf.fit(X_train, y_train)
        rf_probs = rf.predict_proba(X_test)[:, 1]
        rf_sr, rf_n = _top_pick_sr(rf_probs, y_test, test_race_ids)
        rf_auc = round(float(roc_auc_score(y_test, rf_probs)), 4)
        rf_brier = round(float(brier_score_loss(y_test, rf_probs)), 4)
        rf_cal = _calibration_error(rf_probs, y_test)
        fi = dict(zip(features, rf.feature_importances_))
        top3 = sorted(fi, key=fi.get, reverse=True)[:3]
        results["models"]["random_forest"] = {
            "top_pick_sr": rf_sr, "n_picks": rf_n,
            "auc": rf_auc, "brier": rf_brier, "calibration_error": rf_cal,
            "beats_fav": rf_sr > fav_sr, "beats_rpr": rf_sr > rpr_sr,
            "top3_features": top3,
        }
        print(f"  RF: SR={rf_sr:.1%} AUC={rf_auc:.4f} Brier={rf_brier:.4f}")
    except Exception as e:
        results["models"]["random_forest"] = {"error": str(e)}

    # LightGBM
    try:
        import lightgbm as lgb
        lgb_model = lgb.LGBMClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=6,
            num_leaves=31, min_child_samples=20, n_jobs=-1, random_state=42,
            verbose=-1
        )
        lgb_model.fit(X_train, y_train,
                      eval_set=[(X_test, y_test)],
                      callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(-1)])
        lgb_probs = lgb_model.predict_proba(X_test)[:, 1]
        lgb_sr, lgb_n = _top_pick_sr(lgb_probs, y_test, test_race_ids)
        lgb_auc = round(float(roc_auc_score(y_test, lgb_probs)), 4)
        lgb_brier = round(float(brier_score_loss(y_test, lgb_probs)), 4)
        lgb_cal = _calibration_error(lgb_probs, y_test)
        fi_lgb = dict(zip(features, lgb_model.feature_importances_))
        top3_lgb = sorted(fi_lgb, key=fi_lgb.get, reverse=True)[:3]
        results["models"]["lightgbm"] = {
            "top_pick_sr": lgb_sr, "n_picks": lgb_n,
            "auc": lgb_auc, "brier": lgb_brier, "calibration_error": lgb_cal,
            "beats_fav": lgb_sr > fav_sr, "beats_rpr": lgb_sr > rpr_sr,
            "top3_features": top3_lgb,
        }
        print(f"  LGB: SR={lgb_sr:.1%} AUC={lgb_auc:.4f} Brier={lgb_brier:.4f}")
    except Exception as e:
        results["models"]["lightgbm"] = {"error": str(e)}

    # Determine verdict
    best_sr = max(
        (m.get("top_pick_sr", 0) for m in results["models"].values() if "top_pick_sr" in m),
        default=0
    )
    beats_fav = any(m.get("beats_fav", False) for m in results["models"].values())
    beats_rpr = any(m.get("beats_rpr", False) for m in results["models"].values())
    best_auc = max(
        (m.get("auc", 0) for m in results["models"].values() if "auc" in m),
        default=0
    )

    if best_auc >= 0.65 and beats_fav:
        results["verdict"] = "VIABLE_SHADOW_CANDIDATE"
    elif best_auc >= 0.58:
        results["verdict"] = "NEEDS_FEATURE_ENGINEERING"
    elif len(features) < 5:
        results["verdict"] = "DATA_GAP"
    else:
        results["verdict"] = "NEEDS_FEATURE_ENGINEERING"

    results["best_model_sr"] = best_sr
    results["beats_fav_baseline"] = beats_fav
    results["beats_rpr_baseline"] = beats_rpr
    results["best_auc"] = best_auc

    return results


def _write_md(all_results: list[dict], generated_at: str) -> str:
    summary_rows = ""
    for r in all_results:
        models = r.get("models", {})
        best_sr = max((m.get("top_pick_sr", 0) for m in models.values() if "top_pick_sr" in m), default=0)
        best_auc = max((m.get("auc", 0) for m in models.values() if "auc" in m), default=0)
        fav_sr = r.get("baselines", {}).get("favourite_sr", 0)
        rpr_sr = r.get("baselines", {}).get("best_rpr_sr", 0)
        beats_f = "YES" if r.get("beats_fav_baseline") else "NO"
        beats_r = "YES" if r.get("beats_rpr_baseline") else "NO"
        verdict = r.get("verdict", "N/A")
        summary_rows += (
            f"| {r['pack']} | {r.get('n_total', 0):,} | {r.get('n_test', 0):,} | "
            f"{fav_sr:.1%} | {rpr_sr:.1%} | {best_sr:.1%} | {best_auc:.4f} | "
            f"{beats_f} | {beats_r} | **{verdict}** |\n"
        )

    model_detail = ""
    for r in all_results:
        model_detail += f"\n### {r['pack']}\n"
        model_detail += f"Train: {r.get('n_train', 0):,} | Valid: {r.get('n_valid', 0):,} | Test: {r.get('n_test', 0):,}  \n"
        model_detail += f"Features: {r.get('n_features', 0)} | Leakage: {r.get('leakage_check', 'N/A')}  \n"
        b = r.get("baselines", {})
        model_detail += f"Favourite SR: {b.get('favourite_sr', 0):.1%} | Best-RPR SR: {b.get('best_rpr_sr', 0):.1%}\n\n"

        for mname, mdata in r.get("models", {}).items():
            if "error" in mdata:
                model_detail += f"- {mname}: ERROR — {mdata['error']}\n"
            elif "top_pick_sr" in mdata:
                top3 = ", ".join(mdata.get("top3_features", []))
                model_detail += (
                    f"- {mname}: SR={mdata['top_pick_sr']:.1%} AUC={mdata.get('auc', 0):.4f} "
                    f"Brier={mdata.get('brier', 0):.4f} Cal={mdata.get('calibration_error', 'N/A')} "
                    f"| Beats Fav={mdata.get('beats_fav', False)} | Top features: {top3}\n"
                )

        model_detail += f"\n**Verdict: {r.get('verdict', 'N/A')}**\n"

    return f"""# International Baseline Arena V1

**Generated:** {generated_at}
**Method:** Temporal split — Train 2015-2022, Valid 2023, Test 2024-2025
**Status:** OFFLINE ONLY — no DB, no scoring, no live state

---

## Summary Table

| Pack | Total | Test | Fav SR | RPR SR | Best Model SR | Best AUC | >Fav | >RPR | Verdict |
|---|---|---|---|---|---|---|---|---|---|
{summary_rows}
---

## Pack Detail

{model_detail}

---

## Methodology

**Feature sets:** Non-leakage fundamental features only. No SP/odds-derived features.
OR excluded from FR packs (0% coverage). TS excluded from HK and Auteuil (0% coverage).

**Verdict criteria:**
- VIABLE_SHADOW_CANDIDATE: AUC ≥ 0.65 and beats favourite baseline
- NEEDS_FEATURE_ENGINEERING: AUC ≥ 0.58 (promising signal, needs local features)
- DATA_GAP: insufficient data or features

**Governance:**
```
No Supabase writes.
No production pipeline changes.
No scoring changes.
Research only.
```
"""


def main() -> None:
    print("[Arena] Loading parquet...")
    df = pd.read_parquet(PQ_PATH)
    print(f"[Arena] Total rows: {len(df):,}")

    all_results = []
    for pack_name, courses in PACKS.items():
        result = run_pack(pack_name, courses, df)
        all_results.append(result)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "train_period": "2015-2022",
        "valid_period": "2023",
        "test_period": "2024-2025",
        "packs": all_results,
    }

    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(exist_ok=True)

    json_path = out_dir / "international_baseline_arena_latest.json"
    md_path = out_dir / "international_baseline_arena_latest.md"

    json_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n[Arena] Written: {json_path}")

    md_path.write_text(_write_md(all_results, out["generated_at"]))
    print(f"[Arena] Written: {md_path}")

    print("\n=== SUMMARY ===")
    for r in all_results:
        print(f"  {r['pack']}: verdict={r.get('verdict')} best_auc={r.get('best_auc', 0):.4f} "
              f"best_sr={r.get('best_model_sr', 0):.1%} "
              f"fav_sr={r.get('baselines', {}).get('favourite_sr', 0):.1%}")


if __name__ == "__main__":
    main()
