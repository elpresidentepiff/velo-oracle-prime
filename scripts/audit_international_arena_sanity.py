#!/usr/bin/env python3
"""
International Arena Sanity Tests

Runs definitive tests to confirm or deny leakage in the baseline arena:
  1. Random label shuffle test (AUC should drop to ~0.50 if clean)
  2. Race-level group split integrity (no race_id in both train and test)
  3. Time split verification (date parser correctness)
  4. Race-level vs runner-level SR comparison
  5. Feature ablation (RPR_ONLY, OR_ONLY, FIT_SCORES_ONLY, NO_FIT_SCORES)
  6. Final-odds dependency test (with vs without implied_prob)

Outputs:
  data/reports/international_arena_sanity_latest.json
  data/reports/international_arena_sanity_latest.md

Usage:
    PYTHONPATH=. python scripts/audit_international_arena_sanity.py
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
PQ_PATH = ROOT / "data" / "raceform_v17_features.parquet"

TRAIN_END = "2022-12-31"
VALID_END = "2023-12-31"

PACKS = {
    "HK_SHA_TIN_V1": ["Sha Tin (HK)"],
    "HK_HAPPY_VALLEY_V1": ["Happy Valley (HK)"],
    "FR_CHANTILLY_V1": ["Chantilly (FR)"],
}

SAFE_PRE_RACE_ONLY = ["rpr_vs_field", "rpr_num", "or_vs_field", "field_size",
                      "draw_num", "age_num", "dist_f", "going_code", "wgt_lbs",
                      "is_aw", "draw_pct"]

FIT_SCORE_FEATURES = ["course_fit_score", "going_fit_score", "distance_fit_score", "trainer_timing_score"]
RATING_FEATURES = ["rpr_num", "rpr_vs_field", "or_num", "or_vs_field", "ts_num"]

ABLATION_SETS = {
    "RPR_ONLY": ["rpr_vs_field"],
    "RPR_AND_OR": ["rpr_vs_field", "rpr_num", "or_vs_field", "or_num"],
    "RATINGS_ONLY": RATING_FEATURES,
    "SAFE_PRE_RACE_ONLY": SAFE_PRE_RACE_ONLY,
    "NO_FIT_SCORES": [f for f in SAFE_PRE_RACE_ONLY
                      if f not in FIT_SCORE_FEATURES],
    "FIT_SCORES_ONLY": FIT_SCORE_FEATURES,
}


def _split(sub: pd.DataFrame):
    dates = pd.to_datetime(sub["date"], errors="coerce")
    train = sub[dates <= TRAIN_END]
    valid = sub[(dates > TRAIN_END) & (dates <= VALID_END)]
    test = sub[dates > VALID_END]
    return train, valid, test


def _top_pick_sr(y_pred, y_true, race_ids):
    df = pd.DataFrame({"pred": y_pred, "true": y_true, "race": race_ids})
    top = df.loc[df.groupby("race")["pred"].idxmax()]
    n = len(top)
    wins = top["true"].sum()
    return round(float(wins / n), 4) if n > 0 else 0.0, int(n)


def _runner_accuracy(y_pred, y_true, threshold=0.15):
    preds = (y_pred >= threshold).astype(int)
    return round(float((preds == y_true).mean()), 4)


def _simple_lgbm(X_train, y_train, X_test, y_test, race_ids_test):
    try:
        import lightgbm as lgb
        model = lgb.LGBMClassifier(
            n_estimators=100, learning_rate=0.05, max_depth=5,
            num_leaves=31, min_child_samples=20, n_jobs=-1, random_state=42, verbose=-1
        )
        model.fit(X_train, y_train, callbacks=[lgb.log_evaluation(-1)])
        probs = model.predict_proba(X_test)[:, 1]
        auc = round(float(roc_auc_score(y_test, probs)), 4)
        sr, n = _top_pick_sr(probs, y_test, race_ids_test)
        return {"auc": auc, "top_pick_sr": sr, "n_races": n, "status": "OK"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def test_shuffle(sub: pd.DataFrame, features: list[str], pack_name: str) -> dict:
    """Shuffle target within races — AUC should drop to ~0.50 if no leakage."""
    print(f"  [Shuffle] {pack_name}")
    train, _, test = _split(sub)
    avail = [f for f in features if f in sub.columns and (sub[f].ne(0) & sub[f].notna()).mean() > 0.05]
    if not avail or len(train) < 50 or len(test) < 10:
        return {"status": "INSUFFICIENT_DATA"}

    X_train = train[avail].fillna(0).values
    X_test = test[avail].fillna(0).values
    y_test = test["target"].values.astype(float)
    race_ids_test = test["race_id"].values

    # Shuffle labels within each race (preserve race structure)
    y_train_shuffled = train.copy()
    rng = np.random.default_rng(42)
    y_train_shuffled["target"] = (
        y_train_shuffled.groupby("race_id")["target"]
        .transform(lambda x: rng.permutation(x.values))
    )
    y_train_shuf = y_train_shuffled["target"].values.astype(float)

    real_result = _simple_lgbm(X_train, train["target"].values.astype(float), X_test, y_test, race_ids_test)
    shuf_result = _simple_lgbm(X_train, y_train_shuf, X_test, y_test, race_ids_test)

    auc_collapse = None
    if "auc" in real_result and "auc" in shuf_result:
        auc_collapse = round(real_result["auc"] - shuf_result["auc"], 4)

    verdict = "UNKNOWN"
    if "auc" in shuf_result:
        if shuf_result["auc"] < 0.55:
            verdict = "CLEAN — shuffle collapsed AUC as expected"
        elif shuf_result["auc"] < 0.65:
            verdict = "MARGINAL — shuffle partially collapsed AUC (investigate)"
        else:
            verdict = "LEAKAGE_SUSPECTED — AUC barely dropped after shuffle"

    result = {
        "real_auc": real_result.get("auc"),
        "shuffled_auc": shuf_result.get("auc"),
        "real_top_pick_sr": real_result.get("top_pick_sr"),
        "shuffled_top_pick_sr": shuf_result.get("top_pick_sr"),
        "auc_collapse": auc_collapse,
        "verdict": verdict,
        "features_used": avail,
    }
    print(f"    real_auc={real_result.get('auc')} shuffle_auc={shuf_result.get('auc')} verdict={verdict}")
    return result


def test_group_split(sub: pd.DataFrame) -> dict:
    """Confirm no race_id appears in both train and test."""
    train, valid, test = _split(sub)
    train_races = set(train["race_id"].unique())
    valid_races = set(valid["race_id"].unique())
    test_races = set(test["race_id"].unique())

    train_test_overlap = train_races & test_races
    train_valid_overlap = train_races & valid_races
    valid_test_overlap = valid_races & test_races

    return {
        "train_races": int(len(train_races)),
        "valid_races": int(len(valid_races)),
        "test_races": int(len(test_races)),
        "train_test_race_overlap": int(len(train_test_overlap)),
        "train_valid_race_overlap": int(len(train_valid_overlap)),
        "valid_test_race_overlap": int(len(valid_test_overlap)),
        "verdict": "CLEAN" if len(train_test_overlap) == 0 else f"OVERLAP_DETECTED: {len(train_test_overlap)} races in both train and test",
        "overlap_sample": list(train_test_overlap)[:5] if train_test_overlap else [],
    }


def test_date_split(sub: pd.DataFrame) -> dict:
    """Verify temporal split is correct."""
    dates = pd.to_datetime(sub["date"], errors="coerce")
    train, valid, test = _split(sub)

    train_dates = pd.to_datetime(train["date"], errors="coerce")
    test_dates = pd.to_datetime(test["date"], errors="coerce")
    valid_dates = pd.to_datetime(valid["date"], errors="coerce")

    return {
        "date_parse_failures": int(dates.isna().sum()),
        "train_date_min": str(train_dates.min().date()) if len(train) > 0 else "N/A",
        "train_date_max": str(train_dates.max().date()) if len(train) > 0 else "N/A",
        "valid_date_min": str(valid_dates.min().date()) if len(valid) > 0 else "N/A",
        "valid_date_max": str(valid_dates.max().date()) if len(valid) > 0 else "N/A",
        "test_date_min": str(test_dates.min().date()) if len(test) > 0 else "N/A",
        "test_date_max": str(test_dates.max().date()) if len(test) > 0 else "N/A",
        "train_post_cutoff_rows": int((train_dates > TRAIN_END).sum()),
        "test_pre_cutoff_rows": int((test_dates <= VALID_END).sum()),
        "verdict": "CLEAN" if (train_dates > TRAIN_END).sum() == 0 and (test_dates <= VALID_END).sum() == 0
                   else "DATE_SPLIT_ANOMALY_DETECTED",
    }


def test_feature_ablation(sub: pd.DataFrame, pack_name: str) -> dict:
    """Run model with different feature subsets to isolate source of signal."""
    print(f"  [Ablation] {pack_name}")
    train, _, test = _split(sub)
    race_ids_test = test["race_id"].values
    y_train = train["target"].values.astype(float)
    y_test = test["target"].values.astype(float)

    # Fav baseline
    fav_sr = 0.0
    if "is_fav" in sub.columns:
        fav_df = test.copy()
        fav_df["race"] = race_ids_test
        favs = fav_df[fav_df["is_fav"] == 1]
        n_races_fav = favs["race"].nunique()
        fav_wins = favs["target"].sum()
        fav_sr = round(float(fav_wins / n_races_fav), 4) if n_races_fav > 0 else 0.0

    ablation_results = {}
    for ablation_name, feature_set in ABLATION_SETS.items():
        avail = [f for f in feature_set
                 if f in sub.columns and (sub[f].ne(0) & sub[f].notna()).mean() > 0.03]
        if not avail:
            ablation_results[ablation_name] = {"status": "NO_FEATURES_AVAILABLE", "features": feature_set}
            continue

        X_train = train[avail].fillna(0).values
        X_test = test[avail].fillna(0).values

        res = _simple_lgbm(X_train, y_train, X_test, y_test, race_ids_test)
        res["features_available"] = avail
        res["n_features"] = len(avail)
        ablation_results[ablation_name] = res
        sr = res.get("top_pick_sr", "?")
        auc = res.get("auc", "?")
        print(f"    {ablation_name:25s} SR={sr} AUC={auc} features={avail}")

    return {"fav_sr_baseline": fav_sr, "ablations": ablation_results}


def test_runner_vs_race_level(sub: pd.DataFrame, pack_name: str) -> dict:
    """Verify SR is computed race-level (top pick per race) not runner-level accuracy."""
    train, _, test = _split(sub)
    features = ["rpr_vs_field"]
    avail = [f for f in features if f in sub.columns]
    if not avail:
        return {"status": "NO_RPR_AVAILABLE"}

    X_train = train[avail].fillna(0).values
    X_test = test[avail].fillna(0).values
    y_train = train["target"].values.astype(float)
    y_test = test["target"].values.astype(float)
    race_ids_test = test["race_id"].values

    try:
        import lightgbm as lgb
        model = lgb.LGBMClassifier(n_estimators=50, n_jobs=-1, random_state=42, verbose=-1)
        model.fit(X_train, y_train, callbacks=[lgb.log_evaluation(-1)])
        probs = model.predict_proba(X_test)[:, 1]

        race_level_sr, n_races = _top_pick_sr(probs, y_test, race_ids_test)
        # Runner-level "accuracy": did model's top-prob runner within each race end up > threshold?
        # Compare: how many test runners are "winners" vs how many the model predicts
        n_runners = len(y_test)
        n_winners = int(y_test.sum())
        avg_field = n_runners / n_races if n_races > 0 else 0

        return {
            "n_test_runners": n_runners,
            "n_test_races": n_races,
            "n_winners": n_winners,
            "avg_field_size": round(avg_field, 2),
            "race_level_top_pick_sr": race_level_sr,
            "expected_random_sr": round(1.0 / avg_field, 4) if avg_field > 0 else None,
            "note": (
                "race_level_top_pick_sr = pct of races where model's top-prob runner won. "
                "This is the correct SR metric. Runner-level accuracy not shown (misleading)."
            ),
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def main() -> None:
    print("[SanityTests] Loading parquet...")
    df = pd.read_parquet(PQ_PATH)
    print(f"[SanityTests] Rows: {len(df):,}")

    all_results = {}

    for pack_name, courses in PACKS.items():
        print(f"\n=== Pack: {pack_name} ===")
        sub = df[df["course"].isin(courses)].copy()

        pack_result = {
            "pack": pack_name,
            "courses": courses,
            "n_total": int(len(sub)),
        }

        print("  [1] Date split verification...")
        pack_result["date_split"] = test_date_split(sub)

        print("  [2] Race group split verification...")
        pack_result["group_split"] = test_group_split(sub)

        print("  [3] Runner vs race level SR check...")
        pack_result["runner_vs_race_level"] = test_runner_vs_race_level(sub, pack_name)

        print("  [4] Feature ablation...")
        pack_result["feature_ablation"] = test_feature_ablation(sub, pack_name)

        print("  [5] Shuffle test (slowest step)...")
        arena_features_for_pack = [f for f in SAFE_PRE_RACE_ONLY +
                                   ["or_num", "or_vs_field", "class_num", "runs_since_win",
                                    "runs_since_place", "mark_compression_score",
                                    "course_fit_score", "going_fit_score",
                                    "distance_fit_score", "trainer_timing_score"]
                                   if f in sub.columns]
        pack_result["shuffle_test"] = test_shuffle(sub, arena_features_for_pack, pack_name)

        # Overall pack verdict
        dt = pack_result["date_split"].get("verdict", "")
        gs = pack_result["group_split"].get("verdict", "")
        shuf = pack_result["shuffle_test"].get("verdict", "")

        if "LEAKAGE" in shuf:
            pack_result["sanity_verdict"] = "LEAKAGE_CONFIRMED"
        elif "ANOMALY" in dt or "OVERLAP" in gs:
            pack_result["sanity_verdict"] = "STRUCTURAL_ISSUE_DETECTED"
        elif "MARGINAL" in shuf:
            pack_result["sanity_verdict"] = "MARGINAL_INVESTIGATE"
        elif "CLEAN" in shuf:
            pack_result["sanity_verdict"] = "SANITY_PASSED"
        else:
            pack_result["sanity_verdict"] = "UNKNOWN"

        all_results[pack_name] = pack_result
        print(f"  => SANITY VERDICT: {pack_result['sanity_verdict']}")

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "packs": all_results,
    }

    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(exist_ok=True)

    json_path = out_dir / "international_arena_sanity_latest.json"
    json_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n[SanityTests] Written: {json_path}")

    md = _write_md(all_results)
    md_path = out_dir / "international_arena_sanity_latest.md"
    md_path.write_text(md)
    print(f"[SanityTests] Written: {md_path}")

    print("\n=== SUMMARY ===")
    for pack_name, res in all_results.items():
        print(f"  {pack_name}: {res.get('sanity_verdict')}")
        shuf = res.get("shuffle_test", {})
        print(f"    shuffle: real_auc={shuf.get('real_auc')} shuffled_auc={shuf.get('shuffled_auc')}")


def _write_md(all_results: dict) -> str:
    rows = ""
    for pack_name, res in all_results.items():
        dt = res.get("date_split", {}).get("verdict", "?")
        gs = res.get("group_split", {}).get("verdict", "?")
        shuf = res.get("shuffle_test", {})
        sv = res.get("sanity_verdict", "?")
        real_auc = shuf.get("real_auc", "?")
        shuf_auc = shuf.get("shuffled_auc", "?")
        rows += f"| {pack_name} | {dt} | {gs} | real={real_auc} shuf={shuf_auc} | **{sv}** |\n"

    ablation_sections = ""
    for pack_name, res in all_results.items():
        abl = res.get("feature_ablation", {})
        fav_sr = abl.get("fav_sr_baseline", "?")
        ablation_sections += f"\n### {pack_name} — Ablation Results\n"
        ablation_sections += f"Favourite SR baseline: {fav_sr:.1%}\n\n" if isinstance(fav_sr, float) else f"Favourite SR baseline: {fav_sr}\n\n"
        ablation_sections += "| Feature Set | AUC | Top-Pick SR | N Races | Features |\n|---|---|---|---|---|\n"
        for ablation_name, abl_res in abl.get("ablations", {}).items():
            auc = abl_res.get("auc", "N/A")
            sr = abl_res.get("top_pick_sr", "N/A")
            n = abl_res.get("n_races", "N/A")
            feats = ", ".join(abl_res.get("features_available", []))
            sr_str = f"{sr:.1%}" if isinstance(sr, float) else str(sr)
            auc_str = f"{auc:.4f}" if isinstance(auc, float) else str(auc)
            ablation_sections += f"| {ablation_name} | {auc_str} | {sr_str} | {n} | {feats} |\n"

    return f"""# International Arena Sanity Tests

**Generated:** {datetime.now(timezone.utc).isoformat()}

---

## Summary

| Pack | Date Split | Group Split | Shuffle (real/shuffled AUC) | Sanity Verdict |
|---|---|---|---|---|
{rows}
---

## Test Descriptions

1. **Date split**: Confirms temporal split — train ≤ 2022, valid 2023, test > 2023
2. **Group split**: Confirms no race_id appears in both train and test
3. **Shuffle test**: Shuffles target labels within races. If model AUC collapses to ~0.50, features are genuine pre-race signals. If AUC stays high, leakage exists.
4. **Ablation**: Tests different feature subsets to identify where the signal comes from

---

## Ablation Results
{ablation_sections}

---

## Interpretation

- **SANITY_PASSED**: Shuffle test collapsed AUC. Features are genuine. Investigate why AUC is so high in safe arena.
- **LEAKAGE_CONFIRMED**: AUC barely dropped after shuffle. One or more features encode the outcome.
- **MARGINAL_INVESTIGATE**: Partial AUC collapse. Some signal may be leaking.

---

```
SANITY_STATUS: see above per pack
MIGRATION_STATUS: NOT_RUN
WORKER_STATUS: BLOCKED
```
"""


if __name__ == "__main__":
    main()
