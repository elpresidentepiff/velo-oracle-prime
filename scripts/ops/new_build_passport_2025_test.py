#!/usr/bin/env python3
"""
new_build_passport_2025_test.py
Full 2025 unseen test — 4-way: V0 / V0_OR / Passport-only / V0_OR+Passport

Test set: 2025-01-01 → 2025-07-05 (completely unseen, held back from all training).
Passport-only model retrained here from train split only (model not saved from ablation).

Promotion rule:
  V0_OR+Passport is promoted ONLY if it beats V0_OR on ALL of:
    AUC / Brier / top-pick SR / top-3 Frame

Outputs:
  data/new_build/reports/v0_or_passport_2025_unseen_test_latest.md
  data/new_build/reports/v0_or_passport_2025_unseen_test_latest.json

Classification:
  PASSPORT_CHALLENGER_PROMOTE     — beats V0_OR on all 4 metrics
  PASSPORT_CHALLENGER_HOLD        — beats on some but not all
  PASSPORT_CHALLENGER_RETRAIN_REQUIRED — underperforms V0_OR
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

BANNED = {"rpr", "rpr_num", "rpr_vs_field", "ts_num", "sp_dec", "log_sp",
          "is_fav", "sp_rank", "implied_prob", "pos", "ovr_btn",
          "btn", "comment", "time", "target"}

V0_FEATURES = [
    "dist_f", "going_code", "is_aw", "field_size", "draw_num", "draw_pct",
    "age_num", "wgt_lbs", "or_vs_field",
    "release_window_score", "going_fit_score", "distance_fit_score",
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    "setup_run_flag", "cash_run_flag",
]

PASSPORT_COLS = [
    "pp_career_runs", "pp_win_rate", "pp_place_rate",
    "pp_days_since_last", "pp_layoff", "pp_avg_sp_last5",
    "pp_jockey_continuity", "pp_course_seen", "pp_or_change_3",
    "pp_class_moved_up", "pp_class_moved_down",
]

OR_EXTRA = ["official_rating", "is_rated"]

NOW = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── helpers ───────────────────────────────────────────────────────────────────

def race_metrics(df, prob_col):
    sr_hits = frame_hits = races = 0
    for _, g in df.groupby("race_id"):
        if len(g) < 2:
            continue
        races += 1
        if g.loc[g[prob_col].idxmax(), "won"] == 1:
            sr_hits += 1
        if g.nlargest(3, prob_col)["won"].sum() >= 1:
            frame_hits += 1
    sr = sr_hits / races if races else 0.0
    fr = frame_hits / races if races else 0.0
    return round(sr, 4), round(fr, 4), races


def full_eval(df, prob_col):
    y = df["won"]
    p = df[prob_col]
    auc   = round(float(roc_auc_score(y, p)), 4)
    brier = round(float(brier_score_loss(y, p)), 4)
    sr, fr, races = race_metrics(df, prob_col)
    return {"auc": auc, "brier": brier, "sr": sr, "frame": fr,
            "races": races, "runners": len(df)}


def prep(df, feature_cols, medians):
    df = df.copy()
    obj_cols = [c for c in feature_cols if c in df.columns and df[c].dtype == object]
    for c in obj_cols:
        df[c] = pd.Categorical(df[c]).codes
    for c in feature_cols:
        if c not in df.columns:
            df[c] = medians.get(c, 0.0)
    X = df[feature_cols].copy()
    for c in feature_cols:
        fill = medians[c] if c in medians else 0.0
        X[c] = X[c].fillna(fill)
    return X


def leakage_check(feature_cols, label):
    for b in BANNED:
        if b in feature_cols:
            raise AssertionError(f"LEAKAGE [{label}]: {b}")
    rpr_hits = [c for c in feature_cols if "rpr" in c.lower()]
    if rpr_hits:
        raise AssertionError(f"RPR_VIOLATION [{label}]: {rpr_hits}")
    return "PASS"


def calibration_by_band(df, prob_col, bands=None):
    if bands is None:
        bands = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 1.01]
    rows = []
    for i in range(len(bands) - 1):
        lo, hi = bands[i], bands[i + 1]
        sub = df[(df[prob_col] >= lo) & (df[prob_col] < hi)]
        if len(sub) == 0:
            continue
        actual_wr = sub["won"].mean()
        pred_wr   = sub[prob_col].mean()
        rows.append({
            "band": f"{lo:.2f}–{hi:.2f}",
            "n": len(sub),
            "pred_prob": round(float(pred_wr), 4),
            "actual_wr": round(float(actual_wr), 4),
            "over_under": round(float(actual_wr - pred_wr), 4),
        })
    return rows


def subgroup(df, prob_col, col, label_fn, min_races=50):
    rows = []
    df = df.copy()
    df["_label"] = df[col].map(label_fn) if callable(label_fn) else df[col].astype(str)
    for lbl, sub in df.groupby("_label"):
        _, _, races = race_metrics(sub, prob_col)
        if races < min_races:
            continue
        m = full_eval(sub, prob_col)
        rows.append({"group": str(lbl), **m})
    return sorted(rows, key=lambda r: -r["races"])


def train_lgbm(X_tr, y_tr, X_va, y_va):
    try:
        import lightgbm as lgb
        m = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=6,
            num_leaves=63, min_child_samples=50,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbose=-1, n_jobs=4,
        )
        m.fit(X_tr, y_tr, eval_set=[(X_va, y_va)],
              callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(0)])
        return m, "LightGBM"
    except ImportError:
        from sklearn.ensemble import GradientBoostingClassifier
        m = GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            min_samples_leaf=50, subsample=0.8, random_state=42)
        m.fit(X_tr, y_tr)
        return m, "GBM"


def train_variant(train, val, feature_cols):
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
    model, mtype = train_lgbm(X_tr, train["won"], X_va, val["won"])
    return model, non_const, meds


# ── load data ─────────────────────────────────────────────────────────────────

def run():
    print("=== 2025 Unseen Test — 4-Way Ablation ===")
    print()

    print("Loading train/val/test splits ...")
    train_or = pd.read_parquet(TRAIN_DIR / "core_v0_or_train.parquet")
    val_or   = pd.read_parquet(TRAIN_DIR / "core_v0_or_val.parquet")
    test_or  = pd.read_parquet(TRAIN_DIR / "core_v0_or_test.parquet")
    train_v0 = pd.read_parquet(TRAIN_DIR / "core_v0_train.parquet")
    val_v0   = pd.read_parquet(TRAIN_DIR / "core_v0_val.parquet")
    test_v0  = pd.read_parquet(TRAIN_DIR / "core_v0_test.parquet")
    print(f"  Train: {len(train_or):,}  Val: {len(val_or):,}  Test: {len(test_or):,}")
    print(f"  Test date range: {test_or['date'].min()} → {test_or['date'].max()}")

    print("Loading passport features ...")
    pp = pd.read_parquet(TRAIN_DIR / "passport_features.parquet")
    pp_cols = [c for c in PASSPORT_COLS if c in pp.columns]

    def join_pp(df):
        return df.merge(pp[["race_id", "horse"] + pp_cols], on=["race_id", "horse"], how="left")

    train_pp = join_pp(train_or)
    val_pp   = join_pp(val_or)
    test_pp  = join_pp(test_or)
    hit_pct  = test_pp[pp_cols[0]].notna().mean() * 100 if pp_cols else 0
    print(f"  Test passport match: {hit_pct:.1f}%")

    # ── Variant 1: V0 ────────────────────────────────────────────────────────
    print("\n[1/4] Core V0 (original champion) ...")
    with open(MDL_DIR / "core_v0" / "core_v0_model.pkl", "rb") as f:
        b1 = pickle.load(f)
    m1, f1, med1 = b1["model"], b1["feature_cols"], pd.Series(b1["medians"])
    leakage_check(f1, "V0")
    X1 = prep(test_v0, f1, med1)
    test_v0["_p"] = m1.predict_proba(X1)[:, 1]
    r1 = full_eval(test_v0, "_p")
    print(f"  AUC={r1['auc']}  Brier={r1['brier']}  SR={r1['sr']:.1%}  Frame={r1['frame']:.1%}  Races={r1['races']:,}")

    # ── Variant 2: V0_OR (champion) ──────────────────────────────────────────
    print("\n[2/4] Core V0_OR (champion) ...")
    with open(MDL_DIR / "core_v0_or" / "core_v0_or_model.pkl", "rb") as f:
        b2 = pickle.load(f)
    m2, f2, med2 = b2["model"], b2["feature_cols"], pd.Series(b2["medians"])
    leakage_check(f2, "V0_OR")
    X2 = prep(test_or, f2, med2)
    test_or["_p"] = m2.predict_proba(X2)[:, 1]
    r2 = full_eval(test_or, "_p")
    print(f"  AUC={r2['auc']}  Brier={r2['brier']}  SR={r2['sr']:.1%}  Frame={r2['frame']:.1%}  Races={r2['races']:,}")

    # ── Variant 3: Passport-only (retrain from train split) ──────────────────
    print("\n[3/4] Passport-only (retrain from train) ...")
    pp_only_cols = [c for c in pp_cols if train_pp[c].notna().mean() > 0.05]
    if pp_only_cols:
        leakage_check(pp_only_cols, "Passport-only")
        m3, f3, med3 = train_variant(train_pp, val_pp, pp_only_cols)
        X3 = prep(test_pp, f3, med3)
        test_pp["_p3"] = m3.predict_proba(X3)[:, 1]
        r3 = full_eval(test_pp, "_p3")
        print(f"  AUC={r3['auc']}  Brier={r3['brier']}  SR={r3['sr']:.1%}  Frame={r3['frame']:.1%}  Races={r3['races']:,}")
    else:
        print("  SKIPPED — insufficient passport coverage")
        r3 = {"variant": "Passport-only", "auc": None, "brier": None, "sr": None,
              "frame": None, "races": 0, "runners": 0}
        m3 = f3 = med3 = None
        test_pp["_p3"] = np.nan

    # ── Variant 4: V0_OR+Passport (challenger) ───────────────────────────────
    print("\n[4/4] V0_OR+Passport (challenger) ...")
    with open(MDL_DIR / "core_v0_or_passport" / "core_v0_or_passport_model.pkl", "rb") as f:
        b4 = pickle.load(f)
    m4, f4, med4 = b4["model"], b4["feature_cols"], pd.Series(b4["medians"])
    leakage_check(f4, "V0_OR+Passport")
    # Need to add missing pp cols to test_or — use test_pp which already has them
    X4 = prep(test_pp, f4, med4)
    test_pp["_p4"] = m4.predict_proba(X4)[:, 1]
    r4 = full_eval(test_pp, "_p4")
    print(f"  AUC={r4['auc']}  Brier={r4['brier']}  SR={r4['sr']:.1%}  Frame={r4['frame']:.1%}  Races={r4['races']:,}")

    # ── Calibration (V0_OR and challenger) ───────────────────────────────────
    print("\n── Calibration (V0_OR champion, 2025 test) ──")
    cal_champion   = calibration_by_band(test_or, "_p")
    cal_challenger = calibration_by_band(test_pp, "_p4")
    for row in cal_champion:
        print(f"  {row['band']}  n={row['n']:>5}  pred={row['pred_prob']:.3f}  actual={row['actual_wr']:.3f}  over/under={row['over_under']:+.3f}")

    # ── Subgroup: field-size, class, going ───────────────────────────────────
    def field_band(x):
        try:
            x = int(x)
        except Exception:
            return "Unknown"
        if x <= 7:  return "<=7 runners"
        if x <= 11: return "8-11 runners"
        if x <= 15: return "12-15 runners"
        return "16+ runners"

    def class_band(x):
        try:
            x = int(x)
        except Exception:
            return "Unknown"
        if x <= 2:  return "Class 1-2"
        if x <= 4:  return "Class 3-4"
        if x <= 6:  return "Class 5-6"
        return "Class 7+"

    def going_band(x):
        try:
            x = float(x)
        except Exception:
            return "Unknown"
        if x <= 1.5: return "Firm"
        if x <= 2.5: return "Good"
        if x <= 3.5: return "GoodSoft"
        if x <= 4.5: return "Soft"
        if x <= 5.5: return "Heavy"
        return "AW"

    print("\n── Field-size subgroup (V0_OR champion) ──")
    fsub = subgroup(test_or, "_p", "field_size", field_band)
    for r in fsub:
        print(f"  {r['group']:<18}  AUC={r['auc']}  SR={r['sr']:.1%}  Frame={r['frame']:.1%}  Races={r['races']:,}")

    print("\n── Class subgroup (V0_OR champion) ──")
    csub = subgroup(test_or, "_p", "class_num", class_band) if "class_num" in test_or.columns else []
    for r in csub:
        print(f"  {r['group']:<16}  AUC={r['auc']}  SR={r['sr']:.1%}  Frame={r['frame']:.1%}  Races={r['races']:,}")

    print("\n── Going subgroup (V0_OR champion) ──")
    gsub = subgroup(test_or, "_p", "going_code", going_band) if "going_code" in test_or.columns else []
    for r in gsub:
        print(f"  {r['group']:<14}  AUC={r['auc']}  SR={r['sr']:.1%}  Frame={r['frame']:.1%}  Races={r['races']:,}")

    # ── Promotion decision ────────────────────────────────────────────────────
    beats_auc   = r4["auc"]   > r2["auc"]
    beats_brier = r4["brier"] < r2["brier"]
    beats_sr    = r4["sr"]    > r2["sr"]
    beats_frame = r4["frame"] > r2["frame"]
    gates = {"auc": beats_auc, "brier": beats_brier, "sr": beats_sr, "frame": beats_frame}
    n_pass = sum(gates.values())

    if n_pass == 4:
        classification = "PASSPORT_CHALLENGER_PROMOTE"
    elif n_pass >= 2:
        classification = "PASSPORT_CHALLENGER_HOLD"
    else:
        classification = "PASSPORT_CHALLENGER_RETRAIN_REQUIRED"

    auc_delta   = round(r4["auc"]   - r2["auc"],   4)
    brier_delta = round(r4["brier"] - r2["brier"],  4)
    sr_delta    = round(r4["sr"]    - r2["sr"],     4)
    frame_delta = round(r4["frame"] - r2["frame"],  4)

    print("\n")
    print("=" * 76)
    print("2025 UNSEEN TEST — RESULTS")
    print("=" * 76)
    header = f"{'Variant':<22} {'AUC':>8} {'AUC Δ':>8} {'Brier':>7} {'SR':>7} {'Frame':>7} {'Races':>8}"
    print(header)
    print("-" * 76)
    champ_auc = r2["auc"]
    for r, label in [(r1, "V0"), (r2, "V0_OR"), (r3, "Passport-only"), (r4, "V0_OR+Passport")]:
        auc_s   = f"{r['auc']:.4f}" if r["auc"] else "—"
        delta_s = f"{r['auc'] - champ_auc:+.4f}" if r["auc"] else "—"
        br_s    = f"{r['brier']:.4f}" if r["brier"] else "—"
        sr_s    = f"{r['sr']:.1%}" if r["sr"] is not None else "—"
        fr_s    = f"{r['frame']:.1%}" if r["frame"] is not None else "—"
        races_s = f"{r['races']:,}" if r["races"] else "—"
        star    = " ← champion" if label == "V0_OR" else (" ← challenger" if label == "V0_OR+Passport" else "")
        print(f"{label:<22} {auc_s:>8} {delta_s:>8} {br_s:>7} {sr_s:>7} {fr_s:>7} {races_s:>8}{star}")
    print("=" * 76)

    print(f"\nPromotion gates (challenger vs champion):")
    for gate, passed in gates.items():
        mark = "PASS" if passed else "FAIL"
        print(f"  {gate:<10} {mark}")
    print(f"\nClassification: {classification}")

    # ── Save reports ─────────────────────────────────────────────────────────
    def _r(r, label):
        return {
            "variant": label,
            "auc": r.get("auc"),
            "brier": r.get("brier"),
            "sr": r.get("sr"),
            "frame": r.get("frame"),
            "races": r.get("races"),
            "runners": r.get("runners"),
        }

    meta_out = {
        "generated_at": NOW,
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "test_set": {
            "date_range": f"{test_or['date'].min()} → {test_or['date'].max()}",
            "races": r2["races"],
            "runners": r2["runners"],
        },
        "leakage_checks": {
            "V0": "PASS",
            "V0_OR": "PASS",
            "Passport-only": "PASS" if pp_only_cols else "SKIPPED",
            "V0_OR+Passport": "PASS",
        },
        "rpr_violations": 0,
        "variants": [_r(r1, "V0"), _r(r2, "V0_OR"), _r(r3, "Passport-only"), _r(r4, "V0_OR+Passport")],
        "champion": "V0_OR",
        "challenger": "V0_OR+Passport",
        "deltas": {
            "auc": auc_delta,
            "brier": brier_delta,
            "sr": sr_delta,
            "frame": frame_delta,
        },
        "promotion_gates": gates,
        "n_gates_passed": n_pass,
        "classification": classification,
        "calibration_champion": cal_champion,
        "calibration_challenger": cal_challenger,
        "subgroups": {
            "field_size": fsub,
            "class": csub,
            "going": gsub,
        },
        "passport_features_tested": pp_cols,
        "passport_coverage_test_pct": round(hit_pct, 2),
    }

    json_path = RPT_DIR / "v0_or_passport_2025_unseen_test_latest.json"
    json_path.write_text(json.dumps(meta_out, indent=2))

    # ── MD report ─────────────────────────────────────────────────────────────
    md = [
        "# V0_OR+Passport — 2025 Unseen Test",
        f"Generated: {NOW}",
        "",
        "## Test Set",
        f"- Date range: {test_or['date'].min()} → {test_or['date'].max()}",
        f"- Races: {r2['races']:,}",
        f"- Runners: {r2['runners']:,}",
        f"- Passport coverage: {hit_pct:.1f}%",
        "",
        "## Leakage Checks",
        "- V0: PASS",
        "- V0_OR: PASS",
        f"- Passport-only: {'PASS' if pp_only_cols else 'SKIPPED'}",
        "- V0_OR+Passport: PASS",
        "- RPR violations: 0",
        "",
        "## Results",
        "| Variant | AUC | AUC Δ vs V0_OR | Brier | SR | Frame | Races |",
        "|---|---|---|---|---|---|---|",
    ]
    for r, label in [(r1, "V0"), (r2, "V0_OR"), (r3, "Passport-only"), (r4, "V0_OR+Passport")]:
        a   = f"{r['auc']:.4f}" if r["auc"] else "—"
        d   = f"{r['auc'] - champ_auc:+.4f}" if r["auc"] else "—"
        b   = f"{r['brier']:.4f}" if r["brier"] else "—"
        s   = f"{r['sr']:.1%}" if r["sr"] is not None else "—"
        fr  = f"{r['frame']:.1%}" if r["frame"] is not None else "—"
        rc  = f"{r['races']:,}" if r["races"] else "—"
        tag = " **← champion**" if label == "V0_OR" else (" **← challenger**" if label == "V0_OR+Passport" else "")
        md.append(f"| {label}{tag} | {a} | {d} | {b} | {s} | {fr} | {rc} |")

    md += [
        "",
        "## Promotion Gates (challenger vs champion)",
        "| Gate | Result |",
        "|---|---|",
    ]
    for gate, passed in gates.items():
        md.append(f"| {gate} | {'PASS' if passed else 'FAIL'} |")

    md += [
        "",
        f"## Classification: **{classification}**",
        "",
        "| Class | Meaning |",
        "|---|---|",
        "| PASSPORT_CHALLENGER_PROMOTE | All 4 gates PASS — promote challenger to champion |",
        "| PASSPORT_CHALLENGER_HOLD | 2–3 gates PASS — hold as challenger, gather more evidence |",
        "| PASSPORT_CHALLENGER_RETRAIN_REQUIRED | 0–1 gates PASS — revisit feature set |",
        "",
        "## Calibration (V0_OR champion, 2025 test)",
        "| Prob band | n | Predicted | Actual WR | Over/Under |",
        "|---|---|---|---|---|",
    ]
    for row in cal_champion:
        md.append(f"| {row['band']} | {row['n']:,} | {row['pred_prob']:.3f} | {row['actual_wr']:.3f} | {row['over_under']:+.3f} |")

    md += [
        "",
        "## Calibration (V0_OR+Passport challenger, 2025 test)",
        "| Prob band | n | Predicted | Actual WR | Over/Under |",
        "|---|---|---|---|---|",
    ]
    for row in cal_challenger:
        md.append(f"| {row['band']} | {row['n']:,} | {row['pred_prob']:.3f} | {row['actual_wr']:.3f} | {row['over_under']:+.3f} |")

    if fsub:
        md += ["", "## Field-Size Subgroup (V0_OR, 2025 test)",
               "| Group | AUC | SR | Frame | Races |", "|---|---|---|---|---|"]
        for r in fsub:
            md.append(f"| {r['group']} | {r['auc']} | {r['sr']:.1%} | {r['frame']:.1%} | {r['races']:,} |")

    if csub:
        md += ["", "## Class Subgroup (V0_OR, 2025 test)",
               "| Group | AUC | SR | Frame | Races |", "|---|---|---|---|---|"]
        for r in csub:
            md.append(f"| {r['group']} | {r['auc']} | {r['sr']:.1%} | {r['frame']:.1%} | {r['races']:,} |")

    if gsub:
        md += ["", "## Going Subgroup (V0_OR, 2025 test)",
               "| Group | AUC | SR | Frame | Races |", "|---|---|---|---|---|"]
        for r in gsub:
            md.append(f"| {r['group']} | {r['auc']} | {r['sr']:.1%} | {r['frame']:.1%} | {r['races']:,} |")

    md += [
        "",
        "## Passport Features Tested",
    ] + [f"- `{c}`" for c in pp_cols] + [
        "",
        "## Decision",
        f"Champion: **V0_OR** (AUC={r2['auc']}, SR={r2['sr']:.1%}, Frame={r2['frame']:.1%})",
        f"Challenger: **V0_OR+Passport** (AUC={r4['auc']}, SR={r4['sr']:.1%}, Frame={r4['frame']:.1%})",
        f"Δ AUC: {auc_delta:+.4f}  Δ Brier: {brier_delta:+.4f}  Δ SR: {sr_delta:+.1%}  Δ Frame: {frame_delta:+.1%}",
        f"Gates passed: {n_pass}/4",
        f"**{classification}**",
    ]

    md_path = RPT_DIR / "v0_or_passport_2025_unseen_test_latest.md"
    md_path.write_text("\n".join(md))

    print(f"\n  JSON → {json_path.relative_to(ROOT)}")
    print(f"  MD   → {md_path.relative_to(ROOT)}")
    print(f"\n  Classification: {classification}")


if __name__ == "__main__":
    run()
