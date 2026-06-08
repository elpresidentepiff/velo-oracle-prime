"""
V3 ablation: Recent Form Velocity (win_rate_last3, place_rate_last3, win_rate_last6)
Gate: V3 AUC > 0.6999 on 2025 held-out test set
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import roc_auc_score
import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[2]
TR = ROOT / "data" / "new_build" / "training"

params = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "max_depth": 6,
    "num_leaves": 31,
    "verbosity": -1,
    "random_state": 42,
    "objective": "binary",
    "metric": "auc",
}

JOIN = ["race_id", "horse"]


def build_dataset(core_path, pp_path, intent_path, v3_path=None):
    df = pd.read_parquet(core_path)
    pp = pd.read_parquet(pp_path)
    intent = pd.read_parquet(intent_path)
    df = df.merge(pp, on=JOIN, how="left")
    df = df.merge(intent, on=JOIN, how="left")
    if v3_path:
        v3 = pd.read_parquet(v3_path)
        df = df.merge(v3, on=JOIN, how="left")
    return df


def get_features(df, extra=None):
    exclude = {"race_id", "horse", "win_label", "won", "framed", "pos_num",
               "date", "race_date", "course", "rp_uid", "horse_id", "trainer", "jockey"}
    target_col = "won" if "won" in df.columns else "win_label"
    feats = [c for c in df.columns if c not in exclude and c != target_col
             and df[c].dtype in [np.float64, np.float32, np.int64, np.int32]]
    return feats


def train_eval(train_df, test_df, label="V1"):
    target_col = "won" if "won" in train_df.columns else "win_label"
    feats = get_features(train_df)
    X_tr = train_df[feats].fillna(0)
    y_tr = train_df[target_col]
    X_te = test_df[feats].fillna(0)
    y_te = test_df[target_col]

    model = lgb.LGBMClassifier(**params)
    model.fit(X_tr, y_tr)
    proba = model.predict_proba(X_te)[:, 1]
    auc = roc_auc_score(y_te, proba)
    print(f"  {label}: {len(feats)} features | AUC={auc:.4f}")
    return auc, feats


# ── Leakage spot check ────────────────────────────────────────────────────────
print("=== Leakage spot check ===")
core_tr = pd.read_parquet(TR / "core_v0_or_train.parquet")
v3_tr_raw = pd.read_parquet(TR / "v3_velocity_candidates_train.parquet")

date_col = "date" if "date" in core_tr.columns else (
    "race_date" if "race_date" in core_tr.columns else None)
print(f"Date col: {date_col}")

merged_lk = core_tr.merge(v3_tr_raw, on=JOIN, how="left")
if date_col:
    ms = merged_lk.sort_values(["horse", date_col])
    first = ms.groupby("horse").first()
    nan_rate = first["win_rate_last3"].isna().mean()
    print(f"First-appearance NaN rate: {nan_rate:.3f}  (>0.50 = leakage-safe)")
    has_both = ms.groupby("horse")["win_rate_last3"].apply(
        lambda x: x.notna().any() and x.isna().any())
    if has_both.any():
        h = has_both[has_both].index[0]
        s = ms[ms["horse"] == h][[date_col, "win_rate_last3"]].head(6)
        print(f"\nSample horse {h!r} NaN->value transition:")
        print(s.to_string())
    else:
        print("All horses: NaN pattern consistent")
else:
    print("WARNING: no date col in core parquet — temporal check skipped")

# ── Build datasets ────────────────────────────────────────────────────────────
print("\n=== Building datasets ===")
tr_v1 = build_dataset(TR / "core_v0_or_train.parquet",
                      TR / "passport_features.parquet",
                      TR / "intent_features.parquet")
te_v1 = build_dataset(TR / "core_v0_or_test.parquet",
                      TR / "passport_features.parquet",
                      TR / "intent_features.parquet")

tr_v3 = build_dataset(TR / "core_v0_or_train.parquet",
                      TR / "passport_features.parquet",
                      TR / "intent_features.parquet",
                      TR / "v3_velocity_candidates_train.parquet")
te_v3 = build_dataset(TR / "core_v0_or_test.parquet",
                      TR / "passport_features.parquet",
                      TR / "intent_features.parquet",
                      TR / "v3_velocity_candidates_test.parquet")

print(f"V1 train={tr_v1.shape} test={te_v1.shape}")
print(f"V3 train={tr_v3.shape} test={te_v3.shape}")

# ── Train ─────────────────────────────────────────────────────────────────────
print("\n=== Ablation ===")
v1_auc, v1_feats = train_eval(tr_v1, te_v1, "V1_baseline")
v3_auc, v3_feats = train_eval(tr_v3, te_v3, "V3_velocity")

delta = v3_auc - v1_auc
gate = v3_auc > 0.6999
v3_new = [f for f in v3_feats if f not in v1_feats]

print(f"\n  Delta: {delta:+.4f}")
print(f"  New features in V3: {v3_new}")
print(f"  Gate (>0.6999): {'PASS' if gate else 'FAIL'}")
print(f"  Verdict: {'PROMOTED' if gate and delta > 0 else 'REJECTED'}")

# ── Save results ─────────────────────────────────────────────────────────────
out_path = ROOT / "data" / "new_build" / "reports" / "challenger_v3_ablation_results.json"
results = {
    "generated_by": "v3_ablation.py",
    "v1_reproduced_auc": round(v1_auc, 4),
    "v1_target_auc": 0.6969,
    "baseline_check": "PASS" if abs(v1_auc - 0.6969) < 0.005 else "WARNING",
    "v3_results": {"auc": round(v3_auc, 4), "delta": round(delta, 4)},
    "gate_passed": bool(gate and delta > 0),
    "feature_count": {"v1": len(v1_feats), "v3": len(v3_feats)},
    "v3_new_features": v3_new,
    "verdict": "PROMOTED" if (gate and delta > 0) else "REJECTED",
}
out_path.write_text(json.dumps(results, indent=2))
print(f"\nResults written to {out_path.name}")
