"""
VÉLØ Model Arena Ablation V1 — answers the meta-calibrator question.

Three feature sets tested:
  FULL_META        — includes velo_prime_prob (same as arena run 1)
  NO_VP_COMPOSITE  — excludes velo_prime_prob and decision_tier; raw sidecars only
  NO_VP_NO_MARKET  — excludes VP, tier, and market-derived signals (MDS, place_prob,
                     longshot_prob); pure pre-race structural signal only

Classification:
  META_CALIBRATOR_PROMISING  — beats baseline only with VP present
  INDEPENDENT_MODEL_PROMISING — beats baseline without VP (real independent signal)
  CURRENT_STACK_BEATS_ALL    — model cannot improve on stack
  MORE_DATA_REQUIRED         — AUC too unstable, sample too small

Outputs:
  data/reports/velo_model_arena_ablation_latest.json
  data/reports/velo_model_arena_ablation_latest.md

Hard rules: no production changes, no scoring changes, no SP as predictive feature.
"""

import json
import pickle
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

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
OUT_DIR = ROOT / "data" / "reports"
MODEL_DIR = ROOT / "models" / "shadow" / "model_arena" / "ablation"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ── Feature sets ──────────────────────────────────────────────────────────────

FEATURE_SETS = {
    "FULL_META": [
        "velo_prime_prob",          # VP composite — includes SQPE + sidecars
        "sqpe_v17_prob",
        "market_deception_score",
        "improvement_score",
        "place_prob",
        "longshot_prob",
        "release_day_prob",
        "comment_intel_score",
        "decision_tier_encoded",    # derived from VP
        "confidence_level_encoded",
    ],
    "NO_VP_COMPOSITE": [
        # No velo_prime_prob, no decision_tier (VP-derived)
        "sqpe_v17_prob",
        "market_deception_score",
        "improvement_score",
        "place_prob",
        "longshot_prob",
        "release_day_prob",
        "comment_intel_score",
        "confidence_level_encoded",
    ],
    "NO_VP_NO_MARKET": [
        # No VP, no tier, no market-derived signals (MDS, place_prob, longshot)
        # Pure pre-race structural signal
        "sqpe_v17_prob",
        "improvement_score",
        "release_day_prob",
        "comment_intel_score",
    ],
}

TIER_MAP = {"A": 0, "B": 1, "C": 2, "X": 3}
CONF_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

TARGETS = {"win": "won", "frame": "placed"}


# ── Data loading ──────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    df = pd.read_csv(CORPUS_PATH)
    safe = df[df["result_matched"] == True].copy()
    safe = safe[safe["identity_unresolved"] == False].copy()
    safe = safe[safe["date"] != "2026-05-18"].copy()
    safe["date_parsed"] = pd.to_datetime(safe["date"], errors="coerce")
    safe = safe.dropna(subset=["date_parsed"]).sort_values("date_parsed").reset_index(drop=True)
    # Encode categoricals
    safe["decision_tier_encoded"] = safe["decision_tier"].map(TIER_MAP).fillna(1)
    safe["confidence_level_encoded"] = safe["confidence_level"].map(CONF_MAP).fillna(1)
    return safe


def encode_target(col: pd.Series) -> np.ndarray:
    return col.apply(lambda x: 1 if str(x).lower() in ("true", "1", "1.0") else 0).values


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

def calibration_summary(y_true: np.ndarray, probs: np.ndarray, n_bins: int = 5) -> list[dict]:
    fraction_pos, mean_pred = calibration_curve(y_true, probs, n_bins=n_bins, strategy="quantile")
    return [
        {"bin": i, "mean_pred": round(float(mean_pred[i]), 4), "fraction_pos": round(float(fraction_pos[i]), 4)}
        for i in range(len(mean_pred))
    ]


def decile_metrics(probs: np.ndarray, labels: np.ndarray, sp: np.ndarray | None = None) -> list[dict]:
    df = pd.DataFrame({"p": probs, "y": labels})
    if sp is not None:
        df["sp"] = sp
    df["decile"] = pd.qcut(df["p"], 10, labels=False, duplicates="drop")
    rows = []
    for d, grp in df.groupby("decile"):
        row = {"decile": int(d), "n": len(grp), "sr": round(grp["y"].mean(), 4), "avg_prob": round(grp["p"].mean(), 4)}
        if "sp" in df.columns:
            winners = grp[grp["y"] == 1]
            ret = float(winners["sp"].sum()) if len(winners) > 0 else 0.0
            row["roi"] = round((ret - len(grp)) / len(grp), 4) if len(grp) > 0 else None
        rows.append(row)
    return rows


def compute_roi(labels: np.ndarray, sp: np.ndarray | None, strip: float = 0.0) -> float | None:
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


# ── Models ────────────────────────────────────────────────────────────────────

def make_logistic() -> Pipeline:
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("clf", CalibratedClassifierCV(LogisticRegression(max_iter=1000, C=1.0), cv=3, method="isotonic")),
    ])


def make_rf() -> Pipeline:
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("clf", RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42, n_jobs=-1)),
    ])


def make_lgbm() -> Pipeline | None:
    try:
        from lightgbm import LGBMClassifier
        return Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("clf", LGBMClassifier(n_estimators=300, learning_rate=0.05, max_depth=5,
                                   num_leaves=20, min_child_samples=25, random_state=42,
                                   n_jobs=-1, verbose=-1)),
        ])
    except ImportError:
        return None


MODELS = {"logistic": make_logistic, "random_forest": make_rf, "lightgbm": make_lgbm}


# ── Classification ────────────────────────────────────────────────────────────

def classify(feature_set: str, brier: float, sqpe_brier: float, n_val: int) -> str:
    if n_val < 50:
        return "MORE_DATA_REQUIRED"
    beats_sqpe = brier < sqpe_brier
    if feature_set == "FULL_META" and beats_sqpe:
        return "META_CALIBRATOR_PROMISING"
    if feature_set in ("NO_VP_COMPOSITE", "NO_VP_NO_MARKET") and beats_sqpe:
        return "INDEPENDENT_MODEL_PROMISING"
    return "CURRENT_STACK_BEATS_ALL"


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print("\nVÉLØ MODEL ARENA ABLATION V1")
    print("=" * 60)

    df = load_data()
    train_df, val_df = time_split(df)
    val_split_date = str(val_df["date_parsed"].min().date())
    print(f"Train: {len(train_df)} | Val: {len(val_df)} | Split: {val_split_date}")

    # SP for ROI (train-side not needed)
    sp_val = pd.to_numeric(val_df.get("sp_decimal", pd.Series()), errors="coerce").values

    # SQPE baseline brier
    sqpe_val = pd.to_numeric(val_df.get("sqpe_v17_prob", pd.Series()), errors="coerce")
    y_val_win = encode_target(val_df["won"])
    sqpe_ok = sqpe_val.notna().values
    sqpe_brier_win = brier_score_loss(y_val_win[sqpe_ok], sqpe_val.values[sqpe_ok]) if sqpe_ok.sum() > 10 else 0.25
    print(f"SQPE baseline Brier (win): {sqpe_brier_win:.6f}")
    print(f"Val class balance (win): {y_val_win.mean():.3f}")

    all_results = []

    for target_name, target_col in TARGETS.items():
        y_train = encode_target(train_df[target_col])
        y_val = encode_target(val_df[target_col])

        for fs_name, feature_list in FEATURE_SETS.items():
            print(f"\n── {fs_name} / {target_name} ({len(feature_list)} features) ──")

            X_train = encode_features(train_df, feature_list)
            X_val = encode_features(val_df, feature_list)

            for model_name, factory in MODELS.items():
                pipeline = factory()
                if pipeline is None:
                    print(f"  SKIP {model_name} — not installed")
                    continue

                try:
                    print(f"  {model_name}...", end=" ", flush=True)
                    pipeline.fit(X_train, y_train)
                    probs = pipeline.predict_proba(X_val)[:, 1]

                    brier = brier_score_loss(y_val, probs)
                    ll = log_loss(y_val, probs)
                    auc = roc_auc_score(y_val, probs) if 0 < y_val.sum() < len(y_val) else None
                    cal = calibration_summary(y_val, probs)
                    deciles = decile_metrics(probs, y_val, sp_val if target_name == "win" else None)
                    roi = compute_roi(y_val, sp_val if target_name == "win" else None)
                    roi_s = compute_roi(y_val, sp_val if target_name == "win" else None, strip=0.05)
                    cls = classify(fs_name, brier, sqpe_brier_win, len(y_val))

                    auc_str = f"{auc:.4f}" if auc is not None else "n/a"
                    print(f"Brier={brier:.6f} AUC={auc_str} → {cls}")

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
                        "auc": round(auc, 6) if auc else None,
                        "roi_full": roi,
                        "roi_outlier_stripped": roi_s,
                        "calibration": cal,
                        "decile_metrics": deciles,
                        "classification": cls,
                    })

                except Exception as exc:
                    print(f"ERROR: {exc}")
                    all_results.append({
                        "feature_set": fs_name, "model": model_name, "target": target_name,
                        "error": str(exc), "brier_score": None, "classification": "ERROR",
                    })

    # Summary table
    print("\n" + "=" * 60)
    print("ABLATION SUMMARY (win target)")
    print(f"{'Feature Set':<22} {'Model':<15} {'Brier':>8} {'AUC':>7} {'Classification'}")
    print("-" * 80)
    for r in all_results:
        if r.get("target") != "win" or not r.get("brier_score"):
            continue
        print(f"{r['feature_set']:<22} {r['model']:<15} {r['brier_score']:>8.6f} "
              f"{str(r.get('auc','n/a'))[:7]:>7} {r['classification']}")

    print("\n(frame target)")
    for r in all_results:
        if r.get("target") != "frame" or not r.get("brier_score"):
            continue
        print(f"{r['feature_set']:<22} {r['model']:<15} {r['brier_score']:>8.6f} "
              f"{str(r.get('auc','n/a'))[:7]:>7} {r['classification']}")

    # Key verdict
    full_meta_best = min(
        (r["brier_score"] for r in all_results if r.get("feature_set") == "FULL_META" and r.get("target") == "win" and r.get("brier_score")),
        default=None
    )
    no_vp_best = min(
        (r["brier_score"] for r in all_results if r.get("feature_set") == "NO_VP_COMPOSITE" and r.get("target") == "win" and r.get("brier_score")),
        default=None
    )
    no_vp_no_mkt_best = min(
        (r["brier_score"] for r in all_results if r.get("feature_set") == "NO_VP_NO_MARKET" and r.get("target") == "win" and r.get("brier_score")),
        default=None
    )

    print("\nKEY VERDICT:")
    print(f"  SQPE baseline Brier:      {sqpe_brier_win:.6f}")
    print(f"  FULL_META best Brier:     {full_meta_best}")
    print(f"  NO_VP_COMPOSITE best:     {no_vp_best}")
    print(f"  NO_VP_NO_MARKET best:     {no_vp_no_mkt_best}")

    if no_vp_best and no_vp_best < sqpe_brier_win:
        print("\n  → INDEPENDENT_MODEL_PROMISING: real signal beyond VP recalibration")
    elif no_vp_best and full_meta_best and no_vp_best < full_meta_best * 1.02:
        print("\n  → BORDERLINE: near-equivalent. More data needed to confirm.")
    else:
        print("\n  → META_CALIBRATOR_ONLY: challengers depend on VP for their edge")

    arena = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "val_split_date": val_split_date,
        "n_train": len(train_df),
        "n_val": len(val_df),
        "sqpe_baseline_brier_win": round(sqpe_brier_win, 6),
        "feature_sets": {k: v for k, v in FEATURE_SETS.items()},
        "results": all_results,
        "key_verdict": {
            "full_meta_best_brier": full_meta_best,
            "no_vp_composite_best_brier": no_vp_best,
            "no_vp_no_market_best_brier": no_vp_no_mkt_best,
            "sqpe_baseline": round(sqpe_brier_win, 6),
            "independent_signal_confirmed": bool(no_vp_best and no_vp_best < sqpe_brier_win),
        },
        "governance": {
            "no_production_change": True, "no_scoring_change": True,
            "no_sp_as_predictive_feature": True,
        },
    }

    # Write outputs
    json_path = OUT_DIR / "velo_model_arena_ablation_latest.json"
    json_path.write_text(json.dumps(arena, indent=2), encoding="utf-8")
    print(f"\nJSON: {json_path}")
    _write_md(arena)

    return arena


def _write_md(arena: dict) -> None:
    kv = arena["key_verdict"]
    rows_win = [r for r in arena["results"] if r.get("target") == "win" and r.get("brier_score")]
    rows_frame = [r for r in arena["results"] if r.get("target") == "frame" and r.get("brier_score")]
    sqpe = arena["sqpe_baseline_brier_win"]

    def _cls_icon(cls: str) -> str:
        return {"INDEPENDENT_MODEL_PROMISING": "✓", "META_CALIBRATOR_PROMISING": "~",
                "CURRENT_STACK_BEATS_ALL": "✗", "MORE_DATA_REQUIRED": "?"}.get(cls, "?")

    lines = [
        "# VÉLØ MODEL ARENA ABLATION V1",
        "",
        f"**Run at:** {arena['run_at']}  ",
        f"**Train:** {arena['n_train']} | **Val:** {arena['n_val']} | **Split:** {arena['val_split_date']}  ",
        f"**SQPE baseline Brier (win):** {sqpe}",
        "",
        "---",
        "",
        "## Win Target",
        "",
        f"| Feature Set | Model | Brier ↓ | AUC ↑ | ROI | Classification |",
        f"|---|---|---|---|---|---|",
    ]
    for r in rows_win:
        lines.append(
            f"| {r['feature_set']} | {r['model']} | **{r['brier_score']}** | "
            f"{r.get('auc','n/a')} | {r.get('roi_full','n/a')} | "
            f"{_cls_icon(r['classification'])} {r['classification']} |"
        )

    lines += ["", f"*SQPE baseline: {sqpe}*", "", "---", "", "## Frame Target", "",
              "| Feature Set | Model | Brier ↓ | AUC ↑ | Classification |",
              "|---|---|---|---|---|"]
    for r in rows_frame:
        lines.append(
            f"| {r['feature_set']} | {r['model']} | **{r['brier_score']}** | "
            f"{r.get('auc','n/a')} | {_cls_icon(r['classification'])} {r['classification']} |"
        )

    ind = kv["independent_signal_confirmed"]
    lines += [
        "", "---", "", "## Key Verdict",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| SQPE baseline Brier | {sqpe} |",
        f"| FULL_META best | {kv['full_meta_best_brier']} |",
        f"| NO_VP_COMPOSITE best | {kv['no_vp_composite_best_brier']} |",
        f"| NO_VP_NO_MARKET best | {kv['no_vp_no_market_best_brier']} |",
        f"| **Independent signal confirmed** | **{'YES' if ind else 'NO'}** |",
        "",
        "---",
        "",
        "## Governance",
        "",
        "```",
        "No production model changes.",
        "No scoring changes.",
        "No SP as predictive feature.",
        "```",
    ]

    md_path = OUT_DIR / "velo_model_arena_ablation_latest.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"MD:   {md_path}")


if __name__ == "__main__":
    run()
