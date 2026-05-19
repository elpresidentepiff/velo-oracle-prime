"""
VÉLØ Model Arena V2 — expanded challenger set.

Adds:
  XGBoost 3.2.0, CatBoost 1.2.10 (operator-approved 2026-05-18)
  Feature sets: NO_VP_COMPOSITE, NO_VP_NO_MARKET, RAW_SIDECARS_ONLY,
                MARKET_ONLY, HORSE_MEMORY (rolling, leakage-free), FULL_META
  Targets: win, frame, suppress (tier C/X + VP < 0.20)
  Metrics: Brier, log-loss, AUC, calibration, SR/frame/ROI by decile,
           feature importance (native), SHAP if available

Outputs:
  data/reports/velo_model_arena_ablation_v2_latest.json
  data/reports/velo_model_arena_ablation_v2_latest.md
  models/shadow/model_arena_v2/

Hard rules: no production changes, no scoring changes, no SP as predictive feature.
"""

import json
import pickle
import warnings
from datetime import datetime, timezone
from pathlib import Path


class NumpyEncoder(json.JSONEncoder):
    """Convert numpy types to Python native before JSON serialisation."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "data" / "velo_unified_evidence_corpus_v1.csv"
CAREER_MEMORY_PATH = ROOT / "data" / "features" / "horse_career_memory_latest.parquet"
OUT_DIR = ROOT / "data" / "reports"
MODEL_DIR = ROOT / "models" / "shadow" / "model_arena_v2"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

TIER_MAP = {"A": 0, "B": 1, "C": 2, "X": 3}
CONF_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


# ── Feature set definitions ───────────────────────────────────────────────────

FEATURE_SETS = {
    "NO_VP_COMPOSITE": [
        "sqpe_v17_prob", "market_deception_score", "improvement_score",
        "place_prob", "longshot_prob", "release_day_prob",
        "comment_intel_score", "confidence_level_encoded",
    ],
    "NO_VP_NO_MARKET": [
        "sqpe_v17_prob", "improvement_score",
        "release_day_prob", "comment_intel_score",
    ],
    "RAW_SIDECARS_ONLY": [
        "sqpe_v17_prob", "market_deception_score", "improvement_score",
        "place_prob", "longshot_prob", "release_day_prob", "comment_intel_score",
    ],
    "MARKET_ONLY": [
        "market_deception_score", "place_prob", "longshot_prob", "release_day_prob",
    ],
    "HORSE_MEMORY": [
        "prior_starts", "prior_win_rate", "prior_frame_rate",
        "prior_avg_vp", "prior_avg_mds", "prior_avg_improvement",
        "prior_mds_high_events", "prior_vp_ge_30_events", "prior_vp_ge_40_events",
        "prior_improvement_high_events",
    ],
    "FULL_META": [
        "velo_prime_prob", "sqpe_v17_prob", "market_deception_score",
        "improvement_score", "place_prob", "longshot_prob",
        "release_day_prob", "comment_intel_score",
        "decision_tier_encoded", "confidence_level_encoded",
    ],
}

TARGETS = {
    "win": "won_bin",
    "frame": "placed_bin",
    "suppress": "suppress_bin",
}


# ── Data loading + feature engineering ───────────────────────────────────────

def load_data() -> pd.DataFrame:
    df = pd.read_csv(CORPUS_PATH)
    safe = df[df["result_matched"] == True].copy()
    safe = safe[safe.get("identity_unresolved", pd.Series(False, index=safe.index)) == False].copy()
    safe = safe[safe["date"] != "2026-05-18"].copy()
    safe["date_parsed"] = pd.to_datetime(safe["date"], errors="coerce")
    safe = safe.dropna(subset=["date_parsed"]).sort_values("date_parsed").reset_index(drop=True)

    # Encodings
    safe["decision_tier_encoded"] = safe["decision_tier"].map(TIER_MAP).fillna(1)
    safe["confidence_level_encoded"] = safe["confidence_level"].map(CONF_MAP).fillna(1)

    # Binary targets
    safe["won_bin"] = safe["won"].apply(
        lambda x: 1 if str(x).lower() in ("true", "1", "1.0") else 0)
    safe["placed_bin"] = safe["placed"].apply(
        lambda x: 1 if str(x).lower() in ("true", "1", "1.0") else 0)

    # Suppress target: tier C or X AND VP < 0.20
    vp = pd.to_numeric(safe["velo_prime_prob"], errors="coerce").fillna(0.25)
    tier_cx = safe["decision_tier"].isin(["C", "X"])
    safe["suppress_bin"] = ((tier_cx) & (vp < 0.20)).astype(int)

    # Horse identity key (mirrors career memory build)
    safe["group_key"] = (
        safe["horse_id"].fillna("")
        .where(safe["horse_id"].notna() & (safe["horse_id"] != ""),
               safe["horse"].str.lower().str.strip())
    )

    return safe


def build_rolling_horse_memory(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each row, compute career stats using ONLY prior rows for that horse.
    Returns a DataFrame indexed like df with one column per rolling feature.
    Leakage-free: values for race at date D use only races before D.
    """
    df = df.sort_values("date_parsed").reset_index(drop=True)

    rows = []
    for _, grp in df.groupby("group_key", sort=False):
        grp = grp.sort_values("date_parsed").reset_index()
        n = len(grp)
        for i in range(n):
            prior = grp.iloc[:i]
            prior_starts = i

            if prior_starts == 0:
                rows.append({
                    "orig_index": grp.iloc[i]["index"],
                    "prior_starts": 0,
                    "prior_win_rate": np.nan,
                    "prior_frame_rate": np.nan,
                    "prior_avg_vp": np.nan,
                    "prior_avg_mds": np.nan,
                    "prior_avg_improvement": np.nan,
                    "prior_mds_high_events": 0,
                    "prior_vp_ge_30_events": 0,
                    "prior_vp_ge_40_events": 0,
                    "prior_improvement_high_events": 0,
                })
                continue

            wins = prior["won_bin"].sum()
            frames = prior["placed_bin"].sum()
            vp_vals = pd.to_numeric(prior["velo_prime_prob"], errors="coerce").dropna()
            mds_vals = pd.to_numeric(prior["market_deception_score"], errors="coerce").dropna()
            impr_vals = pd.to_numeric(prior["improvement_score"], errors="coerce").dropna()

            rows.append({
                "orig_index": grp.iloc[i]["index"],
                "prior_starts": prior_starts,
                "prior_win_rate": wins / prior_starts,
                "prior_frame_rate": frames / prior_starts,
                "prior_avg_vp": vp_vals.mean() if len(vp_vals) > 0 else np.nan,
                "prior_avg_mds": mds_vals.mean() if len(mds_vals) > 0 else np.nan,
                "prior_avg_improvement": impr_vals.mean() if len(impr_vals) > 0 else np.nan,
                "prior_mds_high_events": int((mds_vals > 0.50).sum()),
                "prior_vp_ge_30_events": int((vp_vals >= 0.30).sum()),
                "prior_vp_ge_40_events": int((vp_vals >= 0.40).sum()),
                "prior_improvement_high_events": int((impr_vals > 0.40).sum()),
            })

    mem_df = pd.DataFrame(rows).set_index("orig_index")
    # Join back onto df
    result = df.copy()
    for col in [c for c in mem_df.columns]:
        result[col] = mem_df[col].reindex(result.index).values
    return result


def encode_features(df: pd.DataFrame, feature_names: list[str]) -> np.ndarray:
    cols = []
    for f in feature_names:
        if f in df.columns:
            cols.append(pd.to_numeric(df[f], errors="coerce").values.reshape(-1, 1))
        else:
            cols.append(np.full((len(df), 1), np.nan))
    return np.hstack(cols)


def time_split(df: pd.DataFrame, val_fraction: float = 0.20):
    idx = int(len(df) * (1 - val_fraction))
    return df.iloc[:idx].copy(), df.iloc[idx:].copy()


# ── Metrics ───────────────────────────────────────────────────────────────────

def calibration_summary(y: np.ndarray, p: np.ndarray, n_bins: int = 5) -> list[dict]:
    try:
        fp, mp = calibration_curve(y, p, n_bins=n_bins, strategy="quantile")
        return [{"bin": i, "mean_pred": round(float(mp[i]), 4),
                 "fraction_pos": round(float(fp[i]), 4)} for i in range(len(mp))]
    except Exception:
        return []


def decile_metrics(probs: np.ndarray, labels: np.ndarray,
                   sp: np.ndarray | None = None) -> list[dict]:
    d = pd.DataFrame({"p": probs, "y": labels})
    if sp is not None:
        d["sp"] = sp
    try:
        d["decile"] = pd.qcut(d["p"], 10, labels=False, duplicates="drop")
    except Exception:
        return []
    rows = []
    for dec, grp in d.groupby("decile"):
        row = {"decile": int(dec), "n": int(len(grp)),
               "sr": round(float(grp["y"].mean()), 4), "avg_prob": round(float(grp["p"].mean()), 4)}
        if "sp" in d.columns:
            winners = grp[grp["y"] == 1]
            ret = float(winners["sp"].dropna().sum())
            row["roi"] = round((ret - len(grp)) / len(grp), 4) if len(grp) > 0 else None
        rows.append(row)
    return rows


def compute_roi(labels: np.ndarray, sp: np.ndarray | None,
                strip: float = 0.0) -> float | None:
    if sp is None:
        return None
    valid = ~np.isnan(sp)
    labels, sp = labels[valid], sp[valid]
    if len(labels) == 0:
        return None
    if strip > 0:
        lo, hi = np.quantile(sp, strip), np.quantile(sp, 1 - strip)
        mask = (sp >= lo) & (sp <= hi)
        labels, sp = labels[mask], sp[mask]
    if len(labels) == 0:
        return None
    winners = labels == 1
    return round((float(sp[winners].sum()) - len(labels)) / len(labels), 4)


def extract_feature_importance(pipeline: Pipeline, feature_names: list[str]) -> list[dict]:
    """Extract feature importance from the last estimator in a pipeline."""
    try:
        clf = pipeline.named_steps["clf"]
        # Handle CalibratedClassifierCV wrapper
        if hasattr(clf, "calibrated_classifiers_"):
            base = clf.calibrated_classifiers_[0].estimator
        elif hasattr(clf, "estimators_"):
            base = clf
        else:
            base = clf

        if hasattr(base, "feature_importances_"):
            imps = base.feature_importances_
        elif hasattr(base, "coef_"):
            imps = np.abs(base.coef_[0]) if base.coef_.ndim > 1 else np.abs(base.coef_)
        else:
            return []

        # Average across calibrated clfs if needed
        if hasattr(clf, "calibrated_classifiers_") and len(clf.calibrated_classifiers_) > 1:
            all_imps = []
            for cc in clf.calibrated_classifiers_:
                b = cc.estimator
                if hasattr(b, "feature_importances_"):
                    all_imps.append(b.feature_importances_)
                elif hasattr(b, "coef_"):
                    all_imps.append(np.abs(b.coef_[0] if b.coef_.ndim > 1 else b.coef_))
            if all_imps:
                imps = np.mean(all_imps, axis=0)

        return [{"feature": f, "importance": round(float(v), 6)}
                for f, v in sorted(zip(feature_names, imps), key=lambda x: -x[1])]
    except Exception:
        return []


# ── Model factories ───────────────────────────────────────────────────────────

def make_logistic():
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("clf", CalibratedClassifierCV(
            LogisticRegression(max_iter=1000, C=1.0), cv=3, method="isotonic")),
    ])


def make_rf():
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("clf", RandomForestClassifier(
            n_estimators=200, max_depth=6, random_state=42, n_jobs=-1)),
    ])


def make_lgbm():
    try:
        from lightgbm import LGBMClassifier
        return Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("clf", LGBMClassifier(
                n_estimators=300, learning_rate=0.05, max_depth=5,
                num_leaves=20, min_child_samples=20, random_state=42,
                n_jobs=-1, verbose=-1)),
        ])
    except ImportError:
        return None


def make_xgb():
    try:
        from xgboost import XGBClassifier
        return Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("clf", XGBClassifier(
                n_estimators=300, learning_rate=0.05, max_depth=4,
                min_child_weight=5, subsample=0.8, colsample_bytree=0.8,
                random_state=42, n_jobs=-1, verbosity=0,
                eval_metric="logloss", use_label_encoder=False)),
        ])
    except ImportError:
        return None


def make_catboost():
    try:
        from catboost import CatBoostClassifier
        return Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("clf", CatBoostClassifier(
                iterations=300, learning_rate=0.05, depth=5,
                min_data_in_leaf=10, random_seed=42,
                verbose=0, allow_writing_files=False)),
        ])
    except ImportError:
        return None


MODELS = {
    "logistic": make_logistic,
    "random_forest": make_rf,
    "lightgbm": make_lgbm,
    "xgboost": make_xgb,
    "catboost": make_catboost,
}


# ── Classification ────────────────────────────────────────────────────────────

def classify(fs: str, target: str, brier: float,
             sqpe_win_brier: float, n_val: int) -> str:
    if n_val < 50:
        return "MORE_DATA_REQUIRED"
    # For suppress: use prevalence baseline comparison
    # For win: use SQPE win brier
    # For frame: report as-is (separate baseline needed)
    if target == "suppress":
        return "SUPPRESS_MODEL_EVALUATED"
    beats = brier < sqpe_win_brier
    if not beats:
        return "CURRENT_STACK_BEATS_ALL"
    if fs == "FULL_META":
        return "META_CALIBRATOR_PROMISING"
    return "INDEPENDENT_MODEL_PROMISING"


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print("\nVÉLØ MODEL ARENA V2")
    print("=" * 60)
    print(f"XGBoost: ", end="")
    try:
        import xgboost; print(xgboost.__version__)
    except ImportError:
        print("MISSING")
    print(f"CatBoost: ", end="")
    try:
        import catboost; print(catboost.__version__)
    except ImportError:
        print("MISSING")
    print(f"Optuna: ", end="")
    try:
        import optuna; print(optuna.__version__)
    except ImportError:
        print("MISSING")
    print(f"SHAP available: {SHAP_AVAILABLE}")

    df = load_data()
    print(f"\nBuilding rolling horse memory (leakage-free)...")
    df = build_rolling_horse_memory(df)
    print(f"  Done. Prior-starts range: {df['prior_starts'].min()}–{df['prior_starts'].max()}")

    train_df, val_df = time_split(df)
    val_split_date = str(val_df["date_parsed"].min().date())
    print(f"Train: {len(train_df)} | Val: {len(val_df)} | Split: {val_split_date}")

    sp_val = pd.to_numeric(val_df.get("sp_decimal", pd.Series(dtype=float)),
                           errors="coerce").values

    # SQPE baseline
    sqpe_val = pd.to_numeric(val_df.get("sqpe_v17_prob", pd.Series(dtype=float)),
                             errors="coerce")
    y_val_win = val_df["won_bin"].values
    sqpe_ok = sqpe_val.notna().values
    sqpe_brier_win = (brier_score_loss(y_val_win[sqpe_ok], sqpe_val.values[sqpe_ok])
                      if sqpe_ok.sum() > 10 else 0.25)
    print(f"SQPE baseline Brier (win): {sqpe_brier_win:.6f}")

    # Suppress prevalence baseline
    y_suppress = val_df["suppress_bin"].values
    suppress_prev = y_suppress.mean()
    suppress_brier_naive = brier_score_loss(
        y_suppress, np.full(len(y_suppress), suppress_prev))
    print(f"Suppress prevalence: {suppress_prev:.3f}  Naive Brier: {suppress_brier_naive:.6f}")

    all_results = []
    best_win_brier = sqpe_brier_win
    best_model_info = None

    for target_name, target_col in TARGETS.items():
        y_train = train_df[target_col].values
        y_val = val_df[target_col].values
        print(f"\n── Target: {target_name} (class balance: train={y_train.mean():.3f} "
              f"val={y_val.mean():.3f}) ──")

        for fs_name, feature_list in FEATURE_SETS.items():
            print(f"  [{fs_name}]")
            X_train = encode_features(train_df, feature_list)
            X_val = encode_features(val_df, feature_list)

            for model_name, factory in MODELS.items():
                pipeline = factory()
                if pipeline is None:
                    print(f"    SKIP {model_name}")
                    continue
                try:
                    print(f"    {model_name}...", end=" ", flush=True)
                    pipeline.fit(X_train, y_train)
                    probs = pipeline.predict_proba(X_val)[:, 1]

                    brier = brier_score_loss(y_val, probs)
                    ll = log_loss(y_val, probs)
                    auc = (roc_auc_score(y_val, probs)
                           if 0 < y_val.sum() < len(y_val) else None)
                    cal = calibration_summary(y_val, probs)
                    deciles = decile_metrics(
                        probs, y_val,
                        sp_val if target_name == "win" else None)
                    roi = compute_roi(
                        y_val, sp_val if target_name == "win" else None)
                    roi_s = compute_roi(
                        y_val, sp_val if target_name == "win" else None, strip=0.05)
                    cls = classify(fs_name, target_name, brier, sqpe_brier_win, len(y_val))
                    fi = extract_feature_importance(pipeline, feature_list)

                    auc_s = f"{auc:.4f}" if auc is not None else "n/a"
                    print(f"Brier={brier:.6f} AUC={auc_s} → {cls}")

                    # Track best win model
                    if target_name == "win" and brier < best_win_brier:
                        best_win_brier = brier
                        best_model_info = (fs_name, model_name, pipeline, feature_list)

                    # Save model
                    pkl_path = MODEL_DIR / f"{fs_name}_{model_name}_{target_name}.pkl"
                    with open(pkl_path, "wb") as f:
                        pickle.dump(pipeline, f)

                    all_results.append({
                        "feature_set": fs_name,
                        "model": model_name,
                        "target": target_name,
                        "n_features": len(feature_list),
                        "features_used": feature_list,
                        "n_train": len(y_train),
                        "n_val": len(y_val),
                        "brier_score": round(brier, 6),
                        "log_loss": round(ll, 6),
                        "auc": round(auc, 6) if auc is not None else None,
                        "roi_full": roi,
                        "roi_outlier_stripped": roi_s,
                        "calibration": cal,
                        "decile_metrics": deciles,
                        "feature_importance": fi[:10],
                        "classification": cls,
                    })
                except Exception as exc:
                    print(f"ERROR: {exc}")
                    all_results.append({
                        "feature_set": fs_name, "model": model_name,
                        "target": target_name, "error": str(exc),
                        "brier_score": None, "classification": "ERROR",
                    })

    # SHAP for best win model
    shap_result = None
    if SHAP_AVAILABLE and best_model_info:
        fs_name, model_name, pipeline, feature_list = best_model_info
        print(f"\nSHAP: computing for best win model ({fs_name}/{model_name})...")
        try:
            X_val_arr = encode_features(val_df, feature_list)
            imputed = pipeline.named_steps["impute"].transform(X_val_arr)
            explainer = shap.TreeExplainer(pipeline.named_steps["clf"])
            shap_vals = explainer.shap_values(imputed)
            mean_abs = np.abs(shap_vals).mean(axis=0)
            shap_result = [{"feature": f, "mean_abs_shap": round(float(v), 6)}
                           for f, v in sorted(zip(feature_list, mean_abs), key=lambda x: -x[1])]
            print(f"  SHAP complete ({len(shap_result)} features)")
        except Exception as e:
            print(f"  SHAP failed: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("ARENA V2 SUMMARY (win target)")
    print(f"{'FS':<22} {'Model':<14} {'Brier':>8} {'AUC':>7} {'Classification'}")
    print("-" * 80)
    for r in sorted([x for x in all_results if x.get("target") == "win"
                     and x.get("brier_score")], key=lambda x: x["brier_score"]):
        auc_s = str(r.get("auc", "n/a"))[:7]
        print(f"{r['feature_set']:<22} {r['model']:<14} {r['brier_score']:>8.6f} "
              f"{auc_s:>7} {r['classification']}")

    # Key verdicts
    def _best(fs, tgt):
        cands = [r["brier_score"] for r in all_results
                 if r.get("feature_set") == fs and r.get("target") == tgt
                 and r.get("brier_score") is not None]
        return min(cands) if cands else None

    print("\nKEY VERDICTS:")
    print(f"  SQPE baseline:             {sqpe_brier_win:.6f}")
    for fs in FEATURE_SETS:
        b = _best(fs, "win")
        if b:
            delta = b - sqpe_brier_win
            ind = " INDEPENDENT" if b < sqpe_brier_win and fs != "FULL_META" else ""
            print(f"  {fs:<22} {b:.6f}  ({delta:+.6f}){ind}")

    # Build output artifact
    key_verdict = {
        "sqpe_baseline_brier_win": round(sqpe_brier_win, 6),
        "best_by_feature_set_win": {
            fs: _best(fs, "win") for fs in FEATURE_SETS},
        "best_overall_win": _best("NO_VP_COMPOSITE", "win"),
        "independent_signal_confirmed": bool(
            _best("NO_VP_COMPOSITE", "win") is not None
            and _best("NO_VP_COMPOSITE", "win") < sqpe_brier_win),
        "frame_remains_current_stack": all(
            r.get("classification") in ("CURRENT_STACK_BEATS_ALL", "SUPPRESS_MODEL_EVALUATED",
                                         "MORE_DATA_REQUIRED", "ERROR", None)
            for r in all_results if r.get("target") == "frame"),
        "suppress_prevalence": round(float(suppress_prev), 4),
        "shap_available": SHAP_AVAILABLE,
    }

    arena = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "val_split_date": val_split_date,
        "n_train": len(train_df),
        "n_val": len(val_df),
        "sqpe_baseline_brier_win": round(sqpe_brier_win, 6),
        "suppress_naive_brier": round(suppress_brier_naive, 6),
        "packages": {
            "xgboost": _pkg_version("xgboost"),
            "catboost": _pkg_version("catboost"),
            "optuna": _pkg_version("optuna"),
            "lightgbm": _pkg_version("lightgbm"),
        },
        "feature_sets": {k: v for k, v in FEATURE_SETS.items()},
        "results": all_results,
        "key_verdict": key_verdict,
        "shap_best_win_model": shap_result,
        "governance": {
            "no_production_change": True,
            "no_scoring_change": True,
            "no_sp_as_predictive_feature": True,
            "rolling_horse_memory_leakage_free": True,
        },
    }

    json_path = OUT_DIR / "velo_model_arena_ablation_v2_latest.json"
    json_path.write_text(json.dumps(arena, indent=2, cls=NumpyEncoder), encoding="utf-8")
    print(f"\nJSON: {json_path}")
    _write_md(arena)
    print("=" * 60)
    return arena


def _pkg_version(name: str) -> str | None:
    try:
        import importlib.metadata
        return importlib.metadata.version(name)
    except Exception:
        return None


def _write_md(arena: dict) -> None:
    kv = arena["key_verdict"]
    sqpe = arena["sqpe_baseline_brier_win"]

    def _icon(cls: str) -> str:
        return {"INDEPENDENT_MODEL_PROMISING": "✓",
                "META_CALIBRATOR_PROMISING": "~",
                "CURRENT_STACK_BEATS_ALL": "✗",
                "SUPPRESS_MODEL_EVALUATED": "S",
                "MORE_DATA_REQUIRED": "?"}.get(cls, "?")

    lines = [
        "# VÉLØ MODEL ARENA V2",
        "",
        f"**Run at:** {arena['run_at']}  ",
        f"**Train:** {arena['n_train']} | **Val:** {arena['n_val']} | **Split:** {arena['val_split_date']}  ",
        f"**SQPE baseline Brier (win):** {sqpe}  ",
        f"**Packages:** XGBoost {arena['packages'].get('xgboost','?')} | "
        f"CatBoost {arena['packages'].get('catboost','?')} | "
        f"Optuna {arena['packages'].get('optuna','?')} | "
        f"LightGBM {arena['packages'].get('lightgbm','?')}",
        "",
        "---",
        "",
        "## Win Target (sorted by Brier ↓)",
        "",
        "| Feature Set | Model | Brier ↓ | AUC ↑ | ROI | Classification |",
        "|---|---|---|---|---|---|",
    ]
    win_rows = sorted([r for r in arena["results"]
                       if r.get("target") == "win" and r.get("brier_score")],
                      key=lambda x: x["brier_score"])
    for r in win_rows:
        lines.append(
            f"| {r['feature_set']} | {r['model']} | **{r['brier_score']}** | "
            f"{r.get('auc','n/a')} | {r.get('roi_full','n/a')} | "
            f"{_icon(r['classification'])} {r['classification']} |")

    lines += ["", f"*SQPE baseline: {sqpe}*", "", "---", "",
              "## Frame Target", "",
              "| Feature Set | Model | Brier ↓ | AUC ↑ | Classification |",
              "|---|---|---|---|---|"]
    frame_rows = sorted([r for r in arena["results"]
                         if r.get("target") == "frame" and r.get("brier_score")],
                        key=lambda x: x["brier_score"])
    for r in frame_rows:
        lines.append(
            f"| {r['feature_set']} | {r['model']} | **{r['brier_score']}** | "
            f"{r.get('auc','n/a')} | {_icon(r['classification'])} {r['classification']} |")

    lines += ["", "---", "", "## Suppress Target", "",
              "| Feature Set | Model | Brier ↓ | AUC ↑ | Classification |",
              "|---|---|---|---|---|"]
    supp_rows = sorted([r for r in arena["results"]
                        if r.get("target") == "suppress" and r.get("brier_score")],
                       key=lambda x: x["brier_score"])
    for r in supp_rows:
        lines.append(
            f"| {r['feature_set']} | {r['model']} | **{r['brier_score']}** | "
            f"{r.get('auc','n/a')} | {_icon(r['classification'])} {r['classification']} |")

    lines += [
        "", "---", "", "## Key Verdict", "",
        "| Metric | Value |", "|---|---|",
        f"| SQPE baseline Brier | {sqpe} |",
        f"| Independent signal confirmed | {'YES' if kv['independent_signal_confirmed'] else 'NO'} |",
        f"| Frame remains current stack | {'YES' if kv['frame_remains_current_stack'] else 'NO'} |",
    ]
    for fs, b in kv.get("best_by_feature_set_win", {}).items():
        lines.append(f"| {fs} best win | {b} |")

    # Feature importance for NO_VP_COMPOSITE logistic if available
    fi_rows = [r for r in win_rows
               if r.get("feature_set") == "NO_VP_COMPOSITE"
               and r.get("model") == "logistic"
               and r.get("feature_importance")]
    if fi_rows:
        fi = fi_rows[0]["feature_importance"]
        lines += ["", "---", "", "## Feature Importance — NO_VP_COMPOSITE Logistic (win)", "",
                  "| Feature | Importance |", "|---|---|"]
        for item in fi:
            lines.append(f"| {item['feature']} | {item['importance']} |")

    lines += [
        "", "---", "", "## Governance", "",
        "```",
        "No production model changes.",
        "No scoring changes.",
        "No SP as predictive feature.",
        "Rolling horse memory: leakage-free (prior-only stats).",
        "```",
    ]
    md_path = OUT_DIR / "velo_model_arena_ablation_v2_latest.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"MD:   {md_path}")


if __name__ == "__main__":
    run()
