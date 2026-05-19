"""
VÉLØ Shadow Model Forward Gate Ledger

Tracks the best challenger (NO_VP_COMPOSITE logistic, win target) prospectively.
Applied to new races post-training-cutoff without retraining.

Hard rule: training cutoff is explicit and immutable per session.
The model loaded here was trained on data before TRAINING_CUTOFF_DATE.
Forward gate rows must have race_date > TRAINING_CUTOFF_DATE.

Outputs:
  data/reports/shadow_model_forward_gate_latest.json
  data/reports/shadow_model_forward_gate_latest.md
  data/reports/shadow_model_forward_gate_ledger.csv  (append-only)

Read-only with respect to scoring. Does not alter verdicts, weights, or routing.
"""

import json
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]

# ── Configuration ─────────────────────────────────────────────────────────────

# The training cutoff for the shadow model. All rows on or before this date
# were used in training. Forward gate rows must be strictly after this date.
TRAINING_CUTOFF_DATE = "2026-05-10"
SHADOW_MODEL_NAME = "NO_VP_COMPOSITE_logistic_win"
SHADOW_FEATURE_SET = "NO_VP_COMPOSITE"
SHADOW_FEATURES = [
    "sqpe_v17_prob", "market_deception_score", "improvement_score",
    "place_prob", "longshot_prob", "release_day_prob",
    "comment_intel_score", "confidence_level_encoded",
]

# Model paths — V2 preferred if available, V1 fallback
MODEL_PATH_V2 = ROOT / "models" / "shadow" / "model_arena_v2" / f"{SHADOW_MODEL_NAME}.pkl"
MODEL_PATH_V1 = ROOT / "models" / "shadow" / "model_arena" / "ablation" / f"{SHADOW_MODEL_NAME}.pkl"

# Data sources
CORPUS_PATH = ROOT / "data" / "velo_unified_evidence_corpus_v1.csv"
VERDICTS_PATH = ROOT / "data" / "features" / "rp_runner_profile_latest.parquet"

# Outputs
OUT_JSON = ROOT / "data" / "reports" / "shadow_model_forward_gate_latest.json"
OUT_MD = ROOT / "data" / "reports" / "shadow_model_forward_gate_latest.md"
OUT_LEDGER = ROOT / "data" / "reports" / "shadow_model_forward_gate_ledger.csv"
OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

CONF_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

# Promotion gates
GATE_MIN_RUNNERS = 300
GATE_MIN_TOP_DECILE = 75


# ── Load model ────────────────────────────────────────────────────────────────

def load_shadow_model():
    import pickle
    for path in (MODEL_PATH_V2, MODEL_PATH_V1):
        if path.exists():
            with open(path, "rb") as f:
                return pickle.load(f), str(path)
    return None, None


# ── Load forward data ─────────────────────────────────────────────────────────

def load_forward_corpus() -> pd.DataFrame:
    """Load rows strictly after training cutoff."""
    df = pd.read_csv(CORPUS_PATH)
    df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
    # Forward rows: after training cutoff, result_matched=True
    forward = df[
        (df["date_parsed"] > pd.Timestamp(TRAINING_CUTOFF_DATE))
        & (df["result_matched"] == True)
    ].copy()
    forward["confidence_level_encoded"] = (
        forward["confidence_level"].map(CONF_MAP).fillna(1))
    return forward.sort_values("date_parsed").reset_index(drop=True)


def encode_features(df: pd.DataFrame) -> np.ndarray:
    cols = []
    for f in SHADOW_FEATURES:
        if f in df.columns:
            cols.append(pd.to_numeric(df[f], errors="coerce").values.reshape(-1, 1))
        else:
            cols.append(np.full((len(df), 1), np.nan))
    return np.hstack(cols)


def encode_target(col: pd.Series) -> np.ndarray:
    return col.apply(
        lambda x: 1 if str(x).lower() in ("true", "1", "1.0") else 0).values


# ── Metrics ───────────────────────────────────────────────────────────────────

def compute_metrics(y: np.ndarray, probs: np.ndarray,
                    sp: np.ndarray | None = None) -> dict:
    if len(y) == 0:
        return {}
    metrics = {}
    metrics["brier"] = round(brier_score_loss(y, probs), 6)
    if 0 < y.sum() < len(y):
        metrics["auc"] = round(roc_auc_score(y, probs), 6)
    # SR by top decile
    top_decile_thresh = np.quantile(probs, 0.90)
    top_mask = probs >= top_decile_thresh
    metrics["top_decile_n"] = int(top_mask.sum())
    metrics["top_decile_sr"] = round(float(y[top_mask].mean()), 4) if top_mask.sum() > 0 else None
    # ROI
    if sp is not None:
        valid = ~np.isnan(sp)
        y_v, sp_v = y[valid], sp[valid]
        if len(y_v) > 0:
            winners = y_v == 1
            metrics["roi_full"] = round(
                (float(sp_v[winners].sum()) - len(y_v)) / len(y_v), 4)
        top_valid = top_mask & valid
        if top_valid.sum() > 0:
            y_t, sp_t = y[top_valid], sp[top_valid]
            winners_t = y_t == 1
            metrics["roi_top_decile"] = round(
                (float(sp_t[winners_t].sum()) - len(y_t)) / len(y_t), 4)
    return metrics


def decile_sr(y: np.ndarray, probs: np.ndarray) -> list[dict]:
    d = pd.DataFrame({"p": probs, "y": y})
    try:
        d["decile"] = pd.qcut(d["p"], 10, labels=False, duplicates="drop")
    except Exception:
        return []
    return [{"decile": int(dec), "n": len(g), "sr": round(g["y"].mean(), 4),
              "avg_prob": round(g["p"].mean(), 4)}
            for dec, g in d.groupby("decile")]


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print("\nSHADOW MODEL FORWARD GATE")
    print("=" * 60)
    print(f"Shadow model:      {SHADOW_MODEL_NAME}")
    print(f"Training cutoff:   {TRAINING_CUTOFF_DATE}")
    print(f"Promotion gate:    n≥{GATE_MIN_RUNNERS} runners, n≥{GATE_MIN_TOP_DECILE} top-decile")

    model, model_path = load_shadow_model()
    if model is None:
        print("ERROR: Shadow model not found. Run train_velo_model_arena_v2.py first.")
        return

    print(f"Model loaded from: {model_path}")

    forward_df = load_forward_corpus()
    print(f"Forward rows (post-{TRAINING_CUTOFF_DATE}): {len(forward_df)}")

    if len(forward_df) == 0:
        print("No forward data yet. Gate ledger initialized at zero.")
        _write_empty_gate()
        return

    X_forward = encode_features(forward_df)
    y_win = encode_target(forward_df["won"])
    y_frame = encode_target(forward_df["placed"])
    sp = pd.to_numeric(forward_df.get("sp_decimal", pd.Series(dtype=float)),
                       errors="coerce").values

    # SQPE comparison (same forward window)
    sqpe_probs = pd.to_numeric(forward_df.get("sqpe_v17_prob", pd.Series(dtype=float)),
                                errors="coerce").values
    sqpe_ok = ~np.isnan(sqpe_probs)

    # Shadow model predictions
    challenger_probs = model.predict_proba(X_forward)[:, 1]

    # Win metrics
    win_metrics = compute_metrics(y_win, challenger_probs, sp)
    win_sr_decile = decile_sr(y_win, challenger_probs)
    sqpe_win_brier = (brier_score_loss(y_win[sqpe_ok], sqpe_probs[sqpe_ok])
                      if sqpe_ok.sum() > 5 else None)

    # Frame metrics (challenger used to rank, frame as target)
    frame_metrics = compute_metrics(y_frame, challenger_probs)

    # Delta vs SQPE
    brier_delta = None
    if sqpe_win_brier and win_metrics.get("brier"):
        brier_delta = round(win_metrics["brier"] - sqpe_win_brier, 6)

    # Gate status
    n_runners = len(forward_df)
    top_decile_n = win_metrics.get("top_decile_n", 0)
    gate_runners_met = n_runners >= GATE_MIN_RUNNERS
    gate_top_decile_met = top_decile_n >= GATE_MIN_TOP_DECILE
    beats_sqpe_forward = (brier_delta is not None and brier_delta < 0)

    gate_status = "GATE_OPEN_ACCUMULATING"
    if gate_runners_met and gate_top_decile_met:
        if beats_sqpe_forward:
            gate_status = "GATE_MET_REVIEW_REQUIRED"
        else:
            gate_status = "GATE_MET_CHALLENGER_FAILS"

    print(f"\nForward results (n={n_runners}):")
    print(f"  Challenger Brier:   {win_metrics.get('brier')}")
    print(f"  SQPE Brier:         {sqpe_win_brier}")
    print(f"  Delta:              {brier_delta}")
    print(f"  Top-decile SR:      {win_metrics.get('top_decile_sr')}")
    print(f"  Top-decile n:       {top_decile_n}")
    print(f"  Gate status:        {gate_status}")
    print(f"  Runners until gate: {max(0, GATE_MIN_RUNNERS - n_runners)}")

    # Append-only ledger row
    ledger_row = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "model": SHADOW_MODEL_NAME,
        "training_cutoff": TRAINING_CUTOFF_DATE,
        "n_forward_runners": n_runners,
        "challenger_brier_win": win_metrics.get("brier"),
        "sqpe_brier_win": sqpe_win_brier,
        "brier_delta": brier_delta,
        "challenger_auc": win_metrics.get("auc"),
        "top_decile_n": top_decile_n,
        "top_decile_sr": win_metrics.get("top_decile_sr"),
        "roi_full": win_metrics.get("roi_full"),
        "roi_top_decile": win_metrics.get("roi_top_decile"),
        "frame_brier": frame_metrics.get("brier"),
        "frame_auc": frame_metrics.get("auc"),
        "beats_sqpe_forward": beats_sqpe_forward,
        "gate_runners_met": gate_runners_met,
        "gate_top_decile_met": gate_top_decile_met,
        "gate_status": gate_status,
    }

    # Append to ledger
    if OUT_LEDGER.exists():
        existing = pd.read_csv(OUT_LEDGER)
        new_ledger = pd.concat([existing, pd.DataFrame([ledger_row])], ignore_index=True)
    else:
        new_ledger = pd.DataFrame([ledger_row])
    new_ledger.to_csv(OUT_LEDGER, index=False)
    print(f"Ledger: {OUT_LEDGER} ({len(new_ledger)} rows)")

    # JSON snapshot
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "shadow_model": SHADOW_MODEL_NAME,
        "feature_set": SHADOW_FEATURE_SET,
        "features": SHADOW_FEATURES,
        "training_cutoff": TRAINING_CUTOFF_DATE,
        "n_forward_runners": n_runners,
        "gate": {
            "status": gate_status,
            "runners_needed": GATE_MIN_RUNNERS,
            "top_decile_needed": GATE_MIN_TOP_DECILE,
            "runners_to_gate": max(0, GATE_MIN_RUNNERS - n_runners),
            "top_decile_to_gate": max(0, GATE_MIN_TOP_DECILE - top_decile_n),
            "runners_met": gate_runners_met,
            "top_decile_met": gate_top_decile_met,
        },
        "win_metrics": win_metrics,
        "sqpe_win_brier": sqpe_win_brier,
        "brier_delta_vs_sqpe": brier_delta,
        "beats_sqpe_forward": beats_sqpe_forward,
        "frame_metrics": frame_metrics,
        "win_sr_by_decile": win_sr_decile,
        "governance": {
            "no_scoring_change": True,
            "no_production_promotion": True,
            "training_cutoff_immutable": True,
            "forward_data_only": True,
        },
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"JSON: {OUT_JSON}")
    _write_md(summary)
    print(f"MD:   {OUT_MD}")
    print("=" * 60)


def _write_empty_gate():
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "shadow_model": SHADOW_MODEL_NAME,
        "training_cutoff": TRAINING_CUTOFF_DATE,
        "n_forward_runners": 0,
        "gate": {
            "status": "GATE_OPEN_ACCUMULATING",
            "runners_needed": GATE_MIN_RUNNERS,
            "top_decile_needed": GATE_MIN_TOP_DECILE,
            "runners_to_gate": GATE_MIN_RUNNERS,
        },
        "governance": {"no_scoring_change": True, "no_production_promotion": True},
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_md(summary)


def _write_md(summary: dict) -> None:
    gate = summary.get("gate", {})
    n = summary.get("n_forward_runners", 0)
    status = gate.get("status", "GATE_OPEN_ACCUMULATING")
    wm = summary.get("win_metrics", {})
    sqpe_b = summary.get("sqpe_win_brier")
    delta = summary.get("brier_delta_vs_sqpe")

    lines = [
        "# VÉLØ SHADOW MODEL FORWARD GATE",
        "",
        f"**Run at:** {summary['run_at']}  ",
        f"**Model:** {summary.get('shadow_model', '?')}  ",
        f"**Training cutoff:** {summary.get('training_cutoff')}  ",
        f"**Gate status:** `{status}`",
        "",
        "---",
        "",
        "## Gate Progress",
        "",
        f"| Gate | Required | Current | Met |",
        f"|---|---|---|---|",
        f"| Total runners | {gate.get('runners_needed', 300)} | {n} | "
        f"{'YES' if gate.get('runners_met') else 'NO'} |",
        f"| Top-decile runners | {gate.get('top_decile_needed', 75)} | "
        f"{wm.get('top_decile_n', 0)} | "
        f"{'YES' if gate.get('top_decile_met') else 'NO'} |",
        f"| Beats SQPE on forward | yes | {'YES' if summary.get('beats_sqpe_forward') else 'NO'} | "
        f"{'YES' if summary.get('beats_sqpe_forward') else 'NO'} |",
        "",
        "---",
        "",
        "## Forward Metrics",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Forward runners | {n} |",
        f"| Challenger Brier (win) | {wm.get('brier', 'n/a')} |",
        f"| SQPE Brier (same window) | {sqpe_b} |",
        f"| Brier delta | {delta} |",
        f"| Challenger AUC | {wm.get('auc', 'n/a')} |",
        f"| Top-decile SR | {wm.get('top_decile_sr', 'n/a')} |",
        f"| ROI (full) | {wm.get('roi_full', 'n/a')} |",
        f"| ROI (top decile) | {wm.get('roi_top_decile', 'n/a')} |",
        "",
        "---",
        "",
        "## Promotion Gate Rules (see VELO_CPU_SHADOW_MODEL_PROTOCOL_V1.md)",
        "",
        "1. Beats SQPE Brier on forward 300 runners",
        "2. Improves win SR by decile vs naive",
        "3. Does not degrade frame layer",
        "4. Positive or neutral ROI after outlier stripping",
        "5. No subgroup collapse",
        "6. Reproducible training",
        "7. No Sentinel violations",
        "8. Human approval required",
        "",
        "---",
        "",
        "## Governance",
        "",
        "```",
        "No scoring change. No production promotion.",
        "Training cutoff immutable. Forward data only.",
        "Gate requires operator approval at every threshold.",
        "```",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
