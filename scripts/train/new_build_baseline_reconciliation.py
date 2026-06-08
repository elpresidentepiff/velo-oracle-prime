"""
new_build_baseline_reconciliation.py
Reproduces the Core V0_OR champion baseline and then ablates Passport / Intent layers.

DATA SOURCE RULE:
  Core V0_OR rows come from the pre-built champion datasets written by
  new_build_core_v0_or_dataset.py (raceform_clean.parquet as or_rating source).
  DO NOT re-derive or_rating from entry_snapshot_v1 — that file differs in coverage.

FEATURE COLUMN TRUTH (verified against actual parquets 2026-05-28):
  passport_features.parquet: pp_career_runs, pp_win_rate, pp_place_rate,
      pp_days_since_last, pp_layoff, pp_avg_sp_last5, pp_jockey_continuity,
      pp_course_seen, pp_or_change_3, pp_class_moved_up, pp_class_moved_down
  intent_features.parquet: mark_compression_score, curr_or_minus_last_win_or,
      curr_or_minus_best_or, runs_since_win, runs_since_place, runs_since_mkt_support,
      odds_resilience_score, intent_trip_match, intent_course_win_history,
      intent_going_match, intent_class_drop_vs_best, intent_run_after_break,
      intent_sp_shortening, intent_wins_last10, intent_top3_last6
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
TRAIN_DIR = ROOT / "data" / "new_build" / "training"
REPORT_DIR = ROOT / "data" / "new_build" / "reports"

# Champion baseline — these files were written by new_build_core_v0_or_dataset.py
# using raceform_clean.parquet as the or_rating source. Do not re-derive.
CORE_TRAIN_PATH = TRAIN_DIR / "core_v0_or_train.parquet"
CORE_VAL_PATH   = TRAIN_DIR / "core_v0_or_val.parquet"

PASSPORT_PATH = TRAIN_DIR / "passport_features.parquet"
INTENT_PATH   = TRAIN_DIR / "intent_features.parquet"

# Core V0_OR champion feature set (identical to new_build_core_v0_or_dataset.py)
CORE_FEATURES = [
    "dist_f", "going_code", "is_aw", "field_size", "draw_num", "draw_pct",
    "age_num", "wgt_lbs", "or_vs_field",
    "release_window_score", "going_fit_score", "distance_fit_score",
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    "setup_run_flag", "cash_run_flag", "official_rating", "is_rated",
]

# Actual columns in passport_features.parquet (verified 2026-05-28)
PASSPORT_FEATURES = [
    "pp_career_runs", "pp_win_rate", "pp_place_rate",
    "pp_days_since_last", "pp_layoff", "pp_avg_sp_last5",
    "pp_jockey_continuity", "pp_course_seen", "pp_or_change_3",
    "pp_class_moved_up", "pp_class_moved_down",
]

# Actual columns in intent_features.parquet (verified 2026-05-28)
INTENT_FEATURES = [
    "mark_compression_score", "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "runs_since_win", "runs_since_place", "runs_since_mkt_support",
    "odds_resilience_score", "intent_trip_match", "intent_course_win_history",
    "intent_going_match", "intent_class_drop_vs_best", "intent_run_after_break",
    "intent_sp_shortening", "intent_wins_last10", "intent_top3_last6",
]

# Accepted champion targets (reproduction tolerance ±0.005 AUC)
CHAMPION_AUC   = 0.6777
CHAMPION_SR    = 0.220
CHAMPION_FRAME = 0.512
REPRO_AUC_TOL  = 0.005

# LightGBM params matching Core V0_OR champion training
LGBM_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "max_depth": 6,
    "num_leaves": 31,
    "verbosity": -1,
    "random_state": 42,
}


def _check_paths():
    missing = [p for p in [CORE_TRAIN_PATH, CORE_VAL_PATH, PASSPORT_PATH, INTENT_PATH] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Required data files not found: {missing}")


def _load_core():
    print("Loading pre-built Core V0_OR champion datasets...")
    train = pd.read_parquet(CORE_TRAIN_PATH)
    val   = pd.read_parquet(CORE_VAL_PATH)
    print(f"  Train: {len(train):,} rows  |  Val: {len(val):,} rows")
    print(f"  Val is_rated coverage: {(val['is_rated'] == 1).mean() * 100:.1f}%")
    return train, val


def _join_features(train, val, path, feature_cols, label):
    print(f"Joining {label} features from {path.name}...")
    feats = pd.read_parquet(path, columns=["race_id", "horse"] + feature_cols)
    print(f"  {label} parquet: {len(feats):,} rows")
    train = train.merge(feats, on=["race_id", "horse"], how="left")
    val   = val.merge(feats, on=["race_id", "horse"], how="left")

    # Coverage check
    for split_name, df in [("train", train), ("val", val)]:
        null_pct = df[feature_cols].isnull().mean().mean() * 100
        if null_pct > 50:
            print(f"  WARNING: {label} null rate in {split_name} = {null_pct:.1f}%")
        else:
            print(f"  {label} null rate in {split_name}: {null_pct:.1f}%")
    return train, val


def _fill_features(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = df[c].fillna(0)
    return df


def _evaluate(name, model, val_df, features):
    probs = model.predict_proba(val_df[features])[:, 1]
    auc   = roc_auc_score(val_df["won"], probs)
    brier = brier_score_loss(val_df["won"], probs)

    tmp = val_df[["race_id", "won"]].copy()
    tmp["prob"] = probs

    top1  = tmp.sort_values(["race_id", "prob"], ascending=[True, False]).groupby("race_id").head(1)
    sr    = top1["won"].mean()

    # Frame: any of top-3 model picks won the race
    top3  = tmp.sort_values(["race_id", "prob"], ascending=[True, False]).groupby("race_id").head(3)
    frame = top3.groupby("race_id")["won"].max().mean()

    print(f"  {name}: AUC={auc:.4f}  SR={sr:.4f}  Frame={frame:.4f}  Brier={brier:.4f}")
    return {"AUC": round(auc, 4), "SR": round(sr, 4), "Frame": round(frame, 4), "Brier": round(brier, 4)}


def run_reconciliation():
    _check_paths()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load champion baseline datasets
    train_df, val_df = _load_core()

    # 2. Join challenger layers
    train_df, val_df = _join_features(train_df, val_df, PASSPORT_PATH, PASSPORT_FEATURES, "Passport")
    train_df, val_df = _join_features(train_df, val_df, INTENT_PATH,   INTENT_FEATURES,   "Intent")

    # 3. Fill all feature NAs with 0
    all_features = CORE_FEATURES + PASSPORT_FEATURES + INTENT_FEATURES
    train_df = _fill_features(train_df, all_features)
    val_df   = _fill_features(val_df,   all_features)

    # 4. Leakage guard — none of these must appear in any feature list
    BANNED = {"rpr_num", "rpr_vs_field", "rpr", "ts_num", "ts",
              "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav"}
    violations = [f for f in all_features if f in BANNED or "rpr" in f.lower()]
    if violations:
        raise AssertionError(f"LEAKAGE ABORT: {violations}")
    print("Leakage check: PASS")

    # 5. Run ablation variants
    variants = {
        "A: Core V0_OR (Champion Baseline)": CORE_FEATURES,
        "B: Passport-only":                  PASSPORT_FEATURES,
        "C: Intent-only":                    INTENT_FEATURES,
        "D: Core + Passport":                CORE_FEATURES + PASSPORT_FEATURES,
        "E: Core + Intent":                  CORE_FEATURES + INTENT_FEATURES,
        "F: All Combined":                   CORE_FEATURES + PASSPORT_FEATURES + INTENT_FEATURES,
    }

    # STEP A: Baseline only first
    print("\n--- STEP A: Baseline reproduction ---")
    model_a = lgb.LGBMClassifier(**LGBM_PARAMS)
    present_core = [f for f in CORE_FEATURES if f in train_df.columns]
    missing_core = [f for f in CORE_FEATURES if f not in train_df.columns]
    if missing_core:
        print(f"  WARNING: Core features missing from dataset: {missing_core}")
    model_a.fit(train_df[present_core], train_df["won"])
    baseline_metrics = _evaluate("A: Core V0_OR (Champion Baseline)", model_a, val_df, present_core)

    baseline_auc = baseline_metrics["AUC"]
    repro_pass   = abs(baseline_auc - CHAMPION_AUC) <= REPRO_AUC_TOL

    print(f"\nBaseline AUC: {baseline_auc:.4f}  (target: {CHAMPION_AUC}  tol: ±{REPRO_AUC_TOL})")
    print(f"Baseline SR:  {baseline_metrics['SR']:.4f}  (target: {CHAMPION_SR})")
    print(f"Baseline Frame: {baseline_metrics['Frame']:.4f}  (target: {CHAMPION_FRAME})")

    if not repro_pass:
        result = {
            "status": "BASELINE_REPRODUCTION_FAILED",
            "baseline_auc": baseline_auc,
            "champion_auc": CHAMPION_AUC,
            "delta": round(abs(baseline_auc - CHAMPION_AUC), 4),
            "metrics": {"A: Core V0_OR (Champion Baseline)": baseline_metrics},
            "reproduction_pass": False,
            "generated_at": datetime.now().isoformat(),
        }
        _write_reports(result, pd.DataFrame(result["metrics"]).T)
        print("\nBASELINE_REPRODUCTION_FAILED — stopping. See report.")
        return

    # 6. Run all variants
    print("\n--- Full ablation (all 6 variants) ---")
    results = {"A: Core V0_OR (Champion Baseline)": baseline_metrics}

    for name, features in list(variants.items())[1:]:
        present = [f for f in features if f in train_df.columns]
        missing = [f for f in features if f not in train_df.columns]
        if missing:
            print(f"  WARN: {name} — missing cols: {missing}")
        model = lgb.LGBMClassifier(**LGBM_PARAMS)
        model.fit(train_df[present], train_df["won"])
        results[name] = _evaluate(name, model, val_df, present)

    # 7. Compute lift vs true champion
    core_auc   = results["A: Core V0_OR (Champion Baseline)"]["AUC"]
    core_sr    = results["A: Core V0_OR (Champion Baseline)"]["SR"]
    core_frame = results["A: Core V0_OR (Champion Baseline)"]["Frame"]

    report_df = pd.DataFrame(results).T
    report_df["AUC_lift_vs_champion"]   = (report_df["AUC"]   - core_auc).round(4)
    report_df["SR_lift_vs_champion"]    = (report_df["SR"]    - core_sr).round(4)
    report_df["Frame_lift_vs_champion"] = (report_df["Frame"] - core_frame).round(4)

    print("\nFINAL RECONCILIATION TABLE")
    print("=" * 70)
    print(report_df.to_markdown())

    # 8. Challenger promotion check
    best_name  = report_df.loc[report_df["AUC"].idxmax()].name
    best_auc   = report_df["AUC"].max()
    promotion  = best_name != "A: Core V0_OR (Champion Baseline)" and best_auc > core_auc

    print(f"\nBest variant: {best_name}  AUC={best_auc:.4f}")
    print(f"Challenger promotion earned: {promotion}")

    final = {
        "status": "BASELINE_REPRODUCTION_PASSED",
        "reproduction_pass": True,
        "champion_auc": CHAMPION_AUC,
        "champion_sr": CHAMPION_SR,
        "champion_frame": CHAMPION_FRAME,
        "baseline_auc": baseline_auc,
        "best_variant": best_name,
        "best_variant_auc": best_auc,
        "challenger_promotion_earned": promotion,
        "rpr_violation": False,
        "sp_violation": False,
        "new_build_scoring_allowed": True,
        "old_live_velo_impact": False,
        "shadow_impact": False,
        "metrics": results,
        "generated_at": datetime.now().isoformat(),
    }
    _write_reports(final, report_df)
    print(f"\nReports saved to: {REPORT_DIR}")


def _write_reports(data, df):
    json_path = REPORT_DIR / "ablation_baseline_reconciliation_latest.json"
    md_path   = REPORT_DIR / "ablation_baseline_reconciliation_latest.md"

    def _json_safe(obj):
        if isinstance(obj, (np.bool_, np.integer)):
            return obj.item()
        if isinstance(obj, (np.floating,)):
            return float(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, default=_json_safe)

    status = data.get("status", "UNKNOWN")
    repro  = data.get("reproduction_pass", False)
    promo  = data.get("challenger_promotion_earned", False)

    lines = [
        "# Ablation Baseline Reconciliation",
        f"Generated: {data['generated_at']}",
        "",
        f"**Status:** `{status}`",
        f"**Baseline Reproduction (AUC ±0.005):** {'PASS' if repro else 'FAIL'}",
        f"**Challenger Promotion Earned:** {promo}",
        "",
        "## Metrics",
        df.to_markdown(),
        "",
        "## Governance",
        f"- `rpr_violation`: {data.get('rpr_violation', False)}",
        f"- `sp_violation`: {data.get('sp_violation', False)}",
        f"- `new_build_scoring_allowed`: {data.get('new_build_scoring_allowed', True)}",
        f"- `old_live_velo_impact`: {data.get('old_live_velo_impact', False)}",
        f"- `shadow_impact`: {data.get('shadow_impact', False)}",
    ]

    if not repro:
        lines += [
            "",
            "## BASELINE REPRODUCTION FAILED",
            f"Expected AUC: {data.get('champion_auc')}  "
            f"Got: {data.get('baseline_auc')}  "
            f"Delta: {data.get('delta')}",
            "Ablation script invalid. No variant results produced.",
        ]

    with open(md_path, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    run_reconciliation()
