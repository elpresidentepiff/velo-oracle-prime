#!/usr/bin/env python3
"""
VÉLØ — RPDC Specialist Model (LAB_EXPERIMENT, additive, not live)
====================================================================
First-ever real trained model using RPDC (release/cash-window) tags as
input features, instead of the current crude RS>=1.5 threshold advisory
gate. Trains on data/training/rpdc_training_corpus.jsonl (RPDC rows
joined against real results by normalized horse name + date, since RPDC's
old rac_/hrs_ ID scheme doesn't match results' numeric RP IDs).

No RPR anywhere in this feature set -- RPDC is entirely career-context/
release-signal data, structurally incapable of leaking RPR.

Does NOT touch Old VELO, No-RPR shadow, New Build, or Champion Intent.
Not wired into any scoring path. LAB_EXPERIMENT: report, do not promote.

Usage:
    python scripts/ops/train_rpdc_specialist_model.py
"""
import json
import pickle
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import log_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "data" / "training" / "rpdc_training_corpus.jsonl"
STAGING_DIR = ROOT / "models" / "rpdc_specialist_staging"

NUMERIC_FIELDS = [
    "current_or", "or_delta_to_win", "runs_since_win", "runs_since_place",
    "campaign_run_no", "days_since_run", "class_delta", "stable_heat",
    "rpdc_tag_count", "rpdc_release_score", "rpdc_suppression_score",
]
BOOLEAN_FIELDS = [
    "distance_revert_flag", "course_return_flag", "jockey_upgrade_flag",
    "rpdc_cash_window_flag", "rpdc_trap_flag",
]
ALL_TAGS = [
    "CYCLE_RUN_1", "CYCLE_RUN_2", "CYCLE_RUN_3", "STABLE_WARM", "COURSE_RETURN",
    "PLACE_FORM", "MARK_READY", "WIN_STREAK", "MARK_NEAR", "DISTANCE_RETURN",
    "BELOW_LAST_WIN_MARK", "FRESH_RETURN", "JOCKEY_UPGRADE", "TRAINER_RELEASE_ZONE",
    "PLACE_MARK_READY",
]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for f in NUMERIC_FIELDS:
        X[f] = pd.to_numeric(df[f], errors="coerce").fillna(0)
    for f in BOOLEAN_FIELDS:
        X[f] = df[f].fillna(False).astype(int)
    for tag in ALL_TAGS:
        X[f"tag_{tag}"] = df["rpdc_tags"].apply(lambda tags: int(tag in (tags or [])))
    return X


def _race_metrics(df, prob_col, target_col="target"):
    top1_hits = mrr_sum = races = 0
    for _, grp in df.groupby(["run_date", "race_id"]):
        if len(grp) < 2:
            continue
        races += 1
        ranked = grp.sort_values(prob_col, ascending=False).reset_index(drop=True)
        winner_pos = ranked.index[ranked[target_col] == 1]
        if len(winner_pos) == 0:
            continue
        rank = int(winner_pos[0]) + 1
        if rank == 1:
            top1_hits += 1
        mrr_sum += 1.0 / rank
    top1 = top1_hits / races if races else 0.0
    mrr = mrr_sum / races if races else 0.0
    return round(top1, 4), round(mrr, 4), races


def main():
    print("=" * 65)
    print("VELO — RPDC Specialist Model (LAB_EXPERIMENT)")
    print("  First-ever trained model using RPDC tags as real features")
    print("=" * 65)

    rows = [json.loads(line) for line in open(CORPUS)]
    df = pd.DataFrame(rows)
    df["run_date"] = pd.to_datetime(df["run_date"])
    df = df.sort_values("run_date").reset_index(drop=True)
    print(f"\nLoaded {len(df):,} rows, {df['run_date'].nunique()} dates "
          f"({df['run_date'].min().date()} to {df['run_date'].max().date()})")
    print(f"Win rate: {df['target'].mean()*100:.2f}%")

    # Date-based split (not year split -- only ~4.5 months of data).
    # Last 20% of dates as test.
    unique_dates = sorted(df["run_date"].unique())
    split_idx = int(len(unique_dates) * 0.8)
    split_date = unique_dates[split_idx]
    train_df = df[df["run_date"] < split_date].copy()
    test_df = df[df["run_date"] >= split_date].copy()
    print(f"\nTrain: {len(train_df):,} rows ({train_df['run_date'].nunique()} dates)")
    print(f"Test:  {len(test_df):,} rows ({test_df['run_date'].nunique()} dates), "
          f"from {split_date.date()}")

    X_tr = build_features(train_df)
    X_te = build_features(test_df)
    y_tr = train_df["target"]
    y_te = test_df["target"]

    # OR-rank baseline on same test population (only where current_or present)
    or_baseline_df = test_df.copy()
    or_baseline_df["pred_or"] = pd.to_numeric(or_baseline_df["current_or"], errors="coerce").fillna(0)
    or_top1, or_mrr, or_n = _race_metrics(or_baseline_df, "pred_or")
    print(f"\nOR-rank baseline (current_or): Top-1={or_top1*100:.1f}%  MRR={or_mrr:.4f}  n={or_n}")

    # RPDC release_score baseline (the CURRENT advisory-gate signal, untrained)
    rs_baseline_df = test_df.copy()
    rs_baseline_df["pred_rs"] = pd.to_numeric(rs_baseline_df["rpdc_release_score"], errors="coerce").fillna(0)
    rs_top1, rs_mrr, rs_n = _race_metrics(rs_baseline_df, "pred_rs")
    print(f"RPDC release_score baseline (current advisory signal, untrained): "
          f"Top-1={rs_top1*100:.1f}%  MRR={rs_mrr:.4f}  n={rs_n}")

    gbm_params = dict(
        n_estimators=300, learning_rate=0.05, max_depth=4,
        min_samples_leaf=20, subsample=0.8, max_features="sqrt",
        random_state=42, verbose=1,
    )
    print(f"\nTraining RPDC specialist ({X_tr.shape[1]} features, {len(train_df):,} rows) ...")
    model = CalibratedClassifierCV(GradientBoostingClassifier(**gbm_params), method="isotonic", cv=3)
    model.fit(X_tr, y_tr)

    p_te = model.predict_proba(X_te)[:, 1]
    auc = roc_auc_score(y_te, p_te)
    ll = log_loss(y_te, p_te)
    test_df = test_df.copy()
    test_df["pred"] = p_te
    top1, mrr, n_races = _race_metrics(test_df, "pred")

    print("\n" + "=" * 65)
    print("RESULTS")
    print("=" * 65)
    print(f"  RPDC specialist       : AUC={auc:.4f}  Top-1={top1*100:.1f}%  MRR={mrr:.4f}  n={n_races}")
    print(f"  OR-rank baseline      : Top-1={or_top1*100:.1f}%  MRR={or_mrr:.4f}  n={or_n}")
    print(f"  RPDC release_score    : Top-1={rs_top1*100:.1f}%  MRR={rs_mrr:.4f}  n={rs_n}  (current gate, untrained)")

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    with open(STAGING_DIR / "rpdc_specialist.pkl", "wb") as f:
        pickle.dump(model, f)

    base_est = model.calibrated_classifiers_[0]
    base = base_est.estimator if hasattr(base_est, "estimator") else base_est.base_estimator
    importances = sorted(zip(X_tr.columns, base.feature_importances_), key=lambda x: -x[1])
    pd.DataFrame(importances, columns=["feature", "importance"]).to_csv(
        STAGING_DIR / "feature_importance.csv", index=False
    )

    metadata = {
        "version": "v1-rpdc-specialist",
        "classification": "LAB_EXPERIMENT",
        "model_type": "GradientBoostingClassifier + IsotonicCalibration",
        "trained_at": datetime.now().isoformat(),
        "source": str(CORPUS),
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "features": list(X_tr.columns),
        "contains_rpr": False,
        "results": {
            "auc": round(float(auc), 4),
            "log_loss": round(float(ll), 4),
            "top1": top1,
            "mrr": mrr,
            "or_baseline_top1": or_top1,
            "rpdc_release_score_baseline_top1": rs_top1,
        },
        "promotion_status": "NOT_PROMOTED — LAB_EXPERIMENT only, requires n>=100 evidence gate + operator sign-off",
        "not_wired_to": ["run_prime_today.py", "run_radical_shadow_today.py", "new_build_two_lane_score.py",
                          "build_rpdc_daily.py"],
    }
    (STAGING_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2))

    print(f"\nWritten: {STAGING_DIR}/")
    print("\nTop 15 feature importances:")
    for feat, imp in importances[:15]:
        print(f"  {feat:25s} {imp:.4f}")


if __name__ == "__main__":
    main()
