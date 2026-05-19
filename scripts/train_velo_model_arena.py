"""
VÉLØ Model Arena — CPU tabular challenger models.

Uses 1310 clean training-safe rows from velo_unified_evidence_corpus_v1.csv.
Time-split validation only. No random splits. No lookahead.

Outputs:
  data/reports/velo_model_arena_latest.json
  data/reports/velo_model_arena_latest.md
  models/shadow/model_arena/{model_name}.pkl

Hard rules:
  No production model changes.
  No scoring changes.
  No SP as predictive feature.
  Classification only — must beat SQPE Brier before any promotion.
"""

import json
import os
import pickle
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "data" / "velo_unified_evidence_corpus_v1.csv"
OUT_DIR = ROOT / "data" / "reports"
MODEL_DIR = ROOT / "models" / "shadow" / "model_arena"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ── Features ──────────────────────────────────────────────────────────────────

NUMERIC_FEATURES = [
    "velo_prime_prob",
    "sqpe_v17_prob",
    "market_deception_score",
    "improvement_score",
    "place_prob",
    "longshot_prob",
    "release_day_prob",
    "comment_intel_score",
]

CATEGORICAL_FEATURES = [
    "decision_tier",
    "confidence_level",
]

TIER_MAP = {"A": 0, "B": 1, "C": 2, "X": 3}
CONF_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

TARGETS = {
    "win": "won",
    "frame": "placed",
}


# ── Data loading and preparation ──────────────────────────────────────────────

def load_training_data() -> pd.DataFrame:
    df = pd.read_csv(CORPUS_PATH)
    # Training-safe filter: result_matched=True, identity_unresolved=False
    safe = df[df["result_matched"] == True].copy()
    safe = safe[safe["identity_unresolved"] == False].copy()
    # Exclude May 18 (not yet approved for learning)
    safe = safe[safe["date"] != "2026-05-18"].copy()
    # Parse date for time split
    safe["date_parsed"] = pd.to_datetime(safe["date"], errors="coerce")
    safe = safe.dropna(subset=["date_parsed"])
    safe = safe.sort_values("date_parsed").reset_index(drop=True)
    return safe


def encode_features(df: pd.DataFrame) -> np.ndarray:
    features = []
    for col in NUMERIC_FEATURES:
        vals = pd.to_numeric(df.get(col, pd.Series([np.nan] * len(df))), errors="coerce")
        features.append(vals.values.reshape(-1, 1))

    # Tier encoding
    tier_vals = df.get("decision_tier", pd.Series(["B"] * len(df))).map(TIER_MAP).fillna(1).values
    features.append(tier_vals.reshape(-1, 1))

    # Confidence encoding
    conf_vals = df.get("confidence_level", pd.Series(["MEDIUM"] * len(df))).map(CONF_MAP).fillna(1).values
    features.append(conf_vals.reshape(-1, 1))

    return np.hstack(features)


def encode_target(df: pd.DataFrame, target_col: str) -> np.ndarray:
    col = df[target_col]
    if col.dtype == bool:
        return col.astype(int).values
    return pd.to_numeric(col, errors="coerce").fillna(0).astype(int).values


def time_split(df: pd.DataFrame, val_fraction: float = 0.20):
    split_idx = int(len(df) * (1 - val_fraction))
    return df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy()


# ── Metrics ───────────────────────────────────────────────────────────────────

def compute_decile_metrics(probs: np.ndarray, labels: np.ndarray, sp: np.ndarray | None = None) -> list[dict]:
    df = pd.DataFrame({"prob": probs, "label": labels})
    if sp is not None:
        df["sp"] = sp
    df["decile"] = pd.qcut(df["prob"], 10, labels=False, duplicates="drop")
    rows = []
    for d, grp in df.groupby("decile"):
        row = {
            "decile": int(d),
            "n": len(grp),
            "sr": round(grp["label"].mean(), 4),
            "avg_prob": round(grp["prob"].mean(), 4),
        }
        if "sp" in df.columns:
            winners = grp[grp["label"] == 1]
            stake = len(grp)
            returns = winners["sp"].sum() if len(winners) > 0 else 0.0
            row["roi"] = round((returns - stake) / stake, 4) if stake > 0 else None
        rows.append(row)
    return rows


def roi_full(probs: np.ndarray, labels: np.ndarray, sp: np.ndarray) -> float:
    winners_mask = labels == 1
    returns = sp[winners_mask].sum()
    stake = len(labels)
    return round((returns - stake) / stake, 4) if stake > 0 else 0.0


def roi_outlier_stripped(probs: np.ndarray, labels: np.ndarray, sp: np.ndarray,
                          lower: float = 0.05, upper: float = 0.95) -> float:
    sp_low = np.quantile(sp, lower)
    sp_high = np.quantile(sp, upper)
    mask = (sp >= sp_low) & (sp <= sp_high)
    sp_s, labels_s = sp[mask], labels[mask]
    winners_mask = labels_s == 1
    returns = sp_s[winners_mask].sum()
    stake = len(labels_s)
    return round((returns - stake) / stake, 4) if stake > 0 else 0.0


# ── Model definitions ─────────────────────────────────────────────────────────

def make_logistic() -> Pipeline:
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("clf", CalibratedClassifierCV(
            LogisticRegression(max_iter=1000, C=1.0, solver="lbfgs"),
            cv=3, method="isotonic",
        )),
    ])


def make_random_forest() -> Pipeline:
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("clf", RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42, n_jobs=-1)),
    ])


def make_lightgbm() -> Pipeline | None:
    try:
        import lightgbm as lgb
        from lightgbm import LGBMClassifier
        return Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("clf", LGBMClassifier(
                n_estimators=300,
                learning_rate=0.05,
                max_depth=6,
                num_leaves=31,
                min_child_samples=20,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                n_jobs=-1,
                verbose=-1,
            )),
        ])
    except ImportError:
        return None


def make_xgboost() -> Pipeline | None:
    try:
        import xgboost as xgb
        from xgboost import XGBClassifier
        return Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("clf", XGBClassifier(
                n_estimators=300,
                learning_rate=0.05,
                max_depth=6,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                n_jobs=-1,
                eval_metric="logloss",
                verbosity=0,
            )),
        ])
    except ImportError:
        return None


def make_catboost() -> Pipeline | None:
    try:
        from catboost import CatBoostClassifier
        return Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("clf", CatBoostClassifier(
                iterations=300,
                learning_rate=0.05,
                depth=6,
                random_seed=42,
                verbose=0,
            )),
        ])
    except ImportError:
        return None


MODELS = {
    "logistic_baseline": make_logistic,
    "random_forest": make_random_forest,
    "lightgbm": make_lightgbm,
    "xgboost": make_xgboost,
    "catboost": make_catboost,
}


# ── Evaluation ────────────────────────────────────────────────────────────────

def evaluate_model(
    name: str,
    pipeline,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    sp_val: np.ndarray | None = None,
    target: str = "win",
) -> dict:
    pipeline.fit(X_train, y_train)
    probs = pipeline.predict_proba(X_val)[:, 1]

    result = {
        "model": name,
        "target": target,
        "n_train": len(y_train),
        "n_val": len(y_val),
        "brier_score": round(brier_score_loss(y_val, probs), 6),
        "log_loss": round(log_loss(y_val, probs), 6),
        "auc": round(roc_auc_score(y_val, probs), 6) if y_val.sum() > 0 and y_val.sum() < len(y_val) else None,
        "val_sr": round(y_val.mean(), 4),
        "decile_metrics": compute_decile_metrics(probs, y_val, sp_val),
    }

    if sp_val is not None and target == "win":
        result["roi_full"] = roi_full(probs, y_val, sp_val)
        result["roi_outlier_stripped"] = roi_outlier_stripped(probs, y_val, sp_val)

    return result


# ── Classification ────────────────────────────────────────────────────────────

def classify_result(model_results: list[dict], sqpe_brier: float) -> dict[str, str]:
    classifications = {}
    for r in model_results:
        name = r["model"]
        target = r["target"]
        brier = r.get("brier_score")
        if brier is None:
            classifications[f"{name}_{target}"] = "MODEL_REJECTED"
        elif brier < sqpe_brier:
            classifications[f"{name}_{target}"] = "SHADOW_MODEL_PROMISING"
        elif brier <= sqpe_brier * 1.05:
            classifications[f"{name}_{target}"] = "CURRENT_STACK_BEATS_ALL"
        else:
            classifications[f"{name}_{target}"] = "CURRENT_STACK_BEATS_ALL"
    return classifications


# ── Report writing ────────────────────────────────────────────────────────────

def write_reports(arena: dict) -> None:
    json_path = OUT_DIR / "velo_model_arena_latest.json"
    json_path.write_text(json.dumps(arena, indent=2), encoding="utf-8")
    print(f"JSON: {json_path}")

    lines = [
        "# VÉLØ MODEL ARENA — LATEST RUN",
        "",
        f"**Run at:** {arena['run_at']}  ",
        f"**Training rows:** {arena['n_train_total']}  ",
        f"**Validation rows:** {arena['n_val_total']}  ",
        f"**Val split date:** {arena['val_split_date']}",
        "",
        "---",
        "",
        "## Dependencies",
        "",
    ]
    for pkg, status in arena["dependencies"].items():
        lines.append(f"- `{pkg}`: {status}")
    lines += [
        "",
        "---",
        "",
        "## Results by Target",
        "",
    ]
    for target in ("win", "frame"):
        lines += [f"### Target: {target}", ""]
        lines += [
            "| Model | Brier ↓ | Log Loss ↓ | AUC ↑ | ROI (full) |",
            "|---|---|---|---|---|",
        ]
        for r in arena["results"]:
            if r["target"] != target:
                continue
            cls = arena["classifications"].get(f"{r['model']}_{target}", "")
            roi = r.get("roi_full", "n/a")
            lines.append(
                f"| {r['model']} | {r['brier_score']} | {r['log_loss']} | "
                f"{r.get('auc','n/a')} | {roi} |"
            )
        lines += [""]

    lines += [
        "## Classifications",
        "",
        "| Model/Target | Classification |",
        "|---|---|",
    ]
    for k, v in arena["classifications"].items():
        lines.append(f"| {k} | **{v}** |")

    lines += [
        "",
        "---",
        "",
        "## Hard Rules",
        "",
        "```",
        "No production model changes.",
        "No scoring changes.",
        "No SP as predictive feature.",
        "Classification only — must beat SQPE Brier before any promotion.",
        "```",
    ]

    md_path = OUT_DIR / "velo_model_arena_latest.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"MD:   {md_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print("\nVÉLØ MODEL ARENA")
    print("=" * 60)

    # Check dependencies
    deps = {}
    for pkg in ["lightgbm", "xgboost", "catboost", "optuna", "mlflow"]:
        try:
            mod = __import__(pkg)
            deps[pkg] = f"INSTALLED {getattr(mod, '__version__', '?')}"
        except ImportError:
            deps[pkg] = "MISSING — install not automatic, operator approval required"
    print("Dependencies:")
    for k, v in deps.items():
        print(f"  {k}: {v}")

    # Load data
    print(f"\nLoading corpus: {CORPUS_PATH}")
    df = load_training_data()
    print(f"Training rows loaded: {len(df)}")

    train_df, val_df = time_split(df, val_fraction=0.20)
    val_split_date = str(val_df["date_parsed"].min().date())
    print(f"Train: {len(train_df)} | Val: {len(val_df)} | Val split date: {val_split_date}")

    X_train = encode_features(train_df)
    X_val = encode_features(val_df)

    sp_val = pd.to_numeric(val_df.get("sp_decimal", pd.Series([np.nan] * len(val_df))), errors="coerce").values

    # SQPE baseline Brier (on val set)
    sqpe_probs_val = pd.to_numeric(val_df.get("sqpe_v17_prob", pd.Series([np.nan] * len(val_df))), errors="coerce")
    y_val_win = encode_target(val_df, "won")
    sqpe_valid = sqpe_probs_val.notna()
    sqpe_brier = brier_score_loss(y_val_win[sqpe_valid], sqpe_probs_val.values[sqpe_valid]) if sqpe_valid.sum() > 10 else 0.25
    print(f"SQPE baseline Brier (win target): {sqpe_brier:.6f}")

    all_results = []

    for target_name, target_col in TARGETS.items():
        print(f"\n── Target: {target_name} ──")
        y_train = encode_target(train_df, target_col)
        y_val = encode_target(val_df, target_col)
        print(f"  class balance train: {y_train.mean():.3f}  val: {y_val.mean():.3f}")

        for model_name, factory in MODELS.items():
            pipeline = factory()
            if pipeline is None:
                print(f"  SKIP {model_name} — package not installed")
                all_results.append({
                    "model": model_name,
                    "target": target_name,
                    "status": "MISSING_PACKAGE",
                    "brier_score": None,
                    "log_loss": None,
                    "auc": None,
                })
                continue

            try:
                print(f"  Training {model_name}...", end=" ", flush=True)
                result = evaluate_model(
                    model_name, pipeline,
                    X_train, y_train,
                    X_val, y_val,
                    sp_val=sp_val if target_name == "win" else None,
                    target=target_name,
                )
                all_results.append(result)
                print(f"Brier={result['brier_score']:.6f} AUC={result.get('auc','n/a')}")

                # Save model
                model_path = MODEL_DIR / f"{model_name}_{target_name}.pkl"
                with open(model_path, "wb") as f:
                    pickle.dump(pipeline, f)

            except Exception as exc:
                print(f"ERROR: {exc}")
                all_results.append({
                    "model": model_name,
                    "target": target_name,
                    "status": f"ERROR: {exc}",
                    "brier_score": None,
                    "log_loss": None,
                    "auc": None,
                })

    # Classify results
    classifications = classify_result(
        [r for r in all_results if r.get("brier_score") is not None],
        sqpe_brier,
    )

    arena = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "corpus_path": str(CORPUS_PATH),
        "n_train_total": len(train_df),
        "n_val_total": len(val_df),
        "val_split_date": val_split_date,
        "sqpe_baseline_brier_win": round(sqpe_brier, 6),
        "features": NUMERIC_FEATURES + ["decision_tier_encoded", "confidence_level_encoded"],
        "targets": list(TARGETS.keys()),
        "dependencies": deps,
        "results": all_results,
        "classifications": classifications,
        "governance": {
            "no_production_model_change": True,
            "no_scoring_change": True,
            "no_sp_as_predictive_feature": True,
            "promotion_gate": "must beat SQPE Brier on time-split validation",
            "approved_by": None,
        },
    }

    write_reports(arena)

    # Summary
    print("\n" + "=" * 60)
    print("ARENA CLASSIFICATIONS:")
    for k, v in classifications.items():
        print(f"  {k:<45} {v}")

    print("\nHard rules confirmed:")
    print("  No production model changes.")
    print("  No scoring changes.")
    print("  No SP as predictive feature.")
    print("=" * 60)

    return arena


if __name__ == "__main__":
    run()
