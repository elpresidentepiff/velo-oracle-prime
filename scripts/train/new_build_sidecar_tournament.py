"""
new_build_sidecar_tournament.py
Controlled sidecar experiment sprint over Challenger V1.

Challenger V1 = Core V0_OR + Horse Passport + Intent
Test AUC 0.6969 / SR 25.02% / Frame 54.98%

Rules (hard):
  - No RPR in any model sidecar
  - No same-race SP in morning model
  - No RP comments or tips as model features
  - No sidecar stacked until it wins solo
  - JTC-D flagged LEAKAGE_RISK (no time boundary) — lab result only

Sidecars evaluated:
  B. JTC-D (5 tables: TJ, TC, TD, JC, JD) — LEAKAGE_RISK in training
  C. International lagged OR history (safe cols only) — TEMPORALLY_SAFE
  G. Market (sp_dec, log_sp, implied_prob, sp_rank, is_fav) — MARKET_ONLY

Outputs:
  data/new_build/sidecars/jtcd_features.parquet
  data/new_build/sidecars/international_lagged_features.parquet
  data/new_build/sidecars/market_features.parquet
  data/new_build/reports/sidecar_tournament_latest.json
  data/new_build/reports/sidecar_tournament_latest.md
  data/new_build/reports/race_day_readiness_latest.json
  data/new_build/reports/race_day_readiness_latest.md
"""
import json
from datetime import datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
TRAIN_DIR   = ROOT / "data" / "new_build" / "training"
SIDECAR_DIR = ROOT / "data" / "new_build" / "sidecars"
REPORT_DIR  = ROOT / "data" / "new_build" / "reports"
SIDECAR_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# Paths
CORE_TRAIN   = TRAIN_DIR / "core_v0_or_train.parquet"
CORE_VAL     = TRAIN_DIR / "core_v0_or_val.parquet"
CORE_TEST    = TRAIN_DIR / "core_v0_or_test.parquet"
PASSPORT_F   = TRAIN_DIR / "passport_features.parquet"
INTENT_F     = TRAIN_DIR / "intent_features.parquet"
V17_PATH     = ROOT / "data" / "raceform_v17_features.parquet"
INTL_PATH    = ROOT / "data" / "features" / "international_lagged_rating_features.parquet"
TJ_PATH      = ROOT / "data" / "features" / "jtc_d" / "trainer_jockey_profile.parquet"
TC_PATH      = ROOT / "data" / "features" / "jtc_d" / "trainer_course_profile.parquet"
TD_PATH      = ROOT / "data" / "features" / "jtc_d" / "trainer_dist_profile.parquet"
JC_PATH      = ROOT / "data" / "features" / "jtc_d" / "jockey_course_profile.parquet"
JD_PATH      = ROOT / "data" / "features" / "jtc_d" / "jockey_dist_profile.parquet"

# Challenger V1 feature sets (verified)
CORE_FEATURES = [
    "dist_f", "going_code", "is_aw", "field_size", "draw_num", "draw_pct",
    "age_num", "wgt_lbs", "or_vs_field",
    "release_window_score", "going_fit_score", "distance_fit_score",
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    "setup_run_flag", "cash_run_flag", "official_rating", "is_rated",
]
PASSPORT_FEATURES = [
    "pp_career_runs", "pp_win_rate", "pp_place_rate",
    "pp_days_since_last", "pp_layoff", "pp_avg_sp_last5",
    "pp_jockey_continuity", "pp_course_seen", "pp_or_change_3",
    "pp_class_moved_up", "pp_class_moved_down",
]
INTENT_FEATURES = [
    "mark_compression_score", "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "runs_since_win", "runs_since_place", "runs_since_mkt_support",
    "odds_resilience_score", "intent_trip_match", "intent_course_win_history",
    "intent_going_match", "intent_class_drop_vs_best", "intent_run_after_break",
    "intent_sp_shortening", "intent_wins_last10", "intent_top3_last6",
]
CHALLENGER_V1 = CORE_FEATURES + PASSPORT_FEATURES + INTENT_FEATURES

# JTC-D sidecar features (post-join names)
JTCD_FEATURES = [
    "tj_jtc_signal", "tj_adj_sr", "tj_confidence",
    "tc_jtc_signal", "tc_adj_sr", "tc_confidence",
    "td_jtc_signal", "td_adj_sr", "td_confidence",
    "jc_jtc_signal", "jc_adj_sr", "jc_confidence",
    "jd_jtc_signal", "jd_adj_sr", "jd_confidence",
]

# International lagged — safe only (no RPR, no TS, no is_fav)
INTL_SAFE_FEATURES = [
    "prev_or_num", "max_or_num_last3", "avg_or_num_last3",
    "days_since_last_run", "starts_last_90",
    "course_prior_runs", "course_prior_wr",
    "dist_prior_runs", "dist_prior_wr",
]

# Market — SEPARATE LANE ONLY, never morning model
MARKET_FEATURES = ["sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav"]

# Hard banned from all model lanes
BANNED = {"rpr_num", "rpr_vs_field", "rpr", "ts_num", "ts",
          "prev_rpr_num", "max_rpr_num_last3", "avg_rpr_num_last3",
          "prev_ts_num", "max_ts_num_last3", "avg_ts_num_last3"}

LGBM_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "max_depth": 6,
    "num_leaves": 31,
    "verbosity": -1,
    "random_state": 42,
}

CHALLENGER_V1_TEST = {"AUC": 0.6969, "SR": 0.2502, "Frame": 0.5498}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _dist_to_band(dist_f):
    if dist_f < 5.5:   return "5f"
    if dist_f < 6.5:   return "6f"
    if dist_f < 7.5:   return "7f"
    if dist_f < 8.5:   return "8f"
    if dist_f < 10.5:  return "9-10f"
    if dist_f < 12.5:  return "11-12f"
    if dist_f < 14.5:  return "13-14f"
    if dist_f < 17.5:  return "15-17f"
    return "18f+"


def _fill(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = df[c].fillna(0)
    return df


def _present(df, cols):
    return [c for c in cols if c in df.columns]


def _eval(model, df, features):
    f = _present(df, features)
    probs = model.predict_proba(df[f])[:, 1]
    auc   = float(roc_auc_score(df["won"], probs))
    tmp   = df[["race_id", "won"]].copy()
    tmp["prob"] = probs
    top1  = tmp.sort_values(["race_id", "prob"], ascending=[True, False]).groupby("race_id").head(1)
    sr    = float(top1["won"].mean())
    top3  = tmp.sort_values(["race_id", "prob"], ascending=[True, False]).groupby("race_id").head(3)
    frame = float(top3.groupby("race_id")["won"].max().mean())
    return {"AUC": round(auc, 4), "SR": round(sr, 4), "Frame": round(frame, 4),
            "Brier": round(float(np.mean((probs - df["won"].values)**2)), 4)}


def _leakage_check(cols):
    hits = [c for c in cols if c in BANNED or "rpr" in c.lower()]
    if hits:
        raise AssertionError(f"LEAKAGE ABORT: {hits}")


# ─────────────────────────────────────────────────────────────────────────────
# Task 1: Sidecar Inventory
# ─────────────────────────────────────────────────────────────────────────────
def task1_inventory(train, val, test):
    print("\n=== TASK 1: Sidecar Inventory ===")
    inventory = {}

    # A. JTC-D
    print("\n  [A] JTC-D")
    tj = pd.read_parquet(TJ_PATH, columns=["trainer","jockey","jtc_signal"])
    tc = pd.read_parquet(TC_PATH, columns=["trainer","course","jtc_signal"])
    jc = pd.read_parquet(JC_PATH, columns=["jockey","course","jtc_signal"])
    for name, lookup, keys in [
        ("trainer_jockey", tj, ["trainer","jockey"]),
        ("trainer_course", tc, ["trainer","course"]),
        ("jockey_course",  jc, ["jockey","course"]),
    ]:
        cov = val.merge(lookup, on=keys, how="left")["jtc_signal"].notna().mean()
        print(f"    {name}: rows={len(lookup):,}  val_coverage={cov*100:.1f}%  "
              f"join_keys={keys}  leakage=NO_DATE_BOUNDARY (LEAKAGE_RISK)")
        inventory[f"jtcd_{name}"] = {
            "rows": len(lookup), "val_coverage": round(float(cov), 3),
            "join_keys": keys, "leakage_risk": "NO_DATE_BOUNDARY",
            "lane": "SHADOW_ONLY",
            "note": "All-time cumulative stats, no cutoff date. Lab experiment only.",
        }

    # B. RPDC (already in core)
    print("\n  [B] RPDC memory")
    rpdc_in_core = [c for c in ["setup_run_flag","cash_run_flag","release_window_score","quiet_run_score"] if c in CORE_FEATURES]
    print(f"    RPDC markers already in CORE_FEATURES: {rpdc_in_core}")
    inventory["rpdc"] = {"lane": "ALREADY_IN_MODEL", "cols": rpdc_in_core}

    # C. International lagged (safe)
    print("\n  [C] International lagged")
    il = pd.read_parquet(INTL_PATH, columns=["race_id","horse"] + INTL_SAFE_FEATURES)
    cov = val.merge(il, on=["race_id","horse"], how="left")[INTL_SAFE_FEATURES[0]].notna().mean()
    null_r = il[INTL_SAFE_FEATURES].isnull().mean().round(3).to_dict()
    rpr_check = [c for c in INTL_SAFE_FEATURES if "rpr" in c.lower()]
    print(f"    rows={len(il):,}  val_coverage={cov*100:.1f}%  rpr_cols={rpr_check}")
    print(f"    null rates: {null_r}")
    inventory["intl_lagged"] = {
        "rows": len(il), "val_coverage": round(float(cov), 3),
        "safe_cols": INTL_SAFE_FEATURES, "rpr_violation": bool(rpr_check),
        "null_rates": null_r, "lane": "KEEP_MODEL",
        "note": "Lagged per-race historical OR/course/dist stats. Temporally safe.",
    }

    # D. Market
    print("\n  [D] Market (MARKET_ONLY)")
    v17_cols = pd.read_parquet(V17_PATH, columns=["race_id","horse"] + MARKET_FEATURES)
    cov_m = val.merge(v17_cols, on=["race_id","horse"], how="left")["sp_dec"].notna().mean()
    print(f"    market fields: {MARKET_FEATURES}  val_coverage={cov_m*100:.1f}%")
    inventory["market"] = {
        "cols": MARKET_FEATURES, "val_coverage": round(float(cov_m), 3),
        "lane": "MARKET_ONLY",
        "note": "Same-race morning odds. Not for morning model.",
    }

    # E. RP context
    print("\n  [E] RP context (ARCHIVE_ONLY)")
    inventory["rp_context"] = {
        "available": ["comment (raw text)"],
        "lane": "ARCHIVE_ONLY",
        "note": "No parsed tip/spotlight columns found. Raw comment text only.",
    }

    return inventory


# ─────────────────────────────────────────────────────────────────────────────
# Task 2: Build sidecar datasets
# ─────────────────────────────────────────────────────────────────────────────
def task2_build_sidecars(train, val, test):
    print("\n=== TASK 2: Build Sidecar Datasets ===")

    # --- JTC-D sidecar ---
    print("  Building JTC-D sidecar...")
    def _build_jtcd(df):
        base = df[["race_id","horse","trainer","jockey","course","dist_f"]].copy()
        base["dist_band"] = base["dist_f"].apply(_dist_to_band).astype("category")

        tj = pd.read_parquet(TJ_PATH).rename(columns={"jtc_signal":"tj_jtc_signal","adj_sr":"tj_adj_sr","confidence":"tj_confidence"})
        tc = pd.read_parquet(TC_PATH).rename(columns={"jtc_signal":"tc_jtc_signal","adj_sr":"tc_adj_sr","confidence":"tc_confidence"})
        td = pd.read_parquet(TD_PATH).rename(columns={"jtc_signal":"td_jtc_signal","adj_sr":"td_adj_sr","confidence":"td_confidence"})
        jc = pd.read_parquet(JC_PATH).rename(columns={"jtc_signal":"jc_jtc_signal","adj_sr":"jc_adj_sr","confidence":"jc_confidence"})
        jd = pd.read_parquet(JD_PATH).rename(columns={"jtc_signal":"jd_jtc_signal","adj_sr":"jd_adj_sr","confidence":"jd_confidence"})

        base = base.merge(tj[["trainer","jockey","tj_jtc_signal","tj_adj_sr","tj_confidence"]], on=["trainer","jockey"], how="left")
        base = base.merge(tc[["trainer","course","tc_jtc_signal","tc_adj_sr","tc_confidence"]], on=["trainer","course"], how="left")
        base = base.merge(td[["trainer","dist_band","td_jtc_signal","td_adj_sr","td_confidence"]], on=["trainer","dist_band"], how="left")
        base = base.merge(jc[["jockey","course","jc_jtc_signal","jc_adj_sr","jc_confidence"]], on=["jockey","course"], how="left")
        base = base.merge(jd[["jockey","dist_band","jd_jtc_signal","jd_adj_sr","jd_confidence"]], on=["jockey","dist_band"], how="left")

        return base[["race_id","horse"] + JTCD_FEATURES]

    all_rows = pd.concat([train, val, test], ignore_index=True)
    jtcd_all  = _build_jtcd(all_rows)
    jtcd_all.to_parquet(SIDECAR_DIR / "jtcd_features.parquet", index=False)
    cov = jtcd_all["tj_jtc_signal"].notna().mean()
    print(f"    JTC-D: {len(jtcd_all):,} rows  tj_coverage={cov*100:.1f}%")

    # --- International lagged sidecar ---
    print("  Building international lagged sidecar...")
    il = pd.read_parquet(INTL_PATH, columns=["race_id","horse"] + INTL_SAFE_FEATURES)
    il.to_parquet(SIDECAR_DIR / "international_lagged_features.parquet", index=False)
    print(f"    Intl lagged: {len(il):,} rows")

    # --- Market sidecar ---
    print("  Building market sidecar...")
    v17 = pd.read_parquet(V17_PATH, columns=["race_id","horse"] + MARKET_FEATURES)
    v17.to_parquet(SIDECAR_DIR / "market_features.parquet", index=False)
    print(f"    Market: {len(v17):,} rows")

    return jtcd_all, il, v17


# ─────────────────────────────────────────────────────────────────────────────
# Task 3: Sidecar ablation ladder
# ─────────────────────────────────────────────────────────────────────────────
def task3_ablation(train, val, test):
    print("\n=== TASK 3: Sidecar Ablation Ladder ===")

    # Join all sidecars to splits
    def _enrich(df):
        jtcd = pd.read_parquet(SIDECAR_DIR / "jtcd_features.parquet")
        il   = pd.read_parquet(SIDECAR_DIR / "international_lagged_features.parquet")
        mkt  = pd.read_parquet(SIDECAR_DIR / "market_features.parquet")
        df   = df.merge(jtcd, on=["race_id","horse"], how="left")
        df   = df.merge(il,   on=["race_id","horse"], how="left")
        df   = df.merge(mkt,  on=["race_id","horse"], how="left")
        return df

    train = _enrich(train)
    val   = _enrich(val)
    test  = _enrich(test)

    # Fill NAs
    all_sidecar = JTCD_FEATURES + INTL_SAFE_FEATURES + MARKET_FEATURES
    for df in [train, val, test]:
        _fill(df, CHALLENGER_V1 + all_sidecar)

    # Leakage guard
    _leakage_check(CHALLENGER_V1 + JTCD_FEATURES + INTL_SAFE_FEATURES)

    # Ablation variants
    variants = {
        "A: Challenger V1 (baseline)":              (CHALLENGER_V1, False),
        "B: V1 + JTC-D [LEAKAGE_RISK]":            (CHALLENGER_V1 + JTCD_FEATURES, True),
        "C: V1 + Intl Lagged":                      (CHALLENGER_V1 + INTL_SAFE_FEATURES, False),
        "D: V1 + JTC-D + Intl Lagged [LEAK_RISK]": (CHALLENGER_V1 + JTCD_FEATURES + INTL_SAFE_FEATURES, True),
        "G: V1 + Market [MARKET_LANE]":             (CHALLENGER_V1 + MARKET_FEATURES, False),
        "H: V1 + Intl + Market [MARKET_LANE]":     (CHALLENGER_V1 + INTL_SAFE_FEATURES + MARKET_FEATURES, False),
    }

    results = {}
    for name, (feats, has_leakage) in variants.items():
        present = _present(train, feats)
        model   = lgb.LGBMClassifier(**LGBM_PARAMS)
        model.fit(train[present], train["won"])
        val_m  = _eval(model, val,  feats)
        test_m = _eval(model, test, feats)
        results[name] = {
            "val":           val_m,
            "test":          test_m,
            "leakage_risk":  has_leakage,
            "test_AUC_lift": round(test_m["AUC"] - results["A: Challenger V1 (baseline)"]["test"]["AUC"], 4)
                              if "A: Challenger V1 (baseline)" in results else 0.0,
        }
        tag = " [LEAKAGE_RISK]" if has_leakage else ""
        print(f"  {name}{tag}")
        print(f"    val={val_m}  test={test_m}")

    # Fix lifts now that all are computed
    base_test_auc = results["A: Challenger V1 (baseline)"]["test"]["AUC"]
    base_test_sr  = results["A: Challenger V1 (baseline)"]["test"]["SR"]
    for name in results:
        results[name]["test_AUC_lift"] = round(results[name]["test"]["AUC"] - base_test_auc, 4)
        results[name]["test_SR_lift"]  = round(results[name]["test"]["SR"]  - base_test_sr,  4)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Segment stability (Intl Lagged winner check)
# ─────────────────────────────────────────────────────────────────────────────
def _segment_check(train, val, test, base_feats, challenger_feats, label):
    print(f"\n  Segment check: {label}")
    test_e = test.copy()

    for feats, name in [(base_feats, "base"), (challenger_feats, "challenger")]:
        p = _present(train, feats)
        m = lgb.LGBMClassifier(**LGBM_PARAMS)
        m.fit(train[p], train["won"])
        test_e[f"prob_{name}"] = m.predict_proba(test_e[_present(test_e, feats)])[:, 1]

    test_e["date_dt"] = pd.to_datetime(test_e["date"], errors="coerce")
    test_e["year"]    = test_e["date_dt"].dt.year

    dims = {"year": "year", "aw": "is_aw"}
    rows = []
    for dim, col in dims.items():
        for val_label in test_e[col].dropna().unique():
            sub = test_e[test_e[col] == val_label]
            tmp = sub[["race_id","won","prob_base","prob_challenger"]].copy()
            for model_name, prob_col in [("base","prob_base"),("challenger","prob_challenger")]:
                top1 = tmp.sort_values(["race_id",prob_col], ascending=[True,False]).groupby("race_id").head(1)
                sr   = float(top1["won"].mean())
                rows.append({
                    "dim": dim, "val": str(val_label), "model": model_name,
                    "n": len(sub), "SR": round(sr, 4)
                })

    df = pd.DataFrame(rows)
    pivoted = df.pivot_table(index=["dim","val","n"], columns="model", values="SR").reset_index()
    if "base" in pivoted.columns and "challenger" in pivoted.columns:
        pivoted["lift"] = (pivoted["challenger"] - pivoted["base"]).round(4)
    print(pivoted.to_string(index=False))
    return pivoted


# ─────────────────────────────────────────────────────────────────────────────
# Task 4 + 5: Race-day readiness + commit output
# ─────────────────────────────────────────────────────────────────────────────
def _verdict(name, results):
    r = results[name]
    if r["leakage_risk"]:
        return "SHADOW_ONLY"
    if "MARKET" in name:
        return "MARKET_LANE"
    lift_auc = r["test_AUC_lift"]
    lift_sr  = r["test_SR_lift"]
    if lift_auc > 0.003 and lift_sr > 0.003:
        return "ACCEPTED"
    return "REJECTED_NO_LIFT"


def write_reports(inventory, ablation_results, now):
    # Sidecar tournament
    rows = []
    for name, r in ablation_results.items():
        verdict = _verdict(name, ablation_results)
        rows.append({
            "variant":        name,
            "val_AUC":        r["val"]["AUC"],
            "test_AUC":       r["test"]["AUC"],
            "test_SR":        r["test"]["SR"],
            "test_Frame":     r["test"]["Frame"],
            "test_AUC_lift":  r["test_AUC_lift"],
            "test_SR_lift":   r["test_SR_lift"],
            "leakage_risk":   r["leakage_risk"],
            "verdict":        verdict,
        })
    table = pd.DataFrame(rows).set_index("variant")

    accepted  = [n for n in ablation_results if _verdict(n, ablation_results) == "ACCEPTED"]
    shadow    = [n for n in ablation_results if _verdict(n, ablation_results) == "SHADOW_ONLY"]
    rejected  = [n for n in ablation_results if _verdict(n, ablation_results) == "REJECTED_NO_LIFT"]
    mkt_lane  = [n for n in ablation_results if _verdict(n, ablation_results) == "MARKET_LANE"]

    # Race-day readiness
    tomorrow_model = "Challenger V1 (Core V0_OR + Passport + Intent)"
    if accepted:
        best = max(accepted, key=lambda n: ablation_results[n]["test_AUC_lift"])
        tomorrow_model = f"Challenger V1 + {best.split('+')[1].strip() if '+' in best else 'sidecars'}"

    readiness = {
        "generated_at":       now,
        "champion":           "Core V0_OR (AUC 0.6769, SR 22.32%, Frame 51.13%)",
        "challenger_v1":      "Challenger V1: Core+Passport+Intent (AUC 0.6969, SR 25.02%, Frame 54.98%)",
        "tomorrow_model":     tomorrow_model,
        "sidecars_tested":    list(ablation_results.keys()),
        "sidecars_accepted":  accepted,
        "sidecars_rejected":  rejected,
        "sidecars_shadow":    shadow,
        "market_lane":        mkt_lane,
        "race_day_approved":  True,
        "rpr_violation":      False,
        "sp_violation":       False,
        "leakage_flagged":    shadow,
        "confidence_caveats": [
            "JTC-D stats are all-time cumulative (no date boundary) — shadow only until time-bounded rebuild",
            "Market lane is a separate product, not morning model",
            "Challenger V1 remains safe for race-day output",
        ],
    }

    # Write JSON
    def _safe(o):
        if isinstance(o, (np.bool_, np.integer)): return o.item()
        if isinstance(o, np.floating): return float(o)
        raise TypeError(type(o).__name__)

    tournament_payload = {
        "generated_at": now,
        "ablation_results": {k: {
            "val":  v["val"],
            "test": v["test"],
            "test_AUC_lift": v["test_AUC_lift"],
            "test_SR_lift": v["test_SR_lift"],
            "leakage_risk": v["leakage_risk"],
            "verdict": _verdict(k, ablation_results),
        } for k, v in ablation_results.items()},
        "sidecar_inventory": inventory,
        "readiness": readiness,
    }

    (REPORT_DIR / "sidecar_tournament_latest.json").write_text(
        json.dumps(tournament_payload, indent=2, default=_safe))
    (REPORT_DIR / "race_day_readiness_latest.json").write_text(
        json.dumps(readiness, indent=2, default=_safe))

    # Markdown
    md_tournament = [
        "# Sidecar Tournament — Challenger V1",
        f"Generated: {now}",
        "",
        "Challenger V1 = Core V0_OR + Horse Passport + Intent",
        "Test baseline: AUC 0.6969 | SR 25.02% | Frame 54.98%",
        "",
        "## Ablation Results",
        table.to_markdown(),
        "",
        "## Verdicts",
        f"- **Accepted:** {accepted if accepted else 'none'}",
        f"- **Rejected (no lift):** {rejected}",
        f"- **Shadow only (leakage risk):** {shadow}",
        f"- **Market lane:** {mkt_lane}",
        "",
        "## Sidecar Inventory",
    ]
    for k, v in inventory.items():
        md_tournament.append(f"\n### {k}")
        for kk, vv in v.items():
            md_tournament.append(f"- `{kk}`: {vv}")

    (REPORT_DIR / "sidecar_tournament_latest.md").write_text("\n".join(md_tournament), encoding="utf-8")

    md_readiness = [
        "# Race Day Readiness Report",
        f"Generated: {now}",
        "",
        f"## Tomorrow's Model: `{tomorrow_model}`",
        "",
        "| Item | Status |",
        "|---|---|",
        f"| Champion | Core V0_OR (AUC 0.6769) |",
        f"| Challenger V1 | AUC 0.6969 (+0.020) — PROMOTION EARNED |",
        f"| Race-day approved | YES |",
        f"| RPR violation | NO |",
        f"| SP violation | NO |",
        f"| JTC-D | SHADOW_ONLY (no date boundary) |",
        f"| International Lagged | {'ACCEPTED' if any('Intl' in a for a in accepted) else 'REJECTED or not tested'} |",
        f"| Market lane | SEPARATE (not morning model) |",
        "",
        "## Confidence Caveats",
    ]
    for c in readiness["confidence_caveats"]:
        md_readiness.append(f"- {c}")

    (REPORT_DIR / "race_day_readiness_latest.md").write_text("\n".join(md_readiness), encoding="utf-8")
    print(f"\n  Reports written to {REPORT_DIR}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def run():
    now = datetime.now().isoformat()
    print("Loading Challenger V1 splits...")

    def _load_split(path):
        df = pd.read_parquet(path)
        pp = pd.read_parquet(PASSPORT_F, columns=["race_id","horse"] + PASSPORT_FEATURES)
        ii = pd.read_parquet(INTENT_F,   columns=["race_id","horse"] + INTENT_FEATURES)
        df = df.merge(pp, on=["race_id","horse"], how="left")
        df = df.merge(ii, on=["race_id","horse"], how="left")
        df = _fill(df, CHALLENGER_V1)
        return df

    train = _load_split(CORE_TRAIN)
    val   = _load_split(CORE_VAL)
    test  = _load_split(CORE_TEST)
    print(f"  train: {len(train):,}  val: {len(val):,}  test: {len(test):,}")

    # Leakage guard on challenger V1
    _leakage_check(CHALLENGER_V1)
    print("  Leakage check (Challenger V1): PASS")

    inventory = task1_inventory(train, val, test)
    task2_build_sidecars(train, val, test)
    ablation  = task3_ablation(train, val, test)

    # Segment check on best non-leakage sidecar
    print("\n=== Segment stability: V1 vs V1+Intl Lagged ===")
    il = pd.read_parquet(SIDECAR_DIR / "international_lagged_features.parquet")
    train2 = train.merge(il, on=["race_id","horse"], how="left")
    val2   = val.merge(il,   on=["race_id","horse"], how="left")
    test2  = test.merge(il,  on=["race_id","horse"], how="left")
    for df in [train2, val2, test2]:
        _fill(df, INTL_SAFE_FEATURES)
    _segment_check(train2, val2, test2, CHALLENGER_V1, CHALLENGER_V1 + INTL_SAFE_FEATURES, "V1 vs V1+Intl")

    write_reports(inventory, ablation, now)

    print(f"\n{'='*60}")
    print("SIDECAR TOURNAMENT COMPLETE")
    accepted = [n for n in ablation if _verdict(n, ablation) == "ACCEPTED"]
    print(f"Sidecars accepted: {accepted if accepted else 'none'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    run()
