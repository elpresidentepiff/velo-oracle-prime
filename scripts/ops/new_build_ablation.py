#!/usr/bin/env python3
"""
new_build_ablation.py
4-way ablation: V0 / V0_OR / Passport-only / V0_OR+Passport

Trains all 4 model variants on the same train split, evaluates on val split.
Produces comparison table + saves ablation metadata + MD report.

Requires passport_features.parquet to already exist.
Run new_build_passport_features.py first if missing.
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
RPT_DIR   = ROOT / "data" / "new_build" / "reports"
MDL_DIR   = ROOT / "data" / "new_build" / "models"

PASSPORT_PATH = TRAIN_DIR / "passport_features.parquet"

IDENTITY = {"race_id", "date", "course", "horse", "jockey", "trainer"}
TARGET   = {"won", "framed", "pos_num"}
BANNED   = {"rpr", "rpr_num", "rpr_vs_field", "ts_num", "sp_dec", "log_sp",
             "is_fav", "sp_rank", "implied_prob", "pos", "ovr_btn",
             "btn", "comment", "time", "target"}

PASSPORT_COLS = [
    "pp_career_runs", "pp_win_rate", "pp_place_rate",
    "pp_days_since_last", "pp_layoff", "pp_avg_sp_last5",
    "pp_jockey_continuity", "pp_course_seen", "pp_or_change_3",
    "pp_class_moved_up", "pp_class_moved_down",
]

V0_FEATURES = [
    "dist_f", "going_code", "is_aw", "field_size", "draw_num", "draw_pct",
    "age_num", "wgt_lbs", "or_vs_field",
    "release_window_score", "going_fit_score", "distance_fit_score",
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    "setup_run_flag", "cash_run_flag",
]

V0_OR_EXTRA = ["official_rating", "is_rated"]


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
    return round(sr / races, 4) if races else 0.0, round(fr / races, 4) if races else 0.0, races


def _train_lgbm(X_train, y_train, X_val, y_val):
    try:
        import lightgbm as lgb
        model = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=6,
            num_leaves=63, min_child_samples=50,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbose=-1, n_jobs=4,
        )
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)],
                  callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(0)])
        return model, "LightGBM"
    except ImportError:
        from sklearn.ensemble import GradientBoostingClassifier
        model = GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            min_samples_leaf=50, subsample=0.8, random_state=42,
        )
        model.fit(X_train, y_train)
        return model, "GBM"


def _prep(train, val, feature_cols):
    obj_cols = [c for c in feature_cols if train[c].dtype == object]
    for c in obj_cols:
        cats = pd.Categorical(pd.concat([train[c], val[c]], ignore_index=True)).categories
        train = train.copy()
        val   = val.copy()
        train[c] = pd.Categorical(train[c], categories=cats).codes
        val[c]   = pd.Categorical(val[c],   categories=cats).codes

    X_tr = train[feature_cols].copy()
    X_va = val[feature_cols].copy()
    medians = X_tr.median(numeric_only=True)
    X_tr = X_tr.fillna(medians)
    X_va = X_va.fillna(medians)
    return X_tr, X_va, train["won"], val["won"], medians


def _evaluate(variant_name, train, val, feature_cols):
    # Leakage check
    for b in BANNED:
        if b in feature_cols:
            raise AssertionError(f"LEAKAGE ABORT [{variant_name}]: {b}")
    rpr_hits = [c for c in feature_cols if "rpr" in c.lower()]
    if rpr_hits:
        raise AssertionError(f"RPR VIOLATION [{variant_name}]: {rpr_hits}")

    # Drop constant cols
    non_const = [c for c in feature_cols if train[c].nunique() > 1]
    dropped = set(feature_cols) - set(non_const)
    if dropped:
        print(f"    Dropped constant: {dropped}")
    feature_cols = non_const

    X_tr, X_va, y_tr, y_va, medians = _prep(train, val, feature_cols)

    model, model_type = _train_lgbm(X_tr, y_tr, X_va, y_va)

    probs = model.predict_proba(X_va)[:, 1]
    auc   = round(float(roc_auc_score(y_va, probs)), 4)
    brier = round(float(brier_score_loss(y_va, probs)), 4)
    val_c = val.copy()
    val_c["_prob"] = probs
    sr, fr, races = _race_metrics(val_c, "_prob")

    return {
        "variant": variant_name,
        "model_type": model_type,
        "n_features": len(feature_cols),
        "auc": auc,
        "brier": brier,
        "sr": sr,
        "frame": fr,
        "races": races,
    }, model, feature_cols, medians


def run():
    print("=== VÉLØ New Build — 4-Way Ablation ===")
    print()

    # --- Load base train/val ---
    print("Loading core_v0_or train/val ...")
    train_or = pd.read_parquet(TRAIN_DIR / "core_v0_or_train.parquet")
    val_or   = pd.read_parquet(TRAIN_DIR / "core_v0_or_val.parquet")
    print(f"  Train: {len(train_or):,}  Val: {len(val_or):,}")

    train_v0 = pd.read_parquet(TRAIN_DIR / "core_v0_train.parquet")
    val_v0   = pd.read_parquet(TRAIN_DIR / "core_v0_val.parquet")

    # --- Load passport features ---
    if not PASSPORT_PATH.exists():
        print(f"\nERROR: {PASSPORT_PATH} not found. Run new_build_passport_features.py first.")
        sys.exit(1)

    print("Loading passport features ...")
    pp = pd.read_parquet(PASSPORT_PATH)
    # Keep only passport cols
    pp = pp[["race_id", "horse"] + [c for c in PASSPORT_COLS if c in pp.columns]]
    pp_available = [c for c in PASSPORT_COLS if c in pp.columns]
    print(f"  Passport features available: {pp_available}")

    # Join passport to train/val
    def _join_pp(df):
        merged = df.merge(pp, on=["race_id", "horse"], how="left")
        hit_pct = merged[pp_available[0]].notna().mean() * 100 if pp_available else 0
        return merged, hit_pct

    train_or_pp, tr_hit = _join_pp(train_or)
    val_or_pp,   va_hit = _join_pp(val_or)
    print(f"  Train passport match: {tr_hit:.1f}%  Val: {va_hit:.1f}%")

    train_v0_pp, _ = _join_pp(train_v0)
    val_v0_pp,   _ = _join_pp(val_v0)

    results = []

    # --- Variant 1: V0 (original champion) ---
    print("\n[1/4] Core V0 ...")
    r1, m1, f1, med1 = _evaluate("V0", train_v0, val_v0, V0_FEATURES[:])
    results.append(r1)
    print(f"  AUC={r1['auc']}  SR={r1['sr']:.1%}  Frame={r1['frame']:.1%}")

    # --- Variant 2: V0_OR (new champion) ---
    print("\n[2/4] Core V0_OR (champion) ...")
    r2, m2, f2, med2 = _evaluate("V0_OR", train_or, val_or, V0_FEATURES + V0_OR_EXTRA)
    results.append(r2)
    print(f"  AUC={r2['auc']}  SR={r2['sr']:.1%}  Frame={r2['frame']:.1%}")

    # --- Variant 3: Passport-only ---
    print("\n[3/4] Passport-only ...")
    pp_only_cols = [c for c in pp_available if train_or_pp[c].notna().mean() > 0.05]
    if pp_only_cols:
        r3, m3, f3, med3 = _evaluate("Passport-only", train_or_pp, val_or_pp, pp_only_cols)
        results.append(r3)
        print(f"  AUC={r3['auc']}  SR={r3['sr']:.1%}  Frame={r3['frame']:.1%}")
    else:
        print("  SKIPPED — no passport cols with >5% coverage")
        r3 = {"variant": "Passport-only", "auc": None, "sr": None, "frame": None, "brier": None, "races": 0, "n_features": 0}
        results.append(r3)

    # --- Variant 4: V0_OR + Passport ---
    print("\n[4/4] V0_OR + Passport ...")
    combo_cols = V0_FEATURES + V0_OR_EXTRA + [c for c in pp_available if c not in V0_FEATURES + V0_OR_EXTRA]
    combo_cols = [c for c in combo_cols if c in train_or_pp.columns]
    r4, m4, f4, med4 = _evaluate("V0_OR+Passport", train_or_pp, val_or_pp, combo_cols)
    results.append(r4)
    print(f"  AUC={r4['auc']}  SR={r4['sr']:.1%}  Frame={r4['frame']:.1%}")

    # --- Summary table ---
    champion_auc = r2["auc"]
    print("\n")
    print("=" * 72)
    print("ABLATION RESULTS")
    print("=" * 72)
    header = f"{'Variant':<22} {'Features':>8} {'AUC':>8} {'AUC Δ':>8} {'SR':>7} {'Frame':>7} {'Races':>8}"
    print(header)
    print("-" * 72)
    for r in results:
        auc_s   = f"{r['auc']:.4f}" if r["auc"] is not None else "—"
        delta_s = f"{r['auc'] - champion_auc:+.4f}" if r["auc"] is not None else "—"
        sr_s    = f"{r['sr']:.1%}" if r["sr"] is not None else "—"
        fr_s    = f"{r['frame']:.1%}" if r["frame"] is not None else "—"
        races_s = f"{r['races']:,}" if r["races"] else "—"
        feat_s  = str(r.get("n_features", "—"))
        star    = " ← champion" if r["variant"] == "V0_OR" else ""
        print(f"{r['variant']:<22} {feat_s:>8} {auc_s:>8} {delta_s:>8} {sr_s:>7} {fr_s:>7} {races_s:>8}{star}")
    print("=" * 72)

    # Determine passport verdict
    if r4["auc"] is not None and r2["auc"] is not None:
        passport_delta = r4["auc"] - r2["auc"]
        if passport_delta > 0.003:
            verdict = "PASSPORT_ADDS_SIGNAL"
        elif passport_delta > 0:
            verdict = "PASSPORT_MARGINAL"
        elif passport_delta >= -0.002:
            verdict = "PASSPORT_NEUTRAL"
        else:
            verdict = "PASSPORT_HURTS"
    else:
        verdict = "PASSPORT_INSUFFICIENT_COVERAGE"

    print(f"\nPassport verdict: {verdict}")
    print(f"V0_OR+Passport vs V0_OR: AUC {r4['auc'] - r2['auc']:+.4f}  SR {(r4['sr'] or 0) - r2['sr']:+.1%}")

    # --- Save reports ---
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    meta_out = {
        "generated_at": now,
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "champion": "V0_OR",
        "passport_verdict": verdict,
        "passport_delta_auc": round(r4["auc"] - r2["auc"], 4) if r4["auc"] else None,
        "passport_delta_sr": round((r4["sr"] or 0) - r2["sr"], 4) if r4["sr"] else None,
        "passport_features_used": pp_available,
        "variants": results,
    }
    (RPT_DIR / "ablation_latest.json").write_text(json.dumps(meta_out, indent=2))

    md_lines = [
        "# 4-Way Ablation — V0 / V0_OR / Passport-only / V0_OR+Passport",
        f"Generated: {now}",
        "",
        "## Results",
        f"| Variant | Features | AUC | AUC Δ vs V0_OR | SR | Frame | Races |",
        f"|---|---|---|---|---|---|---|",
    ]
    for r in results:
        auc_s   = f"{r['auc']:.4f}" if r["auc"] is not None else "—"
        delta_s = f"{r['auc'] - champion_auc:+.4f}" if r["auc"] is not None else "—"
        sr_s    = f"{r['sr']:.1%}" if r["sr"] is not None else "—"
        fr_s    = f"{r['frame']:.1%}" if r["frame"] is not None else "—"
        races_s = f"{r['races']:,}" if r["races"] else "—"
        tag     = " **← champion**" if r["variant"] == "V0_OR" else ""
        md_lines.append(f"| {r['variant']}{tag} | {r.get('n_features','—')} | {auc_s} | {delta_s} | {sr_s} | {fr_s} | {races_s} |")

    md_lines += [
        "",
        f"## Passport Verdict: **{verdict}**",
        "",
        f"V0_OR+Passport vs V0_OR champion:",
        f"- AUC delta: {r4['auc'] - r2['auc']:+.4f}" if r4["auc"] else "- AUC: —",
        f"- SR delta: {(r4['sr'] or 0) - r2['sr']:+.1%}" if r4["sr"] else "- SR: —",
        "",
        "## Passport Features Used",
    ] + [f"- `{c}`" for c in pp_available] + [
        "",
        "## Verdicts",
        "| Classification | Meaning |",
        "|---|---|",
        "| PASSPORT_ADDS_SIGNAL | AUC delta > +0.003 vs champion — passport is worth adding |",
        "| PASSPORT_MARGINAL | AUC delta 0–0.003 — small lift, costs feature complexity |",
        "| PASSPORT_NEUTRAL | AUC within ±0.002 — no meaningful change |",
        "| PASSPORT_HURTS | AUC drops > 0.002 — passport adds noise |",
        "| PASSPORT_INSUFFICIENT_COVERAGE | < 5% passport coverage in training set |",
    ]

    (RPT_DIR / "ablation_latest.md").write_text("\n".join(md_lines))
    print(f"\n  Reports → {(RPT_DIR / 'ablation_latest.md').relative_to(ROOT)}")

    # Save V0_OR+Passport model if it improves
    if verdict in ("PASSPORT_ADDS_SIGNAL", "PASSPORT_MARGINAL"):
        combo_dir = MDL_DIR / "core_v0_or_passport"
        combo_dir.mkdir(parents=True, exist_ok=True)
        with (combo_dir / "core_v0_or_passport_model.pkl").open("wb") as f:
            pickle.dump({"model": m4, "feature_cols": f4, "medians": med4.to_dict()}, f)
        combo_meta = {
            "generated_at": now,
            "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
            "velo_scoring_allowed": False,
            "model_type": r4.get("model_type"),
            "features": f4,
            "metrics": r4,
            "passport_verdict": verdict,
        }
        (combo_dir / "core_v0_or_passport_metadata.json").write_text(json.dumps(combo_meta, indent=2))
        print(f"  V0_OR+Passport model saved → {combo_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    run()
