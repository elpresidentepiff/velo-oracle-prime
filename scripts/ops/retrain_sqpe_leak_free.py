#!/usr/bin/env python3
"""
VÉLØ — SQPE Leak-Free Retrain
==============================
Trains the SQPE model with every feature that cannot exist at 07:00 removed,
and scores it on the only metric that decides anything: money.

WHY THIS EXISTS
---------------
The production model (models/sqpe_v17) reports AUC 0.9296 and 72.0% top-1
accuracy. Live it hits 28.6%. The gap is not drift — it is leakage, from two
independent sources.

1. THE RESULT ITSELF (49.9% of model weight)

   rpr_vs_field 0.3967 | rpr_num 0.1020 | ts_num 0.0361

   Racing Post Rating and Topspeed are assigned AFTER a race, from how the
   horse actually performed in it. Measured on this parquet, within-race
   Spearman correlation against finishing position:

       rpr_num  -0.937   (|rho| > 0.9 in 61.2% of races)
       ts_num   -0.942   (|rho| > 0.9 in 61.7% of races)
       or_num   -0.130   (|rho| > 0.9 in  1.4% of races)   <- a real pre-race figure

   Backing the top-RPR horse wins 68.2% of races; the top-OR horse wins 17.6%.
   RPR is not a rating the model reads, it is the finishing order re-encoded.
   That single fact accounts for the 72.0% top-1 in test.

2. THE MARKET (27.4% of model weight)

   implied_prob 0.1123 | log_sp 0.0665 | sp_dec 0.0564
   is_fav       0.0209 | sp_rank 0.0179

   The starting price does not exist at 07:00 either, and is largely determined
   by the outcome being predicted. At inference the pipeline substitutes RP's
   `forecast_odds` into the sp_dec slot — a different quantity with a different
   distribution — so even the shortcut degrades into noise.

Removing the market features ALONE moves AUC only 0.9296 -> 0.9274, because
RPR carries the model on its own. Both sources have to go.

Measured consequence over 1,540 live picks (2026-05-21 .. 2026-09-02):
  VÉLØ says P(win)=0.399 | actual 0.286 | market 0.289
  Backing VÉLØ's top pick at SP : ROI -3.89%
  Backing the SP favourite      : ROI +0.96%   (same 1,523 races)

WHAT THIS CHANGES
-----------------
Eleven features are removed. Three encode the result. Five are the price
outright. Three more were tested empirically and smuggle the price in:

    odds_resilience_score    within-race Spearman vs sp_dec +0.50
    odds_contraction_score   within-race Spearman vs sp_dec -0.33
    decoy_support_flag       within-race Spearman vs sp_dec -0.775,
                             |corr| 0.387 with implied_prob, fires on 3.9%

ON retrain_sqpe_no_rpr.py
-------------------------
That script's NO_RPR_FEATURES list already excluded all eleven of these. It was
built to answer "can we score without RPR when RPR is missing?" — but it was
accidentally the only honest model in the repo, and its AUC 0.6942 is the real
number. What was never done is the thing that decides anything: nobody measured
whether it makes money. This script's feature set is therefore near-identical
to that one by design, and its contribution is the economics block below.

Deliberately KEPT:

    or_num, or_vs_field
        Official Rating — set by the BHA handicapper BEFORE the race and
        published on the racecard. Within-race rho vs finishing position -0.130.
        This is what a legitimate rating looks like.

    runs_since_mkt_support
        Counts PAST races in which the market supported this horse. Historical,
        knowable pre-race. Correlates with today's price (0.249) for the honest
        reason that a recently-backed horse tends to be short today.

    setup_run_flag, cash_run_flag
        Doctrine flags over past-run patterns. |corr| with implied_prob 0.185
        and 0.015 respectively.

Expect AUC to fall from 0.9296 to roughly 0.69, and top-1 from 72% to ~26%.
That is not a regression. It is the size of the leak, and ~26% is very close
to the 28.6% the model actually achieves live — which is the point: an honest
backtest should predict live performance, and this one does.

BOUNDARY
--------
Writes to models/sqpe_leak_free_staging/ ONLY. There is no --promote flag:
live model weights are frozen under the hard laws in CLAUDE.md and promotion
is an operator decision made on the economics below, not on AUC.

Usage:
    python scripts/ops/retrain_sqpe_leak_free.py
    python scripts/ops/retrain_sqpe_leak_free.py --sample 200000   # dev
"""

from __future__ import annotations

import argparse
import json
import pickle
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import log_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]

FEATURES_PARQUET = ROOT / "data" / "raceform_v17_features.parquet"
PRODUCTION_META = ROOT / "models" / "sqpe_v17" / "metadata.json"
STAGING_DIR = ROOT / "models" / "sqpe_leak_free_staging"

# Every feature that carries today's price, directly or by proxy. Training on
# any of these reintroduces the leak this whole script exists to remove, so the
# list is enforced as an assertion below rather than left as documentation.
BANNED_LEAK_FEATURES = frozenset({
    # Post-race performance figures — the finishing order, re-encoded
    "rpr_num", "rpr_vs_field", "ts_num",
    # The market price, which does not exist at 07:00
    "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav",
    # Price-derived proxies
    "odds_resilience_score", "odds_contraction_score", "decoy_support_flag",
})

LEAK_FREE_FEATURES = [
    # Race conditions — known when the card is published
    "dist_f", "going_code", "is_aw", "class_num", "wgt_lbs",
    # Official Rating only — set pre-race by the handicapper
    "or_num", "or_vs_field",
    # Field shape
    "field_size", "draw_num", "draw_pct", "age_num",
    # Doctrine — release / plot
    "runs_since_win", "runs_since_place", "runs_since_mkt_support",
    "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "mark_compression_score", "release_window_score",
    # Doctrine — fit
    "course_fit_score", "going_fit_score", "distance_fit_score",
    # Doctrine — intent
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    # Doctrine — execution
    "setup_run_flag", "cash_run_flag",
]

assert not (BANNED_LEAK_FEATURES & set(LEAK_FREE_FEATURES)), \
    "a leaking feature found its way back into LEAK_FREE_FEATURES"


def _race_metrics(df: pd.DataFrame, prob_col: str, target_col: str = "target"):
    """Top-1 accuracy and MRR across races — same definition as retrain_sqpe_v17."""
    top1_hits = 0
    mrr_sum = 0.0
    races = 0
    for _, grp in df.groupby("race_id"):
        if len(grp) < 2:
            continue
        races += 1
        ranked = grp.sort_values(prob_col, ascending=False).reset_index(drop=True)
        if not (ranked[target_col] == 1).any():
            continue
        rank = ranked.index[ranked[target_col] == 1][0] + 1
        if rank == 1:
            top1_hits += 1
        mrr_sum += 1.0 / rank
    return (round(top1_hits / races, 4) if races else 0.0,
            round(mrr_sum / races, 4) if races else 0.0,
            races)


def _betting_economics(df: pd.DataFrame, prob_col: str) -> dict:
    """Back the model's rank-1 pick in every test race at SP, 1pt level stakes.

    This is the metric the audit found missing. AUC and top-1 rank horses;
    neither tells you whether the ranking survives the price you have to pay
    for it. Using SP here is legitimate — it is the settlement price, applied
    after the model has committed, never shown to it as a feature.

    The SP favourite over the identical races is carried alongside as the
    benchmark that actually matters: on live data it returned +0.96% while
    VÉLØ returned -3.89%, so a model that cannot beat it is not yet worth
    running.
    """
    model_n = model_w = 0
    model_pl = 0.0
    fav_n = fav_w = 0
    fav_pl = 0.0
    agree = 0
    sp_sum = 0.0

    for _, grp in df.groupby("race_id"):
        g = grp[(grp["sp_dec"] > 1.0) & grp["sp_dec"].notna()]
        if len(g) < 2:
            continue

        pick = g.loc[g[prob_col].idxmax()]
        won = bool(pick["target"] == 1)
        model_n += 1
        model_w += won
        model_pl += (pick["sp_dec"] - 1) if won else -1
        sp_sum += float(pick["sp_dec"])

        fav = g.loc[g["sp_dec"].idxmin()]
        fwon = bool(fav["target"] == 1)
        fav_n += 1
        fav_w += fwon
        fav_pl += (fav["sp_dec"] - 1) if fwon else -1

        agree += int(pick.name == fav.name)

    if not model_n:
        return {"races": 0}
    return {
        "races": model_n,
        "model_wins": model_w,
        "model_strike_rate": round(model_w / model_n, 4),
        "model_avg_pick_sp": round(sp_sum / model_n, 3),
        "model_pl_points": round(model_pl, 2),
        "model_roi": round(model_pl / model_n, 4),
        "favourite_wins": fav_w,
        "favourite_strike_rate": round(fav_w / fav_n, 4),
        "favourite_pl_points": round(fav_pl, 2),
        "favourite_roi": round(fav_pl / fav_n, 4),
        "roi_vs_favourite": round(model_pl / model_n - fav_pl / fav_n, 4),
        "agreed_with_favourite": round(agree / model_n, 4),
        "stake_rule": "1pt level stakes to win at SP, no commission, no each-way",
    }


def _bootstrap_roi_ci(picks: list[tuple[float, bool]], iters: int = 5000, seed: int = 11):
    """95% CI on ROI by resampling picks — a point estimate alone hides the variance."""
    if not picks:
        return None, None
    rng = np.random.default_rng(seed)
    arr = np.array([(sp - 1) if won else -1.0 for sp, won in picks])
    idx = rng.integers(0, len(arr), size=(iters, len(arr)))
    means = arr[idx].mean(axis=1)
    return round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--features", default=str(FEATURES_PARQUET))
    ap.add_argument("--output", default=str(STAGING_DIR))
    ap.add_argument("--sample", type=int, default=None,
                    help="Approximate row cap for a quick development run. Sampling is "
                         "done by RACE, never by row — a fragmented race would leave the "
                         "model picking from 2 of 12 runners and make the economics "
                         "block below meaningless.")
    ap.add_argument("--train-cutoff", type=int, default=2025,
                    help="Exclusive year cutoff (default 2025 = train <=2024, test 2025+).")
    args = ap.parse_args()

    print("=" * 68)
    print("VÉLØ — SQPE Leak-Free Retrain")
    print(f"  Source : {args.features}")
    print(f"  Output : {args.output}   (staging only — no promotion path)")
    print(f"  Split  : train < {args.train_cutoff}, test >= {args.train_cutoff}")
    print(f"  Removed: {len(BANNED_LEAK_FEATURES)} leaking features (post-race + market)")
    print("=" * 68)

    df = pd.read_parquet(args.features)
    print(f"\nLoaded {len(df):,} rows")

    if not pd.api.types.is_datetime64_any_dtype(df["date_parsed"]):
        df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")

    numeric_pos = pd.to_numeric(df["pos"].astype(str).str.strip(), errors="coerce")
    df = df[numeric_pos.notna()].copy()
    print(f"  {len(df):,} rows after removing non-starters")

    if args.sample:
        # Sample whole races. Row-level sampling would break races apart, and the
        # economics block picks one runner per race — from a shredded race it would
        # pick the best of an arbitrary 2 of 12 and report a fantasy ROI.
        avg_runners = max(len(df) / df["race_id"].nunique(), 1.0)
        n_races = max(int(args.sample / avg_runners), 50)
        keep = (df["race_id"].drop_duplicates()
                  .sample(n=min(n_races, df["race_id"].nunique()), random_state=42))
        df = df[df["race_id"].isin(keep)].copy()
        print(f"  Sampled to {len(df):,} rows across {df['race_id'].nunique():,} whole "
              f"races (development run — not for promotion)")

    missing = [f for f in LEAK_FREE_FEATURES if f not in df.columns]
    if missing:
        print(f"\nERROR: missing features in parquet: {missing}")
        return 1

    df = df.sort_values("date_parsed").reset_index(drop=True)
    train_df = df[df["date_parsed"].dt.year < args.train_cutoff]
    test_df = df[df["date_parsed"].dt.year >= args.train_cutoff].copy()

    print(f"\nTrain {len(train_df):,} rows  ({train_df['date_parsed'].dt.year.min()}"
          f"–{train_df['date_parsed'].dt.year.max()})")
    print(f"Test  {len(test_df):,} rows  ({test_df['date_parsed'].dt.year.min()}"
          f"–{test_df['date_parsed'].dt.year.max()})")

    X_tr = train_df[LEAK_FREE_FEATURES].fillna(0)
    X_te = test_df[LEAK_FREE_FEATURES].fillna(0)
    y_tr, y_te = train_df["target"], test_df["target"]
    print(f"\nWin rate  train {y_tr.mean():.4f}   test {y_te.mean():.4f}")
    print(f"Features  {len(LEAK_FREE_FEATURES)} (production uses 37)")

    print("\nTraining GBM + isotonic calibration — identical hyperparameters to\n"
          "retrain_sqpe_v17.py, so the only variable is the feature set ...")
    model = CalibratedClassifierCV(
        GradientBoostingClassifier(
            n_estimators=500, learning_rate=0.04, max_depth=5,
            min_samples_leaf=50, subsample=0.8, max_features="sqrt",
            random_state=42, verbose=1,
        ),
        method="isotonic", cv=3,
    )
    model.fit(X_tr, y_tr)

    probs = model.predict_proba(X_te)[:, 1]
    auc = roc_auc_score(y_te, probs)
    ll = log_loss(y_te, probs)
    test_df["pred"] = probs
    top1, mrr, n_races = _race_metrics(test_df, "pred")

    print(f"\n{'=' * 68}\nRANKING QUALITY")
    print(f"  AUC-ROC    : {auc:.4f}")
    print(f"  Log loss   : {ll:.4f}")
    print(f"  Top-1 acc  : {top1 * 100:.1f}%")
    print(f"  MRR        : {mrr:.4f}")
    print(f"  Races      : {n_races:,}")

    econ = _betting_economics(test_df, "pred")
    print(f"\n{'=' * 68}\nECONOMICS — the metric that decides promotion")
    if econ.get("races"):
        print(f"  Races priced        : {econ['races']:,}")
        print(f"  Model strike rate   : {econ['model_strike_rate']:.2%}"
              f"   (avg pick SP {econ['model_avg_pick_sp']})")
        print(f"  Model P/L           : {econ['model_pl_points']:+.1f} pts")
        print(f"  Model ROI           : {econ['model_roi']:+.2%}")
        print(f"  SP favourite ROI    : {econ['favourite_roi']:+.2%}"
              f"   (strike {econ['favourite_strike_rate']:.2%})")
        print(f"  Model vs favourite  : {econ['roi_vs_favourite']:+.2%}")
        print(f"  Agreed with fav     : {econ['agreed_with_favourite']:.1%} of races")

        picks = []
        for _, grp in test_df.groupby("race_id"):
            g = grp[(grp["sp_dec"] > 1.0) & grp["sp_dec"].notna()]
            if len(g) < 2:
                continue
            p = g.loc[g["pred"].idxmax()]
            picks.append((float(p["sp_dec"]), bool(p["target"] == 1)))
        lo, hi = _bootstrap_roi_ci(picks)
        econ["model_roi_ci95"] = [lo, hi]
        print(f"  ROI 95% CI          : [{lo:+.2%}, {hi:+.2%}]")

    base = model.calibrated_classifiers_[0].estimator
    importance = sorted(zip(LEAK_FREE_FEATURES, base.feature_importances_),
                        key=lambda x: -x[1])
    print(f"\n{'=' * 68}\nTOP 15 FEATURES (no leaking feature can appear here)")
    for feat, val in importance[:15]:
        print(f"  {feat:<32} {val:.4f}")

    if PRODUCTION_META.exists():
        pm = json.loads(PRODUCTION_META.read_text())
        print(f"\n{'=' * 68}\nAGAINST THE LEAKING PRODUCTION MODEL")
        print(f"  {'':<14}{'production':>14}{'leak-free':>14}")
        print(f"  {'AUC':<14}{pm.get('auc', 0):>14.4f}{auc:>14.4f}")
        print(f"  {'Top-1':<14}{pm.get('top1_accuracy', 0):>14.4f}{top1:>14.4f}")
        print(f"  {'Features':<14}{pm.get('n_features', 0):>14}{len(LEAK_FREE_FEATURES):>14}")
        print("\n  A large AUC drop here is the expected and correct result:")
        print("  it is the size of the leak, now removed.")

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "sqpe_leak_free.pkl", "wb") as fh:
        pickle.dump(model, fh)

    metadata = {
        "version": "leak_free_v1",
        "model_type": "GradientBoostingClassifier + IsotonicCalibration",
        "trained_at": datetime.now(UTC).isoformat(),
        "source": str(args.features),
        "development_run": bool(args.sample),
        "train_cutoff_year": args.train_cutoff,
        "n_features": len(LEAK_FREE_FEATURES),
        "feature_names": LEAK_FREE_FEATURES,
        "removed_leaking_features": sorted(BANNED_LEAK_FEATURES),
        "removal_rationale": {
            "rpr_num": "post-race Racing Post Rating; within-race rho vs finish -0.937",
            "rpr_vs_field": "derived from rpr_num",
            "ts_num": "post-race Topspeed figure; within-race rho vs finish -0.942",
            "sp_dec": "starting price — not available at 07:00 scoring time",
            "log_sp": "starting price, transformed",
            "implied_prob": "1/SP — the market's own answer",
            "sp_rank": "rank by starting price",
            "is_fav": "was the SP favourite",
            "odds_resilience_score": "SP-drift derived; within-race Spearman vs sp_dec +0.50",
            "odds_contraction_score": "SP-drift derived; within-race Spearman vs sp_dec -0.33",
            "decoy_support_flag": "within-race Spearman vs sp_dec -0.775; |corr| 0.387 with implied_prob",
        },
        "kept_deliberately": {
            "or_num/or_vs_field":
                "Official Rating — set pre-race by the BHA handicapper and printed "
                "on the racecard; within-race rho vs finishing position -0.130",
            "runs_since_mkt_support": "counts past races, knowable pre-race",
            "setup_run_flag/cash_run_flag": "doctrine flags over past-run patterns",
        },
        "train_rows": int(len(X_tr)),
        "test_rows": int(len(X_te)),
        "test_races": n_races,
        "auc": round(float(auc), 4),
        "log_loss": round(float(ll), 4),
        "top1_accuracy": round(float(top1), 4),
        "mrr": round(float(mrr), 4),
        "train_win_rate": round(float(y_tr.mean()), 4),
        "test_win_rate": round(float(y_te.mean()), 4),
        "economics": econ,
        "top_15_features": [{"feature": f, "importance": round(float(v), 4)}
                            for f, v in importance[:15]],
        "promotion": "BLOCKED — staging only. Live weights are frozen; promotion "
                     "is an operator decision on economics, not on AUC.",
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    pd.DataFrame(importance, columns=["feature", "importance"]).to_csv(
        out_dir / "feature_importance.csv", index=False)

    print(f"\n{'=' * 68}")
    print(f"Staged model : {out_dir / 'sqpe_leak_free.pkl'}")
    print(f"Metadata     : {out_dir / 'metadata.json'}")
    print("NOT promoted. Live weights unchanged.")
    print(f"{'=' * 68}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
