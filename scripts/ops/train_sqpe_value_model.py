#!/usr/bin/env python3
"""
VÉLØ — Value model: predict where the price is wrong, not which horse wins
===========================================================================

WHY THIS EXISTS
---------------
Everything measured in this repo says the win-probability race is unwinnable.
Over 1,540 live picks the market's implied probability averaged 0.289 against
an actual 0.286 — calibrated to three thousandths. VÉLØ's own probability
averaged 0.399, and the harder it leaned the worse it did: picks where VP
exceeded the market returned -9.9%, picks where it did not returned +12.2%.
The leak-free retrain removed every feature that could not exist at 07:00 and
produced an honest model that still returns -10.57% and still loses to backing
the favourite. The no-RPR shadow, measured over 1,100 live races, returns
-16.40%. Model consensus lifts strike rate from 22.4% to 37.6% and moves ROI
not at all, because agreement concentrates on 3.07-average-SP favourites.

Every one of those results says the same thing: this system keeps rediscovering
information the market has already priced. So stop predicting the winner.

WHAT THIS TRAINS
----------------
Target is profit and loss, not a win flag:

    y = (sp_dec - 1) if the horse won, else -1.0

The starting price appears ONLY in the label. It is never a feature, so the
model never sees a price at inference and the leak audit still holds: the
26 inputs are the same leak-free set as retrain_sqpe_leak_free.py, imported
from it rather than restated so the two can never drift apart.

That distinction is the whole design. A win-probability model asks "will this
horse win?" and is then compared to a price it had no part in forming. This
model asks "does backing this horse return more than it costs?" and learns
which feature patterns are systematically underpriced — without ever being
shown the price it is beating.

WHY HUBER, AND WHY A CAP
------------------------
The P/L target is savage: mean -0.2172 (which is simply the overround), sigma
3.59, max +327, and the top 1% of rows carry 37.4% of all winnings. Squared
loss on that chases a handful of 300/1 shots and calls it signal. So:

  - objective is Huber, which bounds the influence of the tail
  - --cap-sp winsorises the label, defaulting to 34.0. The longshot audit
    found 149 picks at SP >= 26 produced 1 winner and -82.6% ROI, so the far
    tail is not a place edge lives; letting it dominate the loss is choosing
    to fit noise.
  - a real validation year drives early stopping, so the tree count is chosen
    out of sample rather than asserted

SPLIT
-----
Three-way and strictly temporal: train <= 2023, validate 2024, test 2025.
The win models used train/test only; a value model needs its own validation
slice or the early stopping leaks the test year.

HOW IT IS JUDGED
----------------
Not by RMSE, which nobody can bet. Every model is scored the way the money
works, against the two benchmarks that have beaten everything so far:

  - back the highest predicted-EV horse in each race
  - back every horse whose predicted EV clears a threshold (the real staking
    rule, which may bet zero or several times in a race)
  - the SP favourite over the identical races
  - the staged leak-free win model's top pick, loaded and scored here so the
    comparison is like for like rather than quoted from another run

BOUNDARY
--------
models/sqpe_value_staging/ only. No --promote flag. Live weights are frozen
under the hard laws in CLAUDE.md and promotion is an operator decision taken
on the economics below.

Usage:
    python scripts/ops/train_sqpe_value_model.py
    python scripts/ops/train_sqpe_value_model.py --sample 200000   # dev
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pickle
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FEATURES_PARQUET = ROOT / "data" / "raceform_v17_features.parquet"
LEAK_FREE_DIR = ROOT / "models" / "sqpe_leak_free_staging"
STAGING_DIR = ROOT / "models" / "sqpe_value_staging"


def _leak_free_features() -> list[str]:
    """Import the feature list from the leak-free trainer.

    Restating it here would let the two drift, and a value model quietly
    trained on rpr_num would look spectacular for exactly the wrong reason.
    """
    spec = importlib.util.spec_from_file_location(
        "_lf", ROOT / "scripts" / "ops" / "retrain_sqpe_leak_free.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    banned = set(mod.BANNED_LEAK_FEATURES)
    feats = list(mod.LEAK_FREE_FEATURES)
    assert not (banned & set(feats)), "leak-free feature list is self-inconsistent"
    return feats


def _bootstrap_ci(pl: np.ndarray, iters: int = 10000, seed: int = 29):
    if len(pl) == 0:
        return None, None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(pl), size=(iters, len(pl)))
    m = pl[idx].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def _econ(label: str, pl: np.ndarray, sp: np.ndarray, won: np.ndarray) -> dict:
    n = len(pl)
    if n == 0:
        return {"strategy": label, "bets": 0}
    lo, hi = _bootstrap_ci(pl)
    return {
        "strategy": label,
        "bets": int(n),
        "wins": int(won.sum()),
        "strike_rate": round(float(won.mean()), 4),
        "avg_sp": round(float(sp.mean()), 3),
        "pl_points": round(float(pl.sum()), 2),
        "roi": round(float(pl.mean()), 4),
        "roi_ci95": [round(lo, 4), round(hi, 4)],
    }


def _print_econ(e: dict) -> None:
    if not e.get("bets"):
        print(f"  {e['strategy']:<40} (no bets)")
        return
    lo, hi = e["roi_ci95"]
    print(f"  {e['strategy']:<40}n={e['bets']:<6} SR={e['strike_rate']:6.2%}  "
          f"avgSP={e['avg_sp']:6.2f}  P/L={e['pl_points']:+9.1f}  "
          f"ROI={e['roi']:+7.2%}  [{lo:+.1%}, {hi:+.1%}]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--features", default=str(FEATURES_PARQUET))
    ap.add_argument("--output", default=str(STAGING_DIR))
    ap.add_argument("--sample", type=int, default=None,
                    help="Approximate row cap for a dev run. Sampled by RACE, never by row.")
    ap.add_argument("--cap-sp", type=float, default=34.0,
                    help="Winsorise the P/L label at this SP (default 34.0 = 33/1).")
    ap.add_argument("--train-end", type=int, default=2023)
    ap.add_argument("--valid-year", type=int, default=2024)
    args = ap.parse_args()

    import lightgbm as lgb

    FEATS = _leak_free_features()
    print("=" * 74)
    print("VÉLØ — Value model (target = profit and loss, not win)")
    print(f"  Features : {len(FEATS)} leak-free, imported from retrain_sqpe_leak_free.py")
    print(f"  Label    : (sp_dec - 1) if won else -1, SP winsorised at {args.cap_sp}")
    print(f"  Split    : train <= {args.train_end} | valid {args.valid_year} | test > {args.valid_year}")
    print(f"  Output   : {args.output}  (staging only — no promotion path)")
    print("=" * 74)

    cols = list(dict.fromkeys(FEATS + ["race_id", "date_parsed", "target", "sp_dec", "pos"]))
    df = pd.read_parquet(args.features, columns=cols)
    if not pd.api.types.is_datetime64_any_dtype(df["date_parsed"]):
        df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")

    df = df[pd.to_numeric(df["pos"].astype(str).str.strip(), errors="coerce").notna()]
    df = df[(df["sp_dec"] > 1.0) & df["sp_dec"].notna()]
    print(f"\n{len(df):,} runner rows with a settleable price")

    if args.sample:
        avg = max(len(df) / df["race_id"].nunique(), 1.0)
        keep = (df["race_id"].drop_duplicates()
                  .sample(n=min(int(args.sample / avg), df["race_id"].nunique()), random_state=42))
        df = df[df["race_id"].isin(keep)]
        print(f"  dev sample: {len(df):,} rows across {df['race_id'].nunique():,} whole races")

    # The label. SP enters here and nowhere else.
    sp_capped = df["sp_dec"].clip(upper=args.cap_sp)
    df["pl"] = np.where(df["target"] == 1, sp_capped - 1.0, -1.0)

    yr = df["date_parsed"].dt.year
    tr = df[yr <= args.train_end]
    va = df[yr == args.valid_year]
    te = df[yr > args.valid_year].copy()
    print(f"\ntrain {len(tr):,}  valid {len(va):,}  test {len(te):,} "
          f"({te['race_id'].nunique():,} test races)")
    print(f"label mean — train {tr['pl'].mean():+.4f}  valid {va['pl'].mean():+.4f}  "
          f"test {te['pl'].mean():+.4f}   (this is the overround you must beat)")

    model = lgb.LGBMRegressor(
        objective="huber", alpha=2.0,
        n_estimators=3000, learning_rate=0.03,
        num_leaves=63, min_child_samples=200,
        subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
        reg_lambda=5.0, random_state=42, n_jobs=-1, verbose=-1,
    )
    print("\ntraining LightGBM (huber) with early stopping on the validation year ...")
    model.fit(tr[FEATS], tr["pl"],
              eval_set=[(va[FEATS], va["pl"])], eval_metric="huber",
              callbacks=[lgb.early_stopping(100, verbose=False), lgb.log_evaluation(0)])
    best_iter = model.best_iteration_ or model.n_estimators
    print(f"  best iteration: {best_iter} of {model.n_estimators}")

    te["ev"] = model.predict(te[FEATS])
    te["won"] = (te["target"] == 1).astype(int)
    # Settle at the TRUE price, never the capped one — the cap shapes the loss
    # during training, it must not flatter the accounts afterwards.
    te["settle_pl"] = np.where(te["won"] == 1, te["sp_dec"] - 1.0, -1.0)

    print(f"\n{'=' * 74}\nECONOMICS ON THE TEST YEARS — every figure is 1pt level stakes at SP\n")
    results = []

    top = te.loc[te.groupby("race_id")["ev"].idxmax()]
    e = _econ("value model — top EV pick per race",
              top["settle_pl"].to_numpy(), top["sp_dec"].to_numpy(), top["won"].to_numpy())
    results.append(e); _print_econ(e)

    fav = te.loc[te.groupby("race_id")["sp_dec"].idxmin()]
    e = _econ("SP favourite (same races)",
              fav["settle_pl"].to_numpy(), fav["sp_dec"].to_numpy(), fav["won"].to_numpy())
    results.append(e); _print_econ(e)

    lf_path = LEAK_FREE_DIR / "sqpe_leak_free.pkl"
    if lf_path.exists():
        try:
            with open(lf_path, "rb") as fh:
                lf = pickle.load(fh)
            # retrain_sqpe_leak_free.py trains on .fillna(0); LightGBM handles
            # NaN natively and must NOT be filled. Feed each what it expects.
            te["p_win"] = lf.predict_proba(te[FEATS].fillna(0))[:, 1]
            lft = te.loc[te.groupby("race_id")["p_win"].idxmax()]
            e = _econ("leak-free win model — top pick",
                      lft["settle_pl"].to_numpy(), lft["sp_dec"].to_numpy(), lft["won"].to_numpy())
            results.append(e); _print_econ(e)
        except Exception as exc:
            print(f"  (leak-free win model not comparable: {type(exc).__name__}: {exc})")

    ev = te["ev"].to_numpy()
    print(f"\n  predicted EV distribution: min={ev.min():+.3f}  p50={np.percentile(ev,50):+.3f}  "
          f"p99={np.percentile(ev,99):+.3f}  max={ev.max():+.3f}")
    print("  threshold staking — back the top slice by predicted EV:")
    thresholds = []
    for pct in [50, 75, 90, 95, 99, 99.5]:
        thr = float(np.percentile(ev, pct))
        sel = te[te["ev"] > thr]
        if len(sel) < 50:
            continue
        e = _econ(f"  top {100 - pct:g}% by EV (> {thr:+.3f})",
                  sel["settle_pl"].to_numpy(), sel["sp_dec"].to_numpy(), sel["won"].to_numpy())
        e["percentile"] = pct
        e["threshold"] = round(thr, 4)
        thresholds.append(e); _print_econ(e)

    imp = sorted(zip(FEATS, model.feature_importances_), key=lambda x: -x[1])
    print(f"\n{'=' * 74}\nTOP 12 FEATURES")
    for f, v in imp[:12]:
        print(f"  {f:<32} {v}")

    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    with open(out / "sqpe_value.pkl", "wb") as fh:
        pickle.dump(model, fh)
    meta = {
        "version": "value_v1",
        "model_type": "LightGBMRegressor(objective=huber) on P/L target",
        "trained_at": datetime.now(UTC).isoformat(),
        "development_run": bool(args.sample),
        "target": "(sp_dec - 1) if win else -1.0",
        "target_sp_cap": args.cap_sp,
        "sp_used_as": "LABEL ONLY — never a feature",
        "n_features": len(FEATS),
        "feature_names": FEATS,
        "split": {"train_end": args.train_end, "valid_year": args.valid_year},
        "rows": {"train": int(len(tr)), "valid": int(len(va)), "test": int(len(te))},
        "test_races": int(te["race_id"].nunique()),
        "best_iteration": int(best_iter),
        "economics": results,
        "threshold_staking": thresholds,
        "top_features": [{"feature": f, "importance": int(v)} for f, v in imp[:20]],
        "promotion": "BLOCKED — staging only; operator decision on economics.",
    }
    (out / "metadata.json").write_text(json.dumps(meta, indent=2))
    print(f"\n{'=' * 74}\nStaged: {out / 'sqpe_value.pkl'}\nNOT promoted. Live weights unchanged.\n{'=' * 74}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
