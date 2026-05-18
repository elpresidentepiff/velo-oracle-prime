#!/usr/bin/env python3.11
"""
Runner Master Shadow Daily Predictor — Step 6
==============================================
Score today's runners with Model C (rank ensemble).
Write daily shadow predictions and report.

Governance:
  NO_SCORING_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE
  NO_TELEGRAM_CHANGE | NO_LIVE_STATE_MUTATION

Mission Control footer:
  RUNNER_MASTER_SHADOW_MODEL_V1 = SHADOW_QUARANTINE
  BEST_MODEL = Model C Ensemble
  NO_SP_FEATURE = TRUE
  LIVE_USE = BLOCKED

Promotion gates (monitor only — do not act):
  300+ forward shadow runners
  75+ top-decile forward runners
  positive top-decile ROI after strip top winner
  beats VP baseline WR
  survives SP 3.0–8.5
  no top winner return concentration >25%

Usage:
  python runner_master_shadow_daily_predict.py [--date YYYY-MM-DD]
"""

import argparse
import json
import pickle
import warnings
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH   = ROOT / "data" / "features" / "runner_master_profile_latest.parquet"
MODEL_PATH     = ROOT / "data" / "models"   / "runner_master_shadow_model_v1.pkl"
SHADOW_DIR     = ROOT / "data" / "shadow"
REPORT_DIR     = ROOT / "data" / "reports"

SHADOW_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

GOVERNANCE = (
    "NO_SCORING_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE "
    "| NO_TELEGRAM_CHANGE | NO_LIVE_STATE_MUTATION"
)

MISSION_FOOTER = """\
RUNNER_MASTER_SHADOW_MODEL_V1 = SHADOW_QUARANTINE
BEST_MODEL                    = Model C Ensemble
NO_SP_FEATURE                 = TRUE
LIVE_USE                      = BLOCKED"""

PROMOTION_GATES = [
    "300+ forward shadow runners",
    "75+ top-decile forward runners",
    "positive top-decile ROI after strip top winner",
    "beats VP baseline WR in forward data",
    "survives SP 3.0–8.5 band",
    "no top winner return concentration >25%",
    "calibration not degraded",
]

# ─── Derivation helpers (must mirror build_runner_master_training_dataset.py) ─

_DIST_MIDPOINTS = {
    "5f": 5.0, "6f": 6.0, "7f": 7.0, "8f": 8.0,
    "9-10f": 9.5, "11-12f": 11.5, "13-14f": 13.5,
    "15-17f": 16.0, "18f+": 18.0,
}


def _dist_band_numeric(v) -> float | None:
    if pd.isna(v):
        return None
    return _DIST_MIDPOINTS.get(str(v).strip().lower())


def _race_type_flags(v) -> tuple[float, float]:
    t = str(v or "").lower()
    is_flat  = float("flat" in t)
    is_jumps = float(any(w in t for w in ("hurdle", "chase", "nh", "national hunt")))
    return is_flat, is_jumps


class _NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):  return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)):    return bool(obj)
        return super().default(obj)


# ─── Feature builder ──────────────────────────────────────────────────────────

def build_features(df: pd.DataFrame, tj_p80: float, impute_vals: dict,
                   feature_cols: list[str]) -> tuple[np.ndarray, pd.DataFrame]:
    """
    Derive features from runner_master_profile row layout.
    Returns (X array, enriched df with derived cols).
    """
    out = df.copy()

    # Derive is_flat, is_jumps
    flags = out["race_type"].apply(lambda v: _race_type_flags(v))
    out["is_flat"]  = [f[0] for f in flags]
    out["is_jumps"] = [f[1] for f in flags]

    # Derive dist_band_f
    out["dist_band_f"] = out["dist_band"].apply(_dist_band_numeric)

    # Derive TJ_HIGH_TODAY20
    out["_tj_high_today20"] = (
        out["trainer_jockey_sr"].notna() &
        (out["trainer_jockey_sr"] >= tj_p80)
    ).astype(float)

    # Missing feature tracker (count nulls across key predictive cols before imputation)
    pred_cols = ["velo_prime_prob", "trainer_jockey_sr", "ofr_api", "or_drop_from_peak",
                 "ts_slope_6", "or_slope_6", "rpr_slope_6", "ts_vs_or_gap",
                 "class_num", "field_size", "dist_band_f"]
    out["missing_feature_count"] = out[pred_cols].isna().sum(axis=1)
    out["data_quality_warning"] = out["missing_feature_count"].apply(
        lambda n: "HIGH_MISSING" if n >= 7 else ("PARTIAL_MISSING" if n >= 4 else "OK")
    )

    # Apply imputation
    raw_cols = {
        "velo_prime_prob": "velo_prime_prob",
        "trainer_jockey_sr": "trainer_jockey_sr",
        "ofr_api": "ofr_api",
        "or_drop_from_peak": "or_drop_from_peak",
        "ts_slope_6": "ts_slope_6",
        "or_slope_6": "or_slope_6",
        "rpr_slope_6": "rpr_slope_6",
        "ts_vs_or_gap": "ts_vs_or_gap",
        "class_num": "class_num",
        "is_flat": "is_flat",
        "is_jumps": "is_jumps",
        "field_size": "field_size",
        "mds_high_flag": "mds_high_flag",
        "dist_band_f": "dist_band_f",
        "_tj_high_today20": "_tj_high_today20",
    }

    X = pd.DataFrame(index=out.index)
    for feat in feature_cols:
        src = raw_cols.get(feat, feat)
        if src in out.columns:
            X[feat] = out[src].values
        else:
            X[feat] = np.nan

    # Bool to float
    X["mds_high_flag"] = X["mds_high_flag"].astype(float)

    # Impute
    for col, val in impute_vals.items():
        if col in X.columns:
            X[col] = X[col].fillna(val)
    X = X.fillna(0.0)

    return X[feature_cols].values, out


# ─── Accumulation counter ─────────────────────────────────────────────────────

def _count_accumulated_shadow(target_date_str: str) -> dict:
    """Scan shadow/ dir for all previous daily parquets, count total forward runners."""
    n_total = 0
    n_days  = 0
    for f in sorted(SHADOW_DIR.glob("runner_master_shadow_predictions_*.parquet")):
        fdate = f.stem.split("_")[-1]
        if fdate >= target_date_str:
            continue
        try:
            sub = pd.read_parquet(f)
            n_total += len(sub)
            n_days  += 1
        except Exception:
            pass
    return {"n_forward_runners": n_total, "n_forward_days": n_days}


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(target_date: str | None = None):
    today_str = target_date or str(date.today())
    print(f"Runner Master Shadow Daily Predictor — {today_str}")
    print(f"Governance: {GOVERNANCE}")
    print()

    # ── Load model ────────────────────────────────────────────────────────────
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
    with open(MODEL_PATH, "rb") as f:
        artifact = pickle.load(f)

    version      = artifact["version"]
    tj_p80       = artifact["tj_p80_train"]
    impute_vals  = artifact["impute_vals"]
    feature_cols = artifact["feature_cols"]
    model_a_info = artifact["model_a"]
    model_b_info = artifact["model_b"]

    scaler    = model_a_info["scaler"]
    lr_model  = model_a_info["model"]
    lgb_model = model_b_info["model"]

    print(f"Model: {version} (trained {artifact['trained_date']})")
    print(f"TJ_HIGH_TODAY20 threshold: {tj_p80:.4f}")
    print()

    # ── Load profile ──────────────────────────────────────────────────────────
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(f"Profile not found: {PROFILE_PATH}")
    full_df = pd.read_parquet(PROFILE_PATH)

    # Filter to target date
    today_df = full_df[full_df["date"] == today_str].copy().reset_index(drop=True)
    if len(today_df) == 0:
        # Try latest date as fallback
        latest_date = str(full_df["date"].max())
        print(f"WARNING: No rows for {today_str}. Falling back to latest date: {latest_date}")
        today_df = full_df[full_df["date"] == latest_date].copy().reset_index(drop=True)
        today_str = latest_date

    n_runners = len(today_df)
    print(f"Runners: {n_runners} | Date: {today_str}")

    # ── Build features ────────────────────────────────────────────────────────
    X, enriched = build_features(today_df, tj_p80, impute_vals, feature_cols)

    # ── Model C scores ────────────────────────────────────────────────────────
    X_scaled = scaler.transform(X)
    probs_a = lr_model.predict_proba(X_scaled)[:, 1]
    probs_b = lgb_model.predict(X)
    probs_c = (probs_a + probs_b) / 2.0

    enriched["shadow_score_a"] = probs_a
    enriched["shadow_score_b"] = probs_b
    enriched["shadow_score_c"] = probs_c

    # Per-race ranking — group by (course, off_time) since race_id is per-runner in this profile
    enriched["_race_group"] = enriched["course"].astype(str) + "|" + enriched["off_time"].astype(str)
    enriched["vp_rank"]     = enriched.groupby("_race_group")["velo_prime_prob"].rank(ascending=False, method="min").astype(int)
    enriched["shadow_rank"] = enriched.groupby("_race_group")["shadow_score_c"].rank(ascending=False, method="min").astype(int)
    enriched["rank_delta"]  = enriched["vp_rank"] - enriched["shadow_rank"]  # positive = shadow ranks higher

    n_races_grouped = enriched["_race_group"].nunique()

    # Top-decile threshold across all runners today
    top_decile_thresh = float(np.quantile(probs_c, 0.90)) if n_runners >= 10 else float(np.quantile(probs_c, 0.50))
    enriched["in_top_decile"] = enriched["shadow_score_c"] >= top_decile_thresh

    n_top_decile = int(enriched["in_top_decile"].sum())
    print(f"Race groups (course+time): {n_races_grouped} | Top-decile threshold: {top_decile_thresh:.4f} | Flagged: {n_top_decile} runners")

    # ── Save daily parquet ────────────────────────────────────────────────────
    save_cols = [
        "date", "race_id", "horse_id", "horse", "course", "off_time",
        "velo_prime_prob", "shadow_score_a", "shadow_score_b", "shadow_score_c",
        "vp_rank", "shadow_rank", "rank_delta", "in_top_decile",
        "_tj_high_today20", "trainer_jockey_sr", "ofr_api",
        "or_drop_from_peak", "ts_slope_6", "mds_high_flag",
        "missing_feature_count", "data_quality_warning",
    ]
    save_cols = [c for c in save_cols if c in enriched.columns]
    daily_parquet = SHADOW_DIR / f"runner_master_shadow_predictions_{today_str}.parquet"
    enriched[save_cols].to_parquet(daily_parquet, index=False)
    print(f"Daily parquet: {daily_parquet}")

    # ── Accumulation progress ─────────────────────────────────────────────────
    acc = _count_accumulated_shadow(today_str)
    acc_total   = acc["n_forward_runners"] + n_runners
    acc_days    = acc["n_forward_days"] + 1
    top_dec_est = int(acc_total * 0.10)
    gates_progress = {
        "300_runners":        acc_total >= 300,
        "75_top_decile_est":  top_dec_est >= 75,
        "n_forward_runners":  acc_total,
        "n_forward_days":     acc_days,
        "est_top_decile":     top_dec_est,
    }
    gates_open = sum(1 for v in [gates_progress["300_runners"],
                                  gates_progress["75_top_decile_est"]] if v)

    races = n_races_grouped

    # ── Build per-race output ─────────────────────────────────────────────────
    race_sections = []
    for race_id, race_df in enriched.sort_values(["off_time", "_race_group"]).groupby("_race_group", sort=False):
        race_df = race_df.sort_values("shadow_rank")
        row = {
            "race_id":  race_id,
            "course":   str(race_df["course"].iloc[0]) if "course" in race_df.columns else "",
            "off_time": str(race_df["off_time"].iloc[0]) if "off_time" in race_df.columns else "",
            "n_runners": len(race_df),
            "runners":  [],
        }
        for _, r in race_df.iterrows():
            tj_flag  = bool(r.get("_tj_high_today20", 0))
            mds_flag = bool(r.get("mds_high_flag", False))
            tj_sr    = r.get("trainer_jockey_sr")
            tj_sr_s  = f"{tj_sr:.3f}" if pd.notna(tj_sr) else "—"
            ofr      = r.get("ofr_api")
            ofr_s    = f"{ofr:.0f}" if pd.notna(ofr) else "—"
            or_drop  = r.get("or_drop_from_peak")
            or_drop_s = f"{or_drop:.1f}" if pd.notna(or_drop) else "—"
            ts_slope = r.get("ts_slope_6")
            ts_slope_s = f"{ts_slope:+.2f}" if pd.notna(ts_slope) else "—"
            row["runners"].append({
                "horse":          str(r.get("horse", "")),
                "shadow_rank":    int(r.get("shadow_rank", 0)),
                "vp_rank":        int(r.get("vp_rank", 0)),
                "rank_delta":     int(r.get("rank_delta", 0)),
                "shadow_score_c": round(float(r["shadow_score_c"]), 4),
                "velo_prime_prob":round(float(r["velo_prime_prob"]), 4),
                "in_top_decile":  bool(r.get("in_top_decile", False)),
                "tj_high_today20":tj_flag,
                "mds_high_flag":  mds_flag,
                "trainer_jockey_sr": tj_sr_s,
                "current_or":     ofr_s,
                "or_drop_from_peak": or_drop_s,
                "ts_slope_6":     ts_slope_s,
                "missing_features": int(r.get("missing_feature_count", 0)),
                "data_quality":   str(r.get("data_quality_warning", "OK")),
            })
        race_sections.append(row)

    # ── Data quality summary ──────────────────────────────────────────────────
    dq_counts = enriched["data_quality_warning"].value_counts().to_dict()
    dq_summary = {
        "OK":              int(dq_counts.get("OK", 0)),
        "PARTIAL_MISSING": int(dq_counts.get("PARTIAL_MISSING", 0)),
        "HIGH_MISSING":    int(dq_counts.get("HIGH_MISSING", 0)),
    }

    # ── JSON report ───────────────────────────────────────────────────────────
    report = {
        "generated":        str(datetime.now().isoformat(timespec="seconds")),
        "target_date":      today_str,
        "governance":       GOVERNANCE,
        "model_version":    version,
        "model_status":     artifact["status"],
        "n_runners":        n_runners,
        "n_races":          races,
        "top_decile_thresh": round(top_decile_thresh, 4),
        "n_top_decile":     n_top_decile,
        "data_quality":     dq_summary,
        "accumulation":     gates_progress,
        "races":            race_sections,
    }

    json_path = REPORT_DIR / "runner_master_shadow_daily_latest.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, cls=_NpEncoder)

    # ── Markdown report ───────────────────────────────────────────────────────
    lines = [
        f"# Runner Master Shadow — Daily Predictions",
        f"**Date:** {today_str}  ",
        f"**Model:** {version}  ",
        f"**Status:** {artifact['status']}",
        "",
        "---",
        "",
        f"## Summary",
        f"| | |",
        f"|---|---|",
        f"| Runners | {n_runners} |",
        f"| Races | {races} |",
        f"| Top-decile threshold | {top_decile_thresh:.4f} |",
        f"| Runners in top decile | {n_top_decile} |",
        f"| Data quality OK | {dq_summary['OK']} |",
        f"| Partial missing | {dq_summary['PARTIAL_MISSING']} |",
        f"| High missing | {dq_summary['HIGH_MISSING']} |",
        "",
        "---",
        "",
        "## Forward Shadow Progress",
        "| Gate | Status | Value |",
        "|---|---|---|",
        f"| 300+ forward runners | {'OPEN' if gates_progress['300_runners'] else 'LOCKED'} | {acc_total} |",
        f"| 75+ top-decile runners (est) | {'OPEN' if gates_progress['75_top_decile_est'] else 'LOCKED'} | ~{top_dec_est} |",
        f"| Days accumulated | — | {acc_days} |",
        "",
        "_Promotion gates are monitoring conditions only. No action permitted until operator review._",
        "",
        "---",
        "",
    ]

    # Per-race tables
    for race in race_sections:
        lines += [
            f"## {race['off_time']} — {race['course']} ({race['n_runners']} runners)",
            "",
            "| # | Horse | Shadow | VP | Δ rank | TJ★ | MDS★ | TJ SR | OR | OR drop | TS slope | Missing | DQ |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in race["runners"]:
            top_flag  = "★" if r["in_top_decile"] else ""
            tj_sym    = "✓" if r["tj_high_today20"] else ""
            mds_sym   = "✓" if r["mds_high_flag"] else ""
            delta_s   = f"{r['rank_delta']:+d}" if r["rank_delta"] != 0 else "="
            lines.append(
                f"| {r['shadow_rank']}{top_flag} | {r['horse']} "
                f"| {r['shadow_score_c']:.3f} | {r['velo_prime_prob']:.3f} "
                f"| {delta_s} | {tj_sym} | {mds_sym} "
                f"| {r['trainer_jockey_sr']} | {r['current_or']} "
                f"| {r['or_drop_from_peak']} | {r['ts_slope_6']} "
                f"| {r['missing_features']} | {r['data_quality']} |"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "## Mission Control",
        "```",
        MISSION_FOOTER,
        "```",
        "",
        "## Promotion Gates (all must be met — operator decision required)",
        "",
    ]
    for g in PROMOTION_GATES:
        lines.append(f"- [ ] {g}")

    lines += [
        "",
        f"**Governance:** {GOVERNANCE}",
        "",
        f"_Generated: {datetime.now().isoformat(timespec='seconds')}_",
    ]

    md_path = REPORT_DIR / "runner_master_shadow_daily_latest.md"
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    # ── Console summary ───────────────────────────────────────────────────────
    print()
    print("── Prediction summary ───────────────────────────────────────")
    for race in sorted(race_sections, key=lambda x: x["off_time"]):
        top_runners = [r for r in race["runners"] if r["in_top_decile"]]
        top_str = ", ".join(
            f"{r['horse']}(shadow={r['shadow_score_c']:.3f} vp={r['velo_prime_prob']:.3f} Δ{r['rank_delta']:+d})"
            for r in sorted(top_runners, key=lambda r: -r["shadow_score_c"])
        )
        print(f"  {race['off_time']} {race['course']:20} ★ {top_str or 'none in top decile'}")

    print()
    print(f"Forward progress: {acc_total} runners / {acc_days} days accumulated")
    print(f"Gate progress: {gates_open}/2 count gates met")
    print()
    print("── Mission Control ─────────────────────────────────────────")
    print(MISSION_FOOTER)
    print()
    print(f"JSON: {json_path.name}")
    print(f"MD:   {md_path.name}")
    print(f"Parquet: {daily_parquet.name}")
    print()
    print(f"Governance: {GOVERNANCE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Runner Master Shadow Daily Predictor")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD (default: today)")
    args = parser.parse_args()
    main(target_date=args.date)
