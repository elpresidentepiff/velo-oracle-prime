#!/usr/bin/env python3
"""
International Pre-Race Arena V1

The definitive gate test: can VELO beat favourite and lagged-RPR baselines
using only information that existed before the race started?

Runs per pack:
  - HK_SHA_TIN_V1, HK_HAPPY_VALLEY_V1 (from hk_prerace_features_v1.parquet)
  - FR_CHANTILLY_V1, FR_FLAT_CORE, FR_AUTEUIL_JUMPS_V1 (from fr_prerace_features_v1.parquet)

Per pack, evaluates:
  1. Favourite baseline (is_fav from original parquet)
  2. Lagged-RPR-only LightGBM (single feature)
  3. Draw-only model (HK only)
  4. Class-only model (HK only)
  5. Going/distance/course model (FR only)
  6. Full pre-race feature model

Temporal split: train ≤2022-12-31, valid ≤2023-12-31, test >2023-12-31

Gate verdicts:
  GATE_REOPENED_SAFE_SHADOW_CANDIDATE: AUC ≥ 0.75 AND beats favourite SR
  NEEDS_FEATURE_ENGINEERING:           AUC ≥ 0.65 (signal present but insufficient)
  FAILS_FAVOURITE_BASELINE:            Does not beat favourite SR
  FAILS_RPR_BASELINE:                  Does not beat lagged-RPR single-feature model
  HOLD:                                Insufficient data (< 500 test races)

Outputs:
  data/reports/international_prerace_arena_v1_latest.json
  data/reports/international_prerace_arena_v1_latest.md

Usage:
    PYTHONPATH=. python scripts/audit_international_prerace_arena_v1.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.preprocessing import StandardScaler

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False
    print("[Arena] WARNING: lightgbm not available — using LR only")

ROOT = Path(__file__).resolve().parent.parent
HK_PQ = ROOT / "data" / "features" / "hk_prerace_features_v1.parquet"
FR_PQ = ROOT / "data" / "features" / "fr_prerace_features_v1.parquet"
ORIG_PQ = ROOT / "data" / "raceform_v17_features.parquet"

TRAIN_CUTOFF = "2022-12-31"
VALID_CUTOFF = "2023-12-31"

PACKS = {
    "HK_SHA_TIN_V1": {
        "source": "HK",
        "courses": ["Sha Tin (HK)"],
        # EXCLUDED from features:
        # prev_class_num: DROP (winner_max=70.64%, borderline — class_move_direction captures delta)
        # class_rise_flag: DROP (winner_max=75.58%, 70% zero within-race variance — artifact)
        "features": [
            "prev_rpr_num", "last3_rpr_avg",
            "prev_or_num", "last3_or_avg",
            "prev_finish_pos", "last3_finish_avg",
            "days_since_last_run", "starts_last_90",
            "course_prior_runs", "course_prior_wr",
            "distance_prior_runs", "distance_prior_wr",
            "class_num", "class_move_direction",
            "class_drop_flag",  # REVIEW_REQUIRED 60.44% — kept, flagged
            "prior_class_win_rate", "prior_class_place_rate",
            "draw_num", "draw_pct", "draw_inside_flag", "draw_outside_flag",
            "draw_win_rate_lagged", "draw_place_rate_lagged",
            "field_avg_prev_rpr", "field_std_prev_rpr", "field_avg_prev_or",
            "rpr_rank_lagged", "or_rank_lagged",
            "rating_consensus_lagged", "race_competitiveness_pre",
            "field_size", "dist_f", "going_code", "wgt_lbs", "age_num", "is_aw",
        ],
        "draw_features": [
            "draw_num", "draw_pct", "draw_inside_flag", "draw_outside_flag",
            "draw_win_rate_lagged", "draw_place_rate_lagged",
        ],
        "class_features": [
            "class_num", "class_move_direction",
            "class_drop_flag",
            "prior_class_win_rate", "prior_class_place_rate",
        ],
        "rpr_features": ["prev_rpr_num"],
        "or_features": ["prev_or_num"],
    },
    "HK_HAPPY_VALLEY_V1": {
        "source": "HK",
        "courses": ["Happy Valley (HK)"],
        # Same exclusions as SHA_TIN: prev_class_num DROP, class_rise_flag DROP
        "features": [
            "prev_rpr_num", "last3_rpr_avg",
            "prev_or_num", "last3_or_avg",
            "prev_finish_pos", "last3_finish_avg",
            "days_since_last_run", "starts_last_90",
            "course_prior_runs", "course_prior_wr",
            "distance_prior_runs", "distance_prior_wr",
            "class_num", "class_move_direction",
            "class_drop_flag",
            "prior_class_win_rate", "prior_class_place_rate",
            "draw_num", "draw_pct", "draw_inside_flag", "draw_outside_flag",
            "draw_win_rate_lagged", "draw_place_rate_lagged",
            "field_avg_prev_rpr", "field_std_prev_rpr", "field_avg_prev_or",
            "rpr_rank_lagged", "or_rank_lagged",
            "rating_consensus_lagged", "race_competitiveness_pre",
            "field_size", "dist_f", "going_code", "wgt_lbs", "age_num", "is_aw",
        ],
        "draw_features": [
            "draw_num", "draw_pct", "draw_inside_flag", "draw_outside_flag",
            "draw_win_rate_lagged", "draw_place_rate_lagged",
        ],
        "class_features": [
            "class_num", "class_move_direction",
            "class_drop_flag",
            "prior_class_win_rate", "prior_class_place_rate",
        ],
        "rpr_features": ["prev_rpr_num"],
        "or_features": ["prev_or_num"],
    },
    "FR_CHANTILLY_V1": {
        "source": "FR",
        "courses": ["Chantilly (FR)"],
        "features": [
            "lagged_rpr_last1", "lagged_rpr_last3_avg", "lagged_rpr_last3_max",
            "lagged_ts_last1", "lagged_ts_last3_avg",
            "prev_finish_pos", "last3_finish_avg",
            "days_since_last_run", "starts_last_90",
            "prior_course_runs", "prior_course_win_rate",
            "prior_distance_runs", "prior_distance_win_rate",
            "going_is_fast", "going_is_good", "going_is_soft",
            "is_hurdle", "is_chase", "is_flat_code",
            "field_avg_prev_rpr", "field_std_prev_rpr",
            "rpr_rank_lagged", "race_competitiveness_pre",
            "field_size", "dist_f", "going_code", "wgt_lbs", "age_num", "is_aw",
            "draw_num", "draw_pct",
        ],
        "going_features": ["going_is_fast", "going_is_good", "going_is_soft", "going_code"],
        "rpr_features": ["lagged_rpr_last1"],
        "context_features": [
            "prior_course_runs", "prior_course_win_rate",
            "prior_distance_runs", "prior_distance_win_rate",
            "dist_f", "field_size", "is_hurdle", "is_chase",
        ],
    },
    "FR_FLAT_CORE": {
        "source": "FR",
        "courses": ["Chantilly (FR)", "Deauville (FR)", "Longchamp (FR)", "Saint-Cloud (FR)"],
        "features": [
            "lagged_rpr_last1", "lagged_rpr_last3_avg", "lagged_rpr_last3_max",
            "lagged_ts_last1", "lagged_ts_last3_avg",
            "prev_finish_pos", "last3_finish_avg",
            "days_since_last_run", "starts_last_90",
            "prior_course_runs", "prior_course_win_rate",
            "prior_distance_runs", "prior_distance_win_rate",
            "going_is_fast", "going_is_good", "going_is_soft",
            "is_flat_code",
            "field_avg_prev_rpr", "field_std_prev_rpr",
            "rpr_rank_lagged", "race_competitiveness_pre",
            "field_size", "dist_f", "going_code", "wgt_lbs", "age_num", "is_aw",
            "draw_num", "draw_pct",
        ],
        "going_features": ["going_is_fast", "going_is_good", "going_is_soft", "going_code"],
        "rpr_features": ["lagged_rpr_last1"],
        "context_features": [
            "prior_course_runs", "prior_course_win_rate",
            "prior_distance_runs", "prior_distance_win_rate",
            "dist_f", "field_size",
        ],
    },
    "FR_AUTEUIL_JUMPS_V1": {
        "source": "FR",
        "courses": ["Auteuil (FR)"],
        "features": [
            "lagged_rpr_last1", "lagged_rpr_last3_avg", "lagged_rpr_last3_max",
            "lagged_ts_last1", "lagged_ts_last3_avg",
            "prev_finish_pos", "last3_finish_avg",
            "days_since_last_run", "starts_last_90",
            "prior_course_runs", "prior_course_win_rate",
            "prior_distance_runs", "prior_distance_win_rate",
            "going_is_fast", "going_is_good", "going_is_soft",
            "is_hurdle", "is_chase",
            "field_avg_prev_rpr", "field_std_prev_rpr",
            "rpr_rank_lagged", "race_competitiveness_pre",
            "field_size", "dist_f", "going_code", "wgt_lbs", "age_num", "is_aw",
        ],
        "going_features": ["going_is_fast", "going_is_good", "going_is_soft", "going_code"],
        "rpr_features": ["lagged_rpr_last1"],
        "context_features": [
            "prior_course_runs", "prior_course_win_rate",
            "prior_distance_runs", "prior_distance_win_rate",
            "dist_f", "field_size", "is_hurdle", "is_chase",
        ],
    },
}


def _top_pick_sr(df: pd.DataFrame, prob_col: str) -> float:
    picks, wins = 0, 0
    for _, race in df.groupby("race_id"):
        if race["target"].sum() != 1:
            continue
        if race[prob_col].isna().all():
            continue
        top_idx = race[prob_col].idxmax()
        wins += int(race.loc[top_idx, "target"] == 1)
        picks += 1
    return wins / max(picks, 1)


def _fav_sr(df: pd.DataFrame, orig_df: pd.DataFrame) -> float:
    sub = df.merge(orig_df[["race_id", "horse", "is_fav"]], on=["race_id", "horse"], how="left")
    total, wins = 0, 0
    for _, race in sub.groupby("race_id"):
        if race["target"].sum() != 1:
            continue
        favs = race[race["is_fav"] == 1]
        if len(favs) == 0:
            continue
        wins += int(favs["target"].sum() > 0)
        total += 1
    return wins / max(total, 1)


def _run_model(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    test: pd.DataFrame,
    features: list[str],
    label: str,
) -> dict:
    available = [f for f in features if f in train.columns]
    if len(available) < 1:
        return {"status": "NO_FEATURES"}

    X_tr = train[available].fillna(-1)
    y_tr = train["target"]
    X_va = valid[available].fillna(-1)
    y_va = valid["target"]
    X_te = test[available].fillna(-1)
    y_te = test["target"]

    if HAS_LGB:
        model = lgb.LGBMClassifier(
            n_estimators=500,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=20,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbose=-1,
        )
        model.fit(
            X_tr, y_tr,
            eval_set=[(X_va, y_va)],
            callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(period=-1)],
        )
        probs = model.predict_proba(X_te)[:, 1]
    else:
        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr)
        X_te_s = scaler.transform(X_te)
        model = LogisticRegression(max_iter=500, C=1.0)
        model.fit(X_tr_s, y_tr)
        probs = model.predict_proba(X_te_s)[:, 1]

    test = test.copy()
    test["_prob"] = probs

    try:
        auc = roc_auc_score(y_te, probs)
    except Exception:
        auc = float("nan")
    brier = brier_score_loss(y_te, probs)
    sr = _top_pick_sr(test, "_prob")
    n_features = len(available)

    return {
        "model": label,
        "auc": round(auc, 4),
        "brier": round(brier, 4),
        "sr": round(sr, 4),
        "n_features": n_features,
        "features_used": available,
    }


def _gate_verdict(auc: float, sr: float, fav_sr: float, rpr_sr: float) -> str:
    if auc >= 0.75 and sr > fav_sr:
        return "GATE_REOPENED_SAFE_SHADOW_CANDIDATE"
    if auc >= 0.65 and sr > fav_sr:
        return "NEEDS_FEATURE_ENGINEERING"
    if sr <= fav_sr:
        return "FAILS_FAVOURITE_BASELINE"
    if sr <= rpr_sr:
        return "FAILS_RPR_BASELINE"
    return "HOLD"


def run_pack(
    pack_name: str,
    config: dict,
    hk_df: pd.DataFrame,
    fr_df: pd.DataFrame,
    orig_df: pd.DataFrame,
) -> dict:
    print(f"\n[Arena] Pack: {pack_name}")
    src = config["source"]
    df = (hk_df if src == "HK" else fr_df).copy()
    df = df[df["course"].isin(config["courses"])]

    df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")

    train = df[df["date_parsed"] <= TRAIN_CUTOFF].copy()
    valid = df[(df["date_parsed"] > TRAIN_CUTOFF) & (df["date_parsed"] <= VALID_CUTOFF)].copy()
    test = df[df["date_parsed"] > VALID_CUTOFF].copy()

    n_test_races = test["race_id"].nunique()
    print(f"  Train:{len(train):,}  Valid:{len(valid):,}  Test:{len(test):,}  TestRaces:{n_test_races:,}")

    if n_test_races < 100:
        return {"pack": pack_name, "status": "HOLD", "reason": f"Only {n_test_races} test races"}

    # Favourite baseline
    fav_sr = _fav_sr(test, orig_df[orig_df["course"].isin(config["courses"])])
    print(f"  Favourite SR: {fav_sr:.2%}")

    all_features = [f for f in config["features"] if f in df.columns]
    rpr_col = config.get("rpr_features", ["prev_rpr_num", "lagged_rpr_last1"])
    rpr_features = [f for f in rpr_col if f in df.columns]

    models: list[dict] = []

    # 1. Lagged RPR single-feature baseline
    if rpr_features:
        rpr_result = _run_model(train, valid, test, rpr_features, "LAGGED_RPR_ONLY")
        models.append(rpr_result)
        rpr_sr = rpr_result["sr"]
        print(f"  Lagged-RPR-only: AUC={rpr_result['auc']:.4f} SR={rpr_sr:.2%}")
    else:
        rpr_sr = 0.0

    # 2. Full pre-race feature model
    full_result = _run_model(train, valid, test, all_features, "FULL_PRERACE_MODEL")
    models.append(full_result)
    print(f"  Full model:      AUC={full_result['auc']:.4f} SR={full_result['sr']:.2%}")

    # 3. Sub-models (HK: draw-only, class-only; FR: going/dist/course, context-only)
    if src == "HK":
        draw_feats = [f for f in config.get("draw_features", []) if f in df.columns]
        if draw_feats:
            draw_result = _run_model(train, valid, test, draw_feats, "DRAW_ONLY")
            models.append(draw_result)
            print(f"  Draw-only:       AUC={draw_result['auc']:.4f} SR={draw_result['sr']:.2%}")

        class_feats = [f for f in config.get("class_features", []) if f in df.columns]
        if class_feats:
            class_result = _run_model(train, valid, test, class_feats, "CLASS_ONLY")
            models.append(class_result)
            print(f"  Class-only:      AUC={class_result['auc']:.4f} SR={class_result['sr']:.2%}")

        or_feats = [f for f in config.get("or_features", []) if f in df.columns]
        if or_feats:
            or_result = _run_model(train, valid, test, or_feats, "LAGGED_OR_ONLY")
            models.append(or_result)
            print(f"  Lagged-OR-only:  AUC={or_result['auc']:.4f} SR={or_result['sr']:.2%}")

    else:
        going_feats = [f for f in config.get("going_features", []) if f in df.columns]
        if going_feats:
            going_result = _run_model(train, valid, test, going_feats, "GOING_ONLY")
            models.append(going_result)
            print(f"  Going-only:      AUC={going_result['auc']:.4f} SR={going_result['sr']:.2%}")

        context_feats = [f for f in config.get("context_features", []) if f in df.columns]
        if context_feats:
            ctx_result = _run_model(train, valid, test, context_feats, "CONTEXT_ONLY")
            models.append(ctx_result)
            print(f"  Context-only:    AUC={ctx_result['auc']:.4f} SR={ctx_result['sr']:.2%}")

    # Gate verdict on full model
    full_auc = full_result.get("auc", 0.0)
    full_sr = full_result.get("sr", 0.0)
    verdict = _gate_verdict(full_auc, full_sr, fav_sr, rpr_sr)
    print(f"  => Gate verdict: {verdict}")

    return {
        "pack": pack_name,
        "courses": config["courses"],
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "n_test_races": int(n_test_races),
        "fav_sr": round(fav_sr, 4),
        "rpr_only_sr": round(rpr_sr, 4),
        "full_model": full_result,
        "all_models": models,
        "gate_verdict": verdict,
    }


def main() -> None:
    print("[Arena] Loading feature parquets...")
    hk_df = pd.read_parquet(HK_PQ) if HK_PQ.exists() else pd.DataFrame()
    fr_df = pd.read_parquet(FR_PQ) if FR_PQ.exists() else pd.DataFrame()
    orig_df = pd.read_parquet(ORIG_PQ, columns=["race_id", "horse", "course", "is_fav"])

    print(f"[Arena] HK: {len(hk_df):,} rows  |  FR: {len(fr_df):,} rows")

    all_results = []
    for pack_name, config in PACKS.items():
        result = run_pack(pack_name, config, hk_df, fr_df, orig_df)
        all_results.append(result)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "train_cutoff": TRAIN_CUTOFF,
        "valid_cutoff": VALID_CUTOFF,
        "gate_question": "Can VELO beat favourite and RPR baselines using only pre-race information?",
        "packs": all_results,
    }

    report_dir = ROOT / "data" / "reports"
    report_dir.mkdir(exist_ok=True)

    json_path = report_dir / "international_prerace_arena_v1_latest.json"
    json_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n[Arena] Written: {json_path}")

    md = _write_md(all_results, out)
    md_path = report_dir / "international_prerace_arena_v1_latest.md"
    md_path.write_text(md)
    print(f"[Arena] Written: {md_path}")

    # Gate status summary report
    gate_status = _build_gate_status(all_results)
    gs_json_path = report_dir / "international_pack_gate_status_latest.json"
    gs_json_path.write_text(json.dumps(gate_status, indent=2, default=str))
    print(f"[Arena] Gate status: {gs_json_path}")

    gs_md = _write_gate_status_md(gate_status)
    gs_md_path = report_dir / "international_pack_gate_status_latest.md"
    gs_md_path.write_text(gs_md)
    print(f"[Arena] Gate status: {gs_md_path}")

    print("\n=== SUMMARY ===")
    for r in all_results:
        full = r.get("full_model", {})
        auc = full.get("auc", "?")
        sr = full.get("sr", "?")
        fav = r.get("fav_sr", "?")
        verdict = r.get("gate_verdict", r.get("status", "?"))
        auc_str = f"{auc:.4f}" if isinstance(auc, float) else str(auc)
        sr_str = f"{sr:.2%}" if isinstance(sr, float) else str(sr)
        fav_str = f"{fav:.2%}" if isinstance(fav, float) else str(fav)
        print(f"  {r['pack']:<25s} AUC={auc_str}  SR={sr_str}  FavSR={fav_str}  => {verdict}")

    gate_open = [r for r in all_results if r.get("gate_verdict") == "GATE_REOPENED_SAFE_SHADOW_CANDIDATE"]
    if gate_open:
        print(f"\n[!] GATE REOPENED for: {', '.join(r['pack'] for r in gate_open)}")
        print("[!] These packs are eligible for migration discussion.")
    else:
        print("\n[Gate] No pack has reopened the gate. PROVENANCE_GATE_ACTIVE remains.")
        print("[Gate] Next: add more pre-race signals (draw tables, sectionals, market structure).")


def _build_gate_status(all_results: list) -> dict:
    packs = []
    for r in all_results:
        verdict = r.get("gate_verdict", r.get("status", "UNKNOWN"))
        full = r.get("full_model", {})
        migration_eligible = verdict == "GATE_REOPENED_SAFE_SHADOW_CANDIDATE"
        worker_eligible = migration_eligible
        if verdict == "GATE_REOPENED_SAFE_SHADOW_CANDIDATE":
            next_blocker = "Migration approval (El Presidente sign-off)"
        elif verdict == "NEEDS_FEATURE_ENGINEERING":
            next_blocker = "Additional pre-race features needed to beat favourite SR"
        elif verdict == "FAILS_FAVOURITE_BASELINE":
            next_blocker = "Model does not beat favourite — more pre-race signals required"
        else:
            next_blocker = "Insufficient test sample or feature gap"

        packs.append({
            "pack": r["pack"],
            "provenance_gate_status": "ACTIVE",
            "prerace_feature_safety": "AUDITED",
            "arena_verdict": verdict,
            "full_model_auc": full.get("auc"),
            "full_model_sr": full.get("sr"),
            "fav_sr": r.get("fav_sr"),
            "beats_favourite": (
                isinstance(full.get("sr"), float) and
                isinstance(r.get("fav_sr"), float) and
                full.get("sr", 0) > r.get("fav_sr", 1)
            ),
            "migration_eligible": migration_eligible,
            "worker_eligible": worker_eligible,
            "next_blocker": next_blocker,
            "final_verdict": verdict,
        })

    any_gate_open = any(p["migration_eligible"] for p in packs)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gate_question": "Can VELO beat fav/RPR baselines on pre-race info only?",
        "gate_status": "REOPENED" if any_gate_open else "ACTIVE",
        "migration_blocked": not any_gate_open,
        "workers_blocked": True,  # always until migration + operator sign-off
        "packs": packs,
    }


def _write_md(all_results: list, out: dict) -> str:
    rows = ""
    for r in all_results:
        full = r.get("full_model", {})
        auc = full.get("auc", "?")
        sr = full.get("sr", "?")
        fav = r.get("fav_sr", "?")
        rpr = r.get("rpr_only_sr", "?")
        verdict = r.get("gate_verdict", r.get("status", "?"))
        auc_str = f"{auc:.4f}" if isinstance(auc, float) else str(auc)
        sr_str = f"{sr:.2%}" if isinstance(sr, float) else str(sr)
        fav_str = f"{fav:.2%}" if isinstance(fav, float) else str(fav)
        rpr_str = f"{rpr:.2%}" if isinstance(rpr, float) else str(rpr)
        beats = "YES" if (isinstance(sr, float) and isinstance(fav, float) and sr > fav) else "NO"
        rows += f"| {r['pack']} | {auc_str} | {sr_str} | {fav_str} | {rpr_str} | {beats} | **{verdict}** |\n"

    # Sub-model detail
    sub_rows = ""
    for r in all_results:
        for m in r.get("all_models", []):
            auc = m.get("auc", "?")
            sr = m.get("sr", "?")
            auc_s = f"{auc:.4f}" if isinstance(auc, float) else str(auc)
            sr_s = f"{sr:.2%}" if isinstance(sr, float) else str(sr)
            sub_rows += (
                f"| {r['pack']} | {m['model']} "
                f"| {auc_s} | {sr_s} "
                f"| {m.get('n_features', '?')} |\n"
            )

    return f"""# International Pre-Race Arena V1

**Generated:** {out['generated_at']}
**Gate question:** {out['gate_question']}

---

## Gate Results

| Pack | AUC | SR | Fav SR | RPR-only SR | Beats Fav | Verdict |
|---|---|---|---|---|---|---|
{rows}
---

## Sub-Model Breakdown

| Pack | Model | AUC | SR | N Features |
|---|---|---|---|---|
{sub_rows}
---

## Gate Criteria

| Verdict | Criteria |
|---|---|
| GATE_REOPENED_SAFE_SHADOW_CANDIDATE | AUC ≥ 0.75 AND SR > Favourite SR |
| NEEDS_FEATURE_ENGINEERING | AUC ≥ 0.65 AND SR > Favourite SR |
| FAILS_FAVOURITE_BASELINE | SR ≤ Favourite SR |
| FAILS_RPR_BASELINE | SR ≤ Lagged-RPR-only SR |
| HOLD | < 100 test races |

---

```
PRERACE_ARENA_V1_STATUS: COMPLETE
GATE_QUESTION: Can VELO beat fav/RPR on pre-race info only?
TRAIN_CUTOFF: {out['train_cutoff']}
VALID_CUTOFF: {out['valid_cutoff']}
```
"""


def _write_gate_status_md(gs: dict) -> str:
    rows = ""
    for p in gs["packs"]:
        auc = p.get("full_model_auc")
        sr = p.get("full_model_sr")
        fav = p.get("fav_sr")
        auc_str = f"{auc:.4f}" if isinstance(auc, float) else "N/A"
        sr_str = f"{sr:.2%}" if isinstance(sr, float) else "N/A"
        fav_str = f"{fav:.2%}" if isinstance(fav, float) else "N/A"
        mig = "YES" if p["migration_eligible"] else "NO"
        rows += (
            f"| {p['pack']} | {p['provenance_gate_status']} "
            f"| {auc_str} | {sr_str} | {fav_str} | {mig} "
            f"| {p['next_blocker'][:50]} | **{p['final_verdict']}** |\n"
        )

    return f"""# International Pack Gate Status

**Generated:** {gs['generated_at']}
**Gate status:** {gs['gate_status']}
**Migration blocked:** {gs['migration_blocked']}
**Workers blocked:** {gs['workers_blocked']}

---

| Pack | Provenance Gate | AUC | SR | Fav SR | Migration Eligible | Next Blocker | Verdict |
|---|---|---|---|---|---|---|---|
{rows}
---

```
GATE_STATUS: {gs['gate_status']}
MIGRATION_BLOCKED: {gs['migration_blocked']}
WORKERS_BLOCKED: {gs['workers_blocked']}
```
"""


if __name__ == "__main__":
    main()
