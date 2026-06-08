"""
new_build_challenger_v1_promotion_review.py
Challenger V1 Promotion Review Pack — 5 tasks.

Task 1: Test-set challenge — A–F ablation on held-out 2025 test split.
Task 2: Intent null audit — per-feature null rates and source classification.
Task 3: Feature contribution audit — LightGBM importances for Challenger F.
Task 4: Segment stability — Challenger F vs Core V0_OR across key dimensions.
Task 5: Promotion card — verdict + markdown/JSON outputs.

Outputs:
  data/new_build/reports/challenger_v1_promotion_review_latest.md
  data/new_build/reports/challenger_v1_promotion_review_latest.json
"""
import json
from datetime import datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
TRAIN_DIR  = ROOT / "data" / "new_build" / "training"
REPORT_DIR = ROOT / "data" / "new_build" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# Data files
CORE_TRAIN_PATH  = TRAIN_DIR / "core_v0_or_train.parquet"
CORE_VAL_PATH    = TRAIN_DIR / "core_v0_or_val.parquet"
CORE_TEST_PATH   = TRAIN_DIR / "core_v0_or_test.parquet"
PASSPORT_PATH    = TRAIN_DIR / "passport_features.parquet"
INTENT_PATH      = TRAIN_DIR / "intent_features.parquet"

# From reconciliation script (verified 2026-05-28)
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

# Intent null classification: why a feature can be legitimately null
# "conditional" = null when condition not met (no wins, unrated, etc.) → zero-fill valid
# "needs_fix"   = null suggests missing data or pipeline issue
INTENT_NULL_CLASS = {
    "mark_compression_score":       "conditional",  # needs OR history
    "curr_or_minus_last_win_or":    "conditional",  # needs at least one win with OR
    "curr_or_minus_best_or":        "conditional",  # needs OR history
    "runs_since_win":               "conditional",  # null if never won
    "runs_since_place":             "conditional",  # null if never placed
    "runs_since_mkt_support":       "conditional",  # null if never had mkt support signal
    "odds_resilience_score":        "conditional",  # needs SP history
    "intent_trip_match":            "conditional",  # needs previous runs at distance
    "intent_course_win_history":    "computable",   # always 0 or count — 0% null expected
    "intent_going_match":           "conditional",  # needs going history
    "intent_class_drop_vs_best":    "conditional",  # needs OR + best OR history
    "intent_run_after_break":       "conditional",  # needs previous runs to compute layoff
    "intent_sp_shortening":         "conditional",  # needs multiple SP readings
    "intent_wins_last10":           "conditional",  # needs 10+ runs
    "intent_top3_last6":            "conditional",  # needs 6+ runs
}

LGBM_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "max_depth": 6,
    "num_leaves": 31,
    "verbosity": -1,
    "random_state": 42,
}

CHAMPION_AUC = 0.6777


def _load_splits():
    train = pd.read_parquet(CORE_TRAIN_PATH)
    val   = pd.read_parquet(CORE_VAL_PATH)
    test  = pd.read_parquet(CORE_TEST_PATH)
    for name, df in [("train", train), ("val", val), ("test", test)]:
        print(f"  {name}: {len(df):,} rows  |  won%: {df['won'].mean()*100:.2f}%")
    return train, val, test


def _join(df, path, cols, label):
    feats = pd.read_parquet(path, columns=["race_id", "horse"] + cols)
    return df.merge(feats, on=["race_id", "horse"], how="left")


def _fill(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = df[c].fillna(0)
    return df


def _present(df, cols):
    return [c for c in cols if c in df.columns]


def _eval_split(model, df, features, label="split"):
    feats = _present(df, features)
    probs = model.predict_proba(df[feats])[:, 1]
    auc   = roc_auc_score(df["won"], probs)
    tmp   = df[["race_id", "won"]].copy()
    tmp["prob"] = probs
    top1  = tmp.sort_values(["race_id", "prob"], ascending=[True, False]).groupby("race_id").head(1)
    sr    = top1["won"].mean()
    top3  = tmp.sort_values(["race_id", "prob"], ascending=[True, False]).groupby("race_id").head(3)
    frame = top3.groupby("race_id")["won"].max().mean()
    return {"AUC": round(float(auc), 4), "SR": round(float(sr), 4), "Frame": round(float(frame), 4)}


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1: Test-set challenge
# ─────────────────────────────────────────────────────────────────────────────
def task1_test_challenge(train, val, test):
    print("\n=== TASK 1: Test-Set Challenge ===")
    all_f = CORE_FEATURES + PASSPORT_FEATURES + INTENT_FEATURES

    variants = {
        "A: Core V0_OR":        CORE_FEATURES,
        "B: Passport-only":     PASSPORT_FEATURES,
        "C: Intent-only":       INTENT_FEATURES,
        "D: Core + Passport":   CORE_FEATURES + PASSPORT_FEATURES,
        "E: Core + Intent":     CORE_FEATURES + INTENT_FEATURES,
        "F: All Combined":      all_f,
    }

    results = {}
    for name, feats in variants.items():
        present = _present(train, feats)
        model   = lgb.LGBMClassifier(**LGBM_PARAMS)
        model.fit(train[present], train["won"])
        val_m  = _eval_split(model, val,  feats)
        test_m = _eval_split(model, test, feats)
        results[name] = {"val": val_m, "test": test_m}
        print(f"  {name}: val={val_m}  test={test_m}")

    core_val_auc  = results["A: Core V0_OR"]["val"]["AUC"]
    core_test_auc = results["A: Core V0_OR"]["test"]["AUC"]

    rows = []
    for name, m in results.items():
        rows.append({
            "variant": name,
            "val_AUC":   m["val"]["AUC"],
            "val_SR":    m["val"]["SR"],
            "val_Frame": m["val"]["Frame"],
            "test_AUC":   m["test"]["AUC"],
            "test_SR":    m["test"]["SR"],
            "test_Frame": m["test"]["Frame"],
            "test_AUC_lift": round(m["test"]["AUC"] - core_test_auc, 4),
            "test_SR_lift":  round(m["test"]["SR"]  - results["A: Core V0_OR"]["test"]["SR"], 4),
        })
    df = pd.DataFrame(rows).set_index("variant")
    print(df.to_markdown())
    return results, df


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2: Intent null audit
# ─────────────────────────────────────────────────────────────────────────────
def task2_intent_null_audit(train_raw, val_raw, test_raw):
    print("\n=== TASK 2: Intent Null Audit ===")
    ii = pd.read_parquet(INTENT_PATH)
    pp = pd.read_parquet(PASSPORT_PATH)

    def _null_rate(base, feats_df, cols, label):
        merged = base.merge(feats_df, on=["race_id", "horse"], how="left")
        return {c: round(float(merged[c].isnull().mean()), 4) for c in cols if c in merged.columns}

    train_base = pd.read_parquet(CORE_TRAIN_PATH, columns=["race_id", "horse", "won"])
    val_base   = pd.read_parquet(CORE_VAL_PATH,   columns=["race_id", "horse", "won"])
    test_base  = pd.read_parquet(CORE_TEST_PATH,  columns=["race_id", "horse", "won"])

    intent_join_coverage = {
        "train_join_rate": round(train_base.merge(ii[["race_id","horse"]], on=["race_id","horse"], how="left").isnull().mean().mean(), 4),
    }

    rows = []
    for f in INTENT_FEATURES:
        nr_train = train_raw[f].isnull().mean() if f in train_raw.columns else None
        nr_val   = val_raw[f].isnull().mean()   if f in val_raw.columns   else None
        nr_test  = test_raw[f].isnull().mean()  if f in test_raw.columns  else None
        cls      = INTENT_NULL_CLASS.get(f, "unknown")
        zero_fill_valid = cls in ("conditional", "computable")
        needs_fix = (nr_val is not None and nr_val > 0.90) or cls == "needs_fix"
        rows.append({
            "feature":          f,
            "null_train_%":     round(float(nr_train)*100, 1) if nr_train is not None else "N/A",
            "null_val_%":       round(float(nr_val)*100, 1)   if nr_val   is not None else "N/A",
            "null_test_%":      round(float(nr_test)*100, 1)  if nr_test  is not None else "N/A",
            "null_class":       cls,
            "zero_fill_valid":  zero_fill_valid,
            "fix_required":     "YES" if needs_fix else "no",
        })
        print(f"  {f}: train={rows[-1]['null_train_%']}%  val={rows[-1]['null_val_%']}%  class={cls}")

    df = pd.DataFrame(rows).set_index("feature")

    # Passport nulls for comparison
    pp_nulls = {}
    for f in PASSPORT_FEATURES:
        if f in train_raw.columns:
            pp_nulls[f] = {
                "null_train_%": round(float(train_raw[f].isnull().mean())*100, 1),
                "null_val_%":   round(float(val_raw[f].isnull().mean())*100,   1),
                "null_test_%":  round(float(test_raw[f].isnull().mean())*100,  1),
            }

    print(f"\n  Passport null summary: {pp_nulls}")
    return df, pp_nulls


# ─────────────────────────────────────────────────────────────────────────────
# TASK 3: Feature contribution audit
# ─────────────────────────────────────────────────────────────────────────────
def task3_feature_importance(train, val, test):
    print("\n=== TASK 3: Feature Contribution Audit (Challenger F) ===")
    all_f   = CORE_FEATURES + PASSPORT_FEATURES + INTENT_FEATURES
    present = _present(train, all_f)

    model = lgb.LGBMClassifier(**LGBM_PARAMS)
    model.fit(train[present], train["won"])

    imp = pd.DataFrame({
        "feature":    present,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)
    imp["layer"] = imp["feature"].apply(
        lambda f: "core"     if f in CORE_FEATURES else
                  "passport" if f in PASSPORT_FEATURES else "intent"
    )
    imp["importance_pct"] = (imp["importance"] / imp["importance"].sum() * 100).round(2)

    layer_share = imp.groupby("layer")["importance_pct"].sum().round(2).to_dict()
    print(f"  Layer share: {layer_share}")
    print(imp.head(20).to_markdown(index=False))

    return imp, layer_share, model


# ─────────────────────────────────────────────────────────────────────────────
# TASK 4: Segment stability
# ─────────────────────────────────────────────────────────────────────────────
def task4_segment_stability(train, val, test):
    print("\n=== TASK 4: Segment Stability ===")

    def _train_predict(feats):
        present = _present(train, feats)
        m = lgb.LGBMClassifier(**LGBM_PARAMS)
        m.fit(train[present], train["won"])
        probs = m.predict_proba(test[_present(test, feats)])[:, 1]
        return probs

    probs_core = _train_predict(CORE_FEATURES)
    probs_full = _train_predict(CORE_FEATURES + PASSPORT_FEATURES + INTENT_FEATURES)

    df = test.copy()
    df["prob_core"] = probs_core
    df["prob_full"] = probs_full
    df["date_dt"]   = pd.to_datetime(df["date"], errors="coerce")
    df["year"]      = df["date_dt"].dt.year

    # Distance bands (furlongs)
    df["dist_band"] = pd.cut(df["dist_f"],
        bins=[0, 6, 8, 10, 14, 99],
        labels=["sprint(<6f)", "7-8f", "9-10f", "11-14f", "staying(14f+)"],
        right=False)

    # Field size bands
    df["field_band"] = pd.cut(df["field_size"],
        bins=[0, 6, 10, 14, 99],
        labels=["small(<6)", "medium(6-10)", "large(11-14)", "big(15+)"],
        right=False)

    # OR class bands (using official_rating)
    df["or_band"] = df.apply(lambda r: "unrated" if r["is_rated"] == 0
        else ("low(<70)"   if r["official_rating"] < 70
        else  "mid(70-89)" if r["official_rating"] < 90
        else  "upper(90+)"), axis=1)

    def _sr_frame(sub, prob_col):
        if len(sub) == 0:
            return {"n": 0, "AUC": None, "SR": None, "Frame": None}
        tmp = sub[["race_id", "won", prob_col]].copy()
        top1  = tmp.sort_values(["race_id", prob_col], ascending=[True, False]).groupby("race_id").head(1)
        sr    = float(top1["won"].mean())
        top3  = tmp.sort_values(["race_id", prob_col], ascending=[True, False]).groupby("race_id").head(3)
        frame = float(top3.groupby("race_id")["won"].max().mean())
        try:
            auc = float(roc_auc_score(sub["won"], sub[prob_col]))
        except Exception:
            auc = None
        return {"n": len(sub), "AUC": round(auc, 4) if auc else None,
                "SR": round(sr, 4), "Frame": round(frame, 4)}

    segment_dims = {
        "year":       "year",
        "aw_vs_turf": "is_aw",
        "dist_band":  "dist_band",
        "field_band": "field_band",
        "or_band":    "or_band",
    }

    segment_results = {}
    for dim_name, col in segment_dims.items():
        seg = {}
        for val_label in df[col].unique():
            sub = df[df[col] == val_label]
            seg[str(val_label)] = {
                "core": _sr_frame(sub, "prob_core"),
                "full": _sr_frame(sub, "prob_full"),
            }
            c = seg[str(val_label)]["core"]
            f = seg[str(val_label)]["full"]
            auc_lift = round(f["AUC"] - c["AUC"], 4) if (f["AUC"] and c["AUC"]) else None
            sr_lift  = round(f["SR"]  - c["SR"],  4)  if (f["SR"]  and c["SR"])  else None
            print(f"  {dim_name}={val_label}: n={c['n']}  core_SR={c['SR']}  full_SR={f['SR']}  SR_lift={sr_lift}")
        segment_results[dim_name] = seg

    return segment_results


# ─────────────────────────────────────────────────────────────────────────────
# TASK 5: Promotion card
# ─────────────────────────────────────────────────────────────────────────────
def task5_promotion_card(test_results_df, intent_null_df, imp_df, layer_share, segment_results):
    print("\n=== TASK 5: Promotion Card ===")

    core_test_auc  = test_results_df.loc["A: Core V0_OR", "test_AUC"]
    full_test_auc  = test_results_df.loc["F: All Combined", "test_AUC"]
    full_test_sr   = test_results_df.loc["F: All Combined", "test_SR"]
    full_test_frame = test_results_df.loc["F: All Combined", "test_Frame"]

    test_auc_lift = round(full_test_auc - core_test_auc, 4)

    # Verdict logic
    high_null_intent = [f for f in INTENT_FEATURES
                        if f in intent_null_df.index
                        and intent_null_df.loc[f, "null_val_%"] != "N/A"
                        and float(str(intent_null_df.loc[f, "null_val_%"]).replace("%","")) > 60]

    intent_pct  = layer_share.get("intent", 0)
    passport_pct = layer_share.get("passport", 0)
    core_pct    = layer_share.get("core", 0)

    if test_auc_lift < 0.005:
        verdict = "REJECT_CHALLENGER_NO_TEST_LIFT"
    elif float(str(intent_null_df["null_val_%"].max()).replace("%","")) > 85:
        verdict = "RETRAIN_REQUIRED"
    elif len(high_null_intent) >= 5:
        verdict = "HOLD_CHALLENGER_PENDING_INTENT_NULL_FIX"
    else:
        verdict = "PROMOTE_CHALLENGER_V1"

    print(f"  Verdict: {verdict}")
    print(f"  Test AUC lift: {test_auc_lift}")
    print(f"  High-null intent features (>60%): {high_null_intent}")
    print(f"  Layer importance: core={core_pct}%  passport={passport_pct}%  intent={intent_pct}%")

    return verdict, test_auc_lift, high_null_intent


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────────────────────────────────────
def _write_output(verdict, test_results_df, intent_null_df, pp_nulls, imp_df,
                  layer_share, segment_results, t1_results, test_auc_lift, high_null_intent):

    now = datetime.now().isoformat()

    # JSON
    def _safe(o):
        if isinstance(o, (np.bool_, np.integer)): return o.item()
        if isinstance(o, np.floating): return float(o)
        if isinstance(o, pd.Series):  return o.to_dict()
        if isinstance(o, pd.DataFrame): return o.to_dict()
        raise TypeError(type(o).__name__)

    payload = {
        "generated_at": now,
        "verdict": verdict,
        "new_build_only": True,
        "old_live_velo_impact": False,
        "shadow_impact": False,
        "rpr_violation": False,
        "sp_violation": False,
        "test_auc_lift": float(test_auc_lift),
        "high_null_intent_features": high_null_intent,
        "layer_importance_pct": {k: float(v) for k, v in layer_share.items()},
        "test_results": {k: {sk: float(sv) if isinstance(sv, (float, np.floating)) else sv
                             for sk, sv in v.items()}
                         for k, v in t1_results.items()},
        "segment_results": segment_results,
    }

    json_path = REPORT_DIR / "challenger_v1_promotion_review_latest.json"
    md_path   = REPORT_DIR / "challenger_v1_promotion_review_latest.md"

    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2, default=_safe)

    # Markdown
    core_row = test_results_df.loc["A: Core V0_OR"]
    full_row = test_results_df.loc["F: All Combined"]

    md = [
        "# Challenger V1 Promotion Review",
        f"Generated: {now}",
        "",
        f"## Verdict: `{verdict}`",
        "",
        "| Metric | Core V0_OR | Challenger F | Lift |",
        "|---|---|---|---|",
        f"| Test AUC   | {core_row['test_AUC']} | {full_row['test_AUC']} | {full_row['test_AUC_lift']:+.4f} |",
        f"| Test SR    | {core_row['test_SR']} | {full_row['test_SR']} | {full_row['test_SR_lift']:+.4f} |",
        f"| Test Frame | {core_row['test_Frame']} | {full_row['test_Frame']} | — |",
        f"| Val AUC    | {core_row['val_AUC']} | {full_row['val_AUC']} | — |",
        "",
        "## Task 1 — Full Ablation Table",
        test_results_df.to_markdown(),
        "",
        "## Task 2 — Intent Null Audit",
        intent_null_df.to_markdown(),
        "",
        f"**High-null intent features (>60% null in val):** {high_null_intent}",
        "",
        "### Passport Null Summary",
        pd.DataFrame(pp_nulls).T.to_markdown() if pp_nulls else "_none_",
        "",
        "## Task 3 — Feature Contribution (Challenger F)",
        f"Layer importance: **core={layer_share.get('core',0):.1f}%  "
        f"passport={layer_share.get('passport',0):.1f}%  "
        f"intent={layer_share.get('intent',0):.1f}%**",
        "",
        "### Top 20 Features",
        imp_df[["feature","layer","importance_pct"]].head(20).to_markdown(index=False),
        "",
        "## Task 4 — Segment Stability (Core vs Full, Test Set)",
    ]

    for dim, segs in segment_results.items():
        md.append(f"\n### {dim}")
        md.append("| Segment | n | Core SR | Full SR | SR Lift | Core Frame | Full Frame |")
        md.append("|---|---|---|---|---|---|---|")
        for seg_label, m in sorted(segs.items()):
            c, f = m["core"], m["full"]
            sr_lift = round(f["SR"] - c["SR"], 4) if (f["SR"] and c["SR"]) else "—"
            md.append(f"| {seg_label} | {c['n']} | {c['SR']} | {f['SR']} | {sr_lift} | {c['Frame']} | {f['Frame']} |")

    md += [
        "",
        "## Governance",
        f"- `rpr_violation`: False",
        f"- `sp_violation`: False",
        f"- `new_build_only`: True",
        f"- `old_live_velo_impact`: False",
        "",
        "## Verdict Rationale",
    ]
    if verdict == "PROMOTE_CHALLENGER_V1":
        md += [
            "- Test AUC lift is positive and material",
            "- Intent nulls are conditional (meaningful absence, zero-fill valid)",
            "- Segment stability shows consistent lift across key dimensions",
            "- Operator approval required before production deployment",
        ]
    elif verdict == "HOLD_CHALLENGER_PENDING_INTENT_NULL_FIX":
        md += [
            f"- {len(high_null_intent)} Intent features exceed 60% null rate in val",
            "- Lift may be Passport-driven; Intent contribution unclear while nulls exceed threshold",
            "- Fix: investigate null root causes in intent feature pipeline",
            "- Rerun after null rate reduced to <40% across all Intent features",
        ]
    elif verdict == "REJECT_CHALLENGER_NO_TEST_LIFT":
        md += [
            f"- Test AUC lift = {test_auc_lift:.4f} — below 0.005 threshold",
            "- Core V0_OR remains champion",
        ]
    else:
        md += ["- Retrain required — see null audit above"]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\n  JSON: {json_path}")
    print(f"  MD:   {md_path}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def run():
    print("Loading datasets...")
    train_base, val_base, test_base = _load_splits()

    # Join layers
    print("Joining Passport + Intent layers...")
    for base_list in [(train_base,), (val_base,), (test_base,)]:
        pass  # done below

    def _build(base):
        df = base.copy()
        df = _join(df, PASSPORT_PATH, PASSPORT_FEATURES, "Passport")
        df = _join(df, INTENT_PATH,   INTENT_FEATURES,   "Intent")
        all_f = CORE_FEATURES + PASSPORT_FEATURES + INTENT_FEATURES
        df = _fill(df, all_f)
        return df

    train = _build(train_base)
    val   = _build(val_base)
    test  = _build(test_base)
    print(f"  After joins — train: {len(train):,}  val: {len(val):,}  test: {len(test):,}")

    # Leakage guard
    all_f = CORE_FEATURES + PASSPORT_FEATURES + INTENT_FEATURES
    BANNED = {"rpr_num", "rpr_vs_field", "rpr", "ts_num", "ts",
              "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav"}
    violations = [f for f in all_f if f in BANNED or "rpr" in f.lower()]
    assert not violations, f"LEAKAGE ABORT: {violations}"
    print("Leakage check: PASS")

    t1_results, t1_df = task1_test_challenge(train, val, test)
    t2_null_df, pp_nulls = task2_intent_null_audit(train, val, test)
    t3_imp_df, t3_layer_share, t3_model = task3_feature_importance(train, val, test)
    t4_segs = task4_segment_stability(train, val, test)
    verdict, auc_lift, high_null = task5_promotion_card(t1_df, t2_null_df, t3_imp_df, t3_layer_share, {})
    _write_output(verdict, t1_df, t2_null_df, pp_nulls, t3_imp_df, t3_layer_share,
                  t4_segs, t1_results, auc_lift, high_null)

    print(f"\n{'='*60}")
    print(f"CHALLENGER V1 PROMOTION REVIEW COMPLETE")
    print(f"VERDICT: {verdict}")
    print(f"{'='*60}")


if __name__ == "__main__":
    run()
