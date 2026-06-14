#!/usr/bin/env python3
"""
new_build_train_core_v0_or.py
Train Core V0_OR challenger — adds official_rating + is_rated to Core V0 features.
Champion model is untouched. Challenger saves to data/new_build/models/core_v0_or/.
Shadow only.
"""
import json
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd
from sklearn.metrics import roc_auc_score, brier_score_loss

MODEL_DIR = ROOT / "data" / "new_build" / "models" / "core_v0_or"
RPT_DIR = ROOT / "data" / "new_build" / "reports"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

TRUST_POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
VELO_SCORING_ALLOWED = False

BANNED_CHECK = {"rpr", "rpr_num", "rpr_vs_field", "sp_dec", "log_sp",
                "is_fav", "sp_rank", "implied_prob", "pos", "ovr_btn",
                "btn", "comment", "time", "target"}

IDENTITY = {"race_id", "date", "course", "horse", "jockey", "trainer"}
TARGET_COLS = {"won", "framed", "pos_num"}

CHAMPION_METRICS = {"auc": 0.6735, "sr": 0.218, "frame": 0.503, "brier": 0.0861}


def _race_metrics(df, prob_col):
    sr = fr = races = 0
    for _, g in df.groupby("race_id"):
        if len(g) < 2:
            continue
        races += 1
        if g.loc[g[prob_col].idxmax(), "won"] == 1:
            sr += 1
        if g.nlargest(3, prob_col)["won"].sum() >= 1:
            fr += 1
    return round(sr / races, 4) if races else 0, round(fr / races, 4) if races else 0, races


def _or_rank_baseline(df):
    sr = fr = races = 0
    col = "official_rating" if "official_rating" in df.columns else "or_vs_field"
    for _, g in df.groupby("race_id"):
        if len(g) < 2:
            continue
        races += 1
        if g.loc[g[col].idxmax(), "won"] == 1:
            sr += 1
        if g.nlargest(3, col)["won"].sum() >= 1:
            fr += 1
    return round(sr / races, 4) if races else 0, round(fr / races, 4) if races else 0


def run():
    print("Loading OR challenger dataset ...")
    train = pd.read_parquet(ROOT / "data" / "new_build" / "training" / "core_v0_or_train.parquet")
    val   = pd.read_parquet(ROOT / "data" / "new_build" / "training" / "core_v0_or_val.parquet")
    print(f"  Train: {len(train):,}  Val: {len(val):,}")

    feature_cols = [c for c in train.columns if c not in IDENTITY and c not in TARGET_COLS]

    # Anti-leakage
    for b in BANNED_CHECK:
        if b in feature_cols:
            raise AssertionError(f"LEAKAGE ABORT: {b} in features")
    rpr_hits = [c for c in feature_cols if "rpr" in c.lower()]
    if rpr_hits:
        raise AssertionError(f"RPR VIOLATION: {rpr_hits}")
    sp_hits = [c for c in feature_cols if c in {"sp_dec", "log_sp", "is_fav", "sp_rank"}]
    if sp_hits:
        raise AssertionError(f"SP LEAKAGE: {sp_hits}")
    print(f"  Leakage check: PASS  Features: {len(feature_cols)}")

    # Drop constant cols, encode objects
    non_const = [c for c in feature_cols if train[c].nunique() > 1]
    dropped_const = set(feature_cols) - set(non_const)
    if dropped_const:
        print(f"  Dropped constant: {dropped_const}")
    feature_cols = non_const

    obj_cols = [c for c in feature_cols if train[c].dtype == object]
    for c in obj_cols:
        cats = pd.Categorical(pd.concat([train[c], val[c]], ignore_index=True)).categories
        train[c] = pd.Categorical(train[c], categories=cats).codes
        val[c]   = pd.Categorical(val[c],   categories=cats).codes

    X_train = train[feature_cols].copy()
    X_val   = val[feature_cols].copy()
    medians = X_train.median(numeric_only=True)
    X_train = X_train.fillna(medians)
    X_val   = X_val.fillna(medians)
    y_train, y_val = train["won"], val["won"]

    try:
        import lightgbm as lgb
        print("  Training LightGBM challenger ...")
        model = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=6,
            num_leaves=63, min_child_samples=50,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbose=-1, n_jobs=4,
        )
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)],
                  callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(0)])
        model_type = "LightGBM"
    except ImportError:
        from sklearn.ensemble import GradientBoostingClassifier
        print("  Training sklearn GBM challenger ...")
        model = GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            min_samples_leaf=50, subsample=0.8, random_state=42,
        )
        model.fit(X_train, y_train)
        model_type = "GradientBoostingClassifier"

    val_probs = model.predict_proba(X_val)[:, 1]
    val_auc   = round(float(roc_auc_score(y_val, val_probs)), 4)
    val_brier = round(float(brier_score_loss(y_val, val_probs)), 4)
    val["_prob"] = val_probs
    val_sr, val_fr, val_races = _race_metrics(val, "_prob")
    or_sr, or_fr = _or_rank_baseline(val)

    print(f"\n  === Challenger Core V0_OR ===")
    print(f"  Val AUC:      {val_auc}  (champion: {CHAMPION_METRICS['auc']}  delta: {val_auc-CHAMPION_METRICS['auc']:+.4f})")
    print(f"  Val Brier:    {val_brier}  (champion: {CHAMPION_METRICS['brier']})")
    print(f"  Val SR:       {val_sr:.1%}  (champion: {CHAMPION_METRICS['sr']:.1%}  baseline: {or_sr:.1%})")
    print(f"  Val Frame:    {val_fr:.1%}  (champion: {CHAMPION_METRICS['frame']:.1%}  baseline: {or_fr:.1%})")
    print(f"  Val Races:    {val_races:,}")

    # Save challenger
    model_path = MODEL_DIR / "core_v0_or_model.pkl"
    with model_path.open("wb") as f:
        pickle.dump({"model": model, "feature_cols": feature_cols, "medians": medians.to_dict()}, f)

    # Decision
    auc_delta = val_auc - CHAMPION_METRICS["auc"]
    sr_delta  = val_sr  - CHAMPION_METRICS["sr"]
    if auc_delta > 0.002 or sr_delta > 0.005:
        decision = "OR_FIX_CONFIRMED_AND_IMPROVES"
    elif auc_delta >= -0.002:
        decision = "OR_FIX_CONFIRMED_NO_LIFT"
    else:
        decision = "OR_MAPPING_BUG_NOT_FOUND"

    print(f"\n  Decision: {decision}")

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": VELO_SCORING_ALLOWED,
        "rpr_violation": False,
        "sp_violation": False,
        "model_type": model_type,
        "features": feature_cols,
        "or_features_added": ["official_rating", "is_rated"],
        "or_diagnosis": "or_rating='–' for unrated horses (41% of Flat). official_rating=0 + is_rated=0 for unrated.",
        "challenger_metrics": {"auc": val_auc, "brier": val_brier, "sr": val_sr, "frame": val_fr, "races": val_races},
        "champion_metrics": CHAMPION_METRICS,
        "or_rank_baseline": {"sr": or_sr, "frame": or_fr},
        "auc_delta_vs_champion": auc_delta,
        "sr_delta_vs_champion": sr_delta,
        "decision": decision,
    }
    (MODEL_DIR / "core_v0_or_metadata.json").write_text(json.dumps(metadata, indent=2))

    lines = [
        "# Core V0_OR Challenger — Decision Report",
        f"Generated: {metadata['generated_at']}",
        "",
        "## OR Diagnosis",
        "- `or_rating = '–'` for ~41% of Flat runners (genuine unrated horses: maidens, novices)",
        "- Not a bug — `or_num` nulls correctly reflect real absence of handicap mark",
        "- Fix: `official_rating` (numeric, 0=unrated) + `is_rated` binary flag",
        "- `or_vs_field` (relative OR within race) already in Core V0 — retained",
        "",
        "## Metrics Comparison",
        "| Metric | Champion (Core V0) | Challenger (Core V0_OR) | OR Baseline | Delta |",
        "|---|---|---|---|---|",
        f"| AUC | {CHAMPION_METRICS['auc']} | {val_auc} | — | {auc_delta:+.4f} |",
        f"| Brier | {CHAMPION_METRICS['brier']} | {val_brier} | — | {val_brier-CHAMPION_METRICS['brier']:+.4f} |",
        f"| SR | {CHAMPION_METRICS['sr']:.1%} | {val_sr:.1%} | {or_sr:.1%} | {sr_delta:+.1%} |",
        f"| Frame | {CHAMPION_METRICS['frame']:.1%} | {val_fr:.1%} | {or_fr:.1%} | {val_fr-CHAMPION_METRICS['frame']:+.1%} |",
        "",
        f"## Decision: **{decision}**",
        "",
        "| Classification | Meaning |",
        "|---|---|",
        "| OR_FIX_CONFIRMED_AND_IMPROVES | OR was missing, challenger beats champion |",
        "| OR_FIX_CONFIRMED_NO_LIFT | OR was missing but no meaningful improvement |",
        "| OR_MAPPING_BUG_NOT_FOUND | OR already captured via or_vs_field |",
    ]
    (RPT_DIR / "core_v0_or_decision_latest.md").write_text("\n".join(lines))
    (RPT_DIR / "core_v0_or_decision_latest.json").write_text(json.dumps(metadata, indent=2))
    print("  Reports written.")


if __name__ == "__main__":
    run()
