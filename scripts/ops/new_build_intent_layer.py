#!/usr/bin/env python3
"""
new_build_intent_layer.py
Intent Layer V1 sidecar — ablation vs champion Core_V0_OR_Passport_V1.

Three-way test on 2025 unseen holdout:
  1. Champion alone          (frozen — Core_V0_OR_Passport_V1)
  2. Intent-only             (intent features, retrained challenger)
  3. Champion + Intent       (champion features + intent features, retrained challenger)

Promotion rule:
  Champion + Intent promoted only if it beats champion on ALL of:
    AUC / Brier / SR / Frame on the 2025 unseen test set.

Outputs:
  data/new_build/reports/intent_layer_v1_latest.md
  data/new_build/reports/intent_layer_v1_latest.json
  data/new_build/models/core_v0_or_passport_intent/  (if promoted)

Classification:
  INTENT_ADDS_SIGNAL
  INTENT_MARGINAL
  INTENT_NEUTRAL
  INTENT_INSUFFICIENT_COVERAGE
"""
import json
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, brier_score_loss

TRAIN_DIR = ROOT / "data" / "new_build" / "training"
MDL_DIR   = ROOT / "data" / "new_build" / "models"
RPT_DIR   = ROOT / "data" / "new_build" / "reports"
INTENT_PATH = TRAIN_DIR / "intent_features.parquet"
PASSPORT_PATH = TRAIN_DIR / "passport_features.parquet"

CHAMPION_PKL  = MDL_DIR / "core_v0_or_passport" / "core_v0_or_passport_model.pkl"
CHAMPION_META = MDL_DIR / "core_v0_or_passport" / "core_v0_or_passport_metadata.json"

BANNED = {"rpr", "rpr_num", "rpr_vs_field", "ts_num", "sp_dec", "log_sp",
          "is_fav", "sp_rank", "implied_prob", "pos", "ovr_btn",
          "btn", "comment", "time", "target",
          # Intent-specific bans: use current-race market data
          "odds_contraction_score",  # (prev_SP - curr_SP)/prev_SP → needs current SP
          "decoy_support_flag",      # fires on is_fav[current_race] → leakage
          }

NOW = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def leakage_check(cols, label):
    for b in BANNED:
        if b in cols:
            raise AssertionError(f"LEAKAGE [{label}]: {b}")
    rpr = [c for c in cols if "rpr" in c.lower()]
    if rpr:
        raise AssertionError(f"RPR_VIOLATION [{label}]: {rpr}")
    return "PASS"


def race_metrics(df, prob_col):
    sr = fr = races = 0
    for _, g in df.groupby("race_id"):
        if len(g) < 2:
            continue
        races += 1
        if g.loc[g[prob_col].idxmax(), "won"] == 1:
            sr += 1
        if g.nlargest(3, prob_col)["won"].sum() >= 1:
            fr += 1
    return round(sr / races, 4) if races else 0.0, round(fr / races, 4) if races else 0.0, races


def full_eval(df, prob_col):
    y, p = df["won"], df[prob_col]
    auc   = round(float(roc_auc_score(y, p)), 4)
    brier = round(float(brier_score_loss(y, p)), 4)
    sr, fr, races = race_metrics(df, prob_col)
    return {"auc": auc, "brier": brier, "sr": sr, "frame": fr,
            "races": races, "runners": len(df)}


def prep_and_train(train, val, feature_cols):
    obj_cols = [c for c in feature_cols if train[c].dtype == object]
    for c in obj_cols:
        cats = pd.Categorical(
            pd.concat([train[c], val[c]], ignore_index=True)).categories
        train = train.copy(); val = val.copy()
        train[c] = pd.Categorical(train[c], categories=cats).codes
        val[c]   = pd.Categorical(val[c],   categories=cats).codes

    non_const = [c for c in feature_cols if train[c].nunique() > 1]
    X_tr = train[non_const].copy()
    X_va = val[non_const].copy()
    meds = X_tr.median(numeric_only=True)
    X_tr = X_tr.fillna(meds)
    X_va = X_va.fillna(meds)

    try:
        import lightgbm as lgb
        model = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=6,
            num_leaves=63, min_child_samples=50,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbose=-1, n_jobs=4,
        )
        model.fit(X_tr, train["won"], eval_set=[(X_va, val["won"])],
                  callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(0)])
    except ImportError:
        from sklearn.ensemble import GradientBoostingClassifier
        model = GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            min_samples_leaf=50, subsample=0.8, random_state=42)
        model.fit(X_tr, train["won"])

    return model, non_const, meds


def score_on_test(test, model, feature_cols, meds, col_name):
    t = test.copy()
    obj_cols = [c for c in feature_cols if c in t.columns and t[c].dtype == object]
    for c in obj_cols:
        t[c] = pd.Categorical(t[c]).codes
    for c in feature_cols:
        if c not in t.columns:
            t[c] = meds.get(c, 0.0)
    X = t[feature_cols].copy()
    for c in feature_cols:
        X[c] = X[c].fillna(meds.get(c, 0.0))
    test[col_name] = model.predict_proba(X)[:, 1]
    return test


def feat_importance(model, feature_cols):
    try:
        imp = model.feature_importances_
        rows = sorted(
            [{"feature": f, "importance": float(i)} for f, i in zip(feature_cols, imp)],
            key=lambda r: -r["importance"],
        )
        total = sum(r["importance"] for r in rows) or 1.0
        for r in rows:
            r["importance_pct"] = round(r["importance"] / total * 100, 2)
        return rows
    except AttributeError:
        return []


def run():
    print("=== Intent Layer V1 Sidecar — Ablation vs Champion ===\n")

    # ── Load splits ───────────────────────────────────────────────────────────
    print("Loading splits ...")
    train_or = pd.read_parquet(TRAIN_DIR / "core_v0_or_train.parquet")
    val_or   = pd.read_parquet(TRAIN_DIR / "core_v0_or_val.parquet")
    test_or  = pd.read_parquet(TRAIN_DIR / "core_v0_or_test.parquet")
    print(f"  Train: {len(train_or):,}  Val: {len(val_or):,}  Test: {len(test_or):,}")

    # ── Load and join passport features ───────────────────────────────────────
    pp = pd.read_parquet(PASSPORT_PATH)
    pp_cols = [c for c in pp.columns if c not in ("race_id", "horse")]

    def join(base, feat_df, feat_cols, label):
        merged = base.merge(feat_df[["race_id", "horse"] + feat_cols],
                            on=["race_id", "horse"], how="left")
        hit = merged[feat_cols[0]].notna().mean() * 100 if feat_cols else 0
        print(f"  {label} passport match: {hit:.1f}%")
        return merged

    train_pp = join(train_or, pp, pp_cols, "Train")
    val_pp   = join(val_or,   pp, pp_cols, "Val")
    test_pp  = join(test_or,  pp, pp_cols, "Test")

    # ── Load and join intent features ─────────────────────────────────────────
    if not INTENT_PATH.exists():
        print(f"\nERROR: {INTENT_PATH} not found. Run new_build_intent_features.py first.")
        sys.exit(1)

    print("\nLoading intent features ...")
    intent_df = pd.read_parquet(INTENT_PATH)
    intent_cols = [c for c in intent_df.columns if c not in ("race_id", "horse")]
    # Filter to cols with >5% coverage
    coverage = {c: intent_df[c].notna().mean() for c in intent_cols}
    usable   = [c for c in intent_cols if coverage[c] > 0.05]
    print(f"  Intent features: {len(intent_cols)} total, {len(usable)} with >5% coverage")
    for c in intent_cols:
        print(f"    {c:<40} {coverage[c]*100:.1f}%{'  DROP' if c not in usable else ''}")

    def join_intent(base):
        return base.merge(intent_df[["race_id", "horse"] + usable],
                          on=["race_id", "horse"], how="left")

    train_int = join_intent(train_pp)
    val_int   = join_intent(val_pp)
    test_int  = join_intent(test_pp)
    int_hit   = test_int[usable[0]].notna().mean() * 100 if usable else 0
    print(f"  Test intent match: {int_hit:.1f}%")

    # ── Load champion ─────────────────────────────────────────────────────────
    print("\nLoading champion model ...")
    with open(CHAMPION_PKL, "rb") as f:
        champ_bundle = pickle.load(f)
    champ_model  = champ_bundle["model"]
    champ_feats  = champ_bundle["feature_cols"]
    champ_meds   = pd.Series(champ_bundle["medians"])
    leakage_check(champ_feats, "Champion")
    print(f"  Champion features: {len(champ_feats)}")

    # ── Variant 1: Champion (frozen) ─────────────────────────────────────────
    print("\n[1/3] Champion (frozen) on 2025 unseen test ...")
    test_int = score_on_test(test_int, champ_model, champ_feats, champ_meds, "_p_champ")
    r_champ  = full_eval(test_int, "_p_champ")
    print(f"  AUC={r_champ['auc']}  Brier={r_champ['brier']}  SR={r_champ['sr']:.1%}  Frame={r_champ['frame']:.1%}  Races={r_champ['races']:,}")

    # ── Variant 2: Intent-only (retrained challenger) ─────────────────────────
    print("\n[2/3] Intent-only (retrained on train/val) ...")
    leakage_check(usable, "Intent-only")
    m_int, f_int, med_int = prep_and_train(train_int, val_int, usable)
    test_int = score_on_test(test_int, m_int, f_int, med_int, "_p_intent")
    r_intent = full_eval(test_int, "_p_intent")
    imp_intent = feat_importance(m_int, f_int)
    print(f"  AUC={r_intent['auc']}  Brier={r_intent['brier']}  SR={r_intent['sr']:.1%}  Frame={r_intent['frame']:.1%}  Races={r_intent['races']:,}")

    # ── Variant 3: Champion + Intent (retrained challenger) ───────────────────
    print("\n[3/3] Champion + Intent (retrained challenger) ...")
    combo_cols = champ_feats + [c for c in usable if c not in champ_feats]
    combo_cols = [c for c in combo_cols if c in train_int.columns]
    leakage_check(combo_cols, "Champion+Intent")
    m_combo, f_combo, med_combo = prep_and_train(train_int, val_int, combo_cols)
    test_int = score_on_test(test_int, m_combo, f_combo, med_combo, "_p_combo")
    r_combo  = full_eval(test_int, "_p_combo")
    imp_combo = feat_importance(m_combo, f_combo)
    print(f"  AUC={r_combo['auc']}  Brier={r_combo['brier']}  SR={r_combo['sr']:.1%}  Frame={r_combo['frame']:.1%}  Races={r_combo['races']:,}")

    # ── Summary table ─────────────────────────────────────────────────────────
    auc_c, brier_c, sr_c, fr_c = r_champ["auc"], r_champ["brier"], r_champ["sr"], r_champ["frame"]
    print("\n")
    print("=" * 76)
    print("INTENT LAYER V1 — 2025 UNSEEN TEST RESULTS")
    print("=" * 76)
    header = f"{'Variant':<25} {'AUC':>8} {'AUC Δ':>8} {'Brier':>8} {'SR':>7} {'Frame':>7} {'Races':>8}"
    print(header)
    print("-" * 76)
    for r, label in [(r_champ, "Champion"), (r_intent, "Intent-only"), (r_combo, "Champion+Intent")]:
        a  = f"{r['auc']:.4f}"
        d  = f"{r['auc'] - auc_c:+.4f}"
        b  = f"{r['brier']:.4f}"
        s  = f"{r['sr']:.1%}"
        f  = f"{r['frame']:.1%}"
        rc = f"{r['races']:,}"
        star = " ← champion" if label == "Champion" else (" ← challenger" if label == "Champion+Intent" else "")
        print(f"{label:<25} {a:>8} {d:>8} {b:>8} {s:>7} {f:>7} {rc:>8}{star}")
    print("=" * 76)

    # Promotion gates
    beats_auc   = r_combo["auc"]   > auc_c
    beats_brier = r_combo["brier"] < brier_c
    beats_sr    = r_combo["sr"]    > sr_c
    beats_frame = r_combo["frame"] > fr_c
    gates = {"auc": beats_auc, "brier": beats_brier, "sr": beats_sr, "frame": beats_frame}
    n_pass = sum(gates.values())

    auc_d   = round(r_combo["auc"]   - auc_c,  4)
    brier_d = round(r_combo["brier"] - brier_c, 4)
    sr_d    = round(r_combo["sr"]    - sr_c,    4)
    frame_d = round(r_combo["frame"] - fr_c,    4)

    if n_pass == 4:
        verdict = "INTENT_ADDS_SIGNAL"
    elif n_pass >= 2:
        verdict = "INTENT_MARGINAL"
    elif usable and int_hit < 30:
        verdict = "INTENT_INSUFFICIENT_COVERAGE"
    else:
        verdict = "INTENT_NEUTRAL"

    print(f"\nPromotion gates (Champion+Intent vs Champion):")
    for gate, passed in gates.items():
        print(f"  {gate:<10} {'PASS' if passed else 'FAIL'}")
    print(f"\nVerdict: {verdict}  ({n_pass}/4 gates)")

    # Top intent features in combo model
    intent_contrib = [r for r in imp_combo if r["feature"] in usable]
    intent_total_pct = sum(r["importance_pct"] for r in intent_contrib)
    print(f"\nIntent features in combo: {intent_total_pct:.1f}% of total importance")
    for r in sorted(intent_contrib, key=lambda x: -x["importance_pct"])[:10]:
        bar = "█" * max(1, int(r["importance_pct"] / 2))
        print(f"  {r['feature']:<40} {r['importance_pct']:5.1f}%  {bar}")

    # ── Save ──────────────────────────────────────────────────────────────────
    meta_out = {
        "generated_at": NOW,
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "test_set": {
            "date_range": f"{test_or['date'].min()} → {test_or['date'].max()}",
            "races": r_champ["races"],
            "runners": r_champ["runners"],
        },
        "champion": "Core_V0_OR_Passport_V1",
        "variants": [
            {"variant": "Champion",          **{k: r_champ[k]  for k in ["auc","brier","sr","frame","races"]}},
            {"variant": "Intent-only",       **{k: r_intent[k] for k in ["auc","brier","sr","frame","races"]}},
            {"variant": "Champion+Intent",   **{k: r_combo[k]  for k in ["auc","brier","sr","frame","races"]}},
        ],
        "deltas": {"auc": auc_d, "brier": brier_d, "sr": sr_d, "frame": frame_d},
        "promotion_gates": gates,
        "n_gates_passed": n_pass,
        "verdict": verdict,
        "intent_features_used": usable,
        "intent_features_coverage_pct": round(int_hit, 2),
        "intent_importance_in_combo_pct": round(intent_total_pct, 2),
        "combo_feature_importance": imp_combo[:30],
        "intent_only_feature_importance": imp_intent[:20],
    }

    (RPT_DIR / "intent_layer_v1_latest.json").write_text(json.dumps(meta_out, indent=2))

    md = [
        "# Intent Layer V1 — Ablation vs Champion",
        f"Generated: {NOW}",
        "",
        "## Test Set",
        f"- 2025 unseen: {test_or['date'].min()} → {test_or['date'].max()}",
        f"- Races: {r_champ['races']:,} | Runners: {r_champ['runners']:,}",
        f"- Intent feature coverage: {int_hit:.1f}%",
        "",
        "## Results",
        "| Variant | AUC | AUC Δ | Brier | SR | Frame | Races |",
        "|---|---|---|---|---|---|---|",
        f"| Champion **← champion** | {auc_c:.4f} | +0.0000 | {brier_c:.4f} | {sr_c:.1%} | {fr_c:.1%} | {r_champ['races']:,} |",
        f"| Intent-only | {r_intent['auc']:.4f} | {r_intent['auc']-auc_c:+.4f} | {r_intent['brier']:.4f} | {r_intent['sr']:.1%} | {r_intent['frame']:.1%} | {r_intent['races']:,} |",
        f"| Champion+Intent **← challenger** | {r_combo['auc']:.4f} | {auc_d:+.4f} | {r_combo['brier']:.4f} | {r_combo['sr']:.1%} | {r_combo['frame']:.1%} | {r_combo['races']:,} |",
        "",
        "## Promotion Gates",
        "| Gate | Result |",
        "|---|---|",
    ] + [f"| {g} | {'PASS' if p else 'FAIL'} |" for g, p in gates.items()] + [
        "",
        f"## Verdict: **{verdict}** ({n_pass}/4 gates)",
        "",
        f"Δ AUC: {auc_d:+.4f}  Δ Brier: {brier_d:+.4f}  Δ SR: {sr_d:+.1%}  Δ Frame: {frame_d:+.1%}",
        "",
        "## Intent Features Used",
        f"({len(usable)} features, {intent_total_pct:.1f}% of combo model importance)",
        "",
        "| Feature | Coverage | Combo Importance % |",
        "|---|---|---|",
    ]
    imp_lookup = {r["feature"]: r["importance_pct"] for r in imp_combo}
    for c in usable:
        cov = round(coverage[c] * 100, 1)
        pct = imp_lookup.get(c, 0.0)
        md.append(f"| `{c}` | {cov:.1f}% | {pct:.1f}% |")

    md += [
        "",
        "## Top 15 Features (Champion+Intent combo)",
        "| Rank | Feature | Importance % |",
        "|---|---|---|",
    ]
    for i, r in enumerate(imp_combo[:15], 1):
        md.append(f"| {i} | `{r['feature']}` | {r['importance_pct']:.1f}% |")

    (RPT_DIR / "intent_layer_v1_latest.md").write_text("\n".join(md))
    print(f"\n  Reports → data/new_build/reports/intent_layer_v1_latest.md")

    # Save combo model if it adds signal
    if verdict in ("INTENT_ADDS_SIGNAL", "INTENT_MARGINAL"):
        combo_dir = MDL_DIR / "core_v0_or_passport_intent"
        combo_dir.mkdir(parents=True, exist_ok=True)
        with (combo_dir / "model.pkl").open("wb") as fh:
            pickle.dump({"model": m_combo, "feature_cols": f_combo,
                         "medians": med_combo.to_dict()}, fh)
        (combo_dir / "metadata.json").write_text(json.dumps({
            "generated_at": NOW,
            "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
            "velo_scoring_allowed": False,
            "verdict": verdict,
            "features": f_combo,
            "metrics_2025_unseen": r_combo,
        }, indent=2))
        print(f"  Combo model saved → data/new_build/models/core_v0_or_passport_intent/")

    return verdict


if __name__ == "__main__":
    run()
