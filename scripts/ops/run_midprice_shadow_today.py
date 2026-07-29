"""
Mid-Price Specialist Shadow Lane — daily paper scorer.

Scores today's racecard with models/sqpe_v17_midprice_specialist_staging
(LAB_EXPERIMENT, trained 2026-07-27: market-blind GBM+isotonic over 25
behavioural/handicap features, RPR and all SP/market features banned).

Why this lane exists (proven 2026-07-29, ONE_TRUTH Subsystem Truth Board):
65% of live VELO misses are mid_priced_won (median winner SP 4.8), and in
62% of the snapshot-verified cases the winner sat at VELO rank 4+ with a
median VP gap of 0.234 — a model blind spot, not a selection problem. This
lane measures whether the specialist actually sees those runners, in the
honest multimodel ledger, before any promotion talk.

PAPER ONLY: no Supabase writes, no Telegram, no live-scoring effect.
trust_policy=ARCHIVE_CONTEXT_ONLY_NOT_SCORING on every output row.

Usage:
    PYTHONPATH=. python scripts/ops/run_midprice_shadow_today.py --date YYYY-MM-DD
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.services.sqpe_v17_service import (  # noqa: E402
    _resolve_decimal_odds,
    build_v17_feature_vector,
)
from src.velo.racecard_loader import load_racecards  # noqa: E402

MODEL_DIR = ROOT / "models" / "sqpe_v17_midprice_specialist_staging"
MODEL_PKL = MODEL_DIR / "sqpe_v17_midprice_specialist.pkl"
METADATA = MODEL_DIR / "metadata.json"
OUT_DIR = ROOT / "data" / "reports"


def _load_specialist():
    meta = json.loads(METADATA.read_text(encoding="utf-8"))
    with MODEL_PKL.open("rb") as f:
        model = pickle.load(f)
    return model, meta


def score_date(date_str: str) -> dict:
    date_tag = date_str.replace("-", "_")
    model, meta = _load_specialist()
    features = meta["specialist_features"]
    band_lo, band_hi = meta.get("mid_price_band", [3.0, 10.0])

    races, source_label = load_racecards(
        date_tag=date_tag, date_str=date_str, data_root=ROOT / "data"
    )
    if not races:
        raise SystemExit(f"No racecards found for {date_str} — run capture/parse first.")

    out_races = []
    n_band_runners = 0
    for race in races:
        runners = race.get("runners", [])
        scored = []
        for runner in runners:
            fv = build_v17_feature_vector(runner, race)
            row = pd.DataFrame(
                [{f: float(fv.get(f, 0.0) or 0.0) for f in features}], columns=features
            )
            try:
                prob = float(model.predict_proba(row)[0][1])
            except Exception:
                continue
            odds = _resolve_decimal_odds(runner)
            in_band = bool(odds and band_lo <= odds <= band_hi)
            if in_band:
                n_band_runners += 1
            scored.append(
                {
                    "horse": runner.get("horse") or runner.get("name"),
                    "midprice_prob": round(prob, 4),
                    "odds_decimal": odds or None,
                    "in_band": in_band,
                }
            )
        scored.sort(key=lambda x: x["midprice_prob"], reverse=True)
        band_runners = [s for s in scored if s["in_band"]]
        top_pick = band_runners[0] if band_runners else None
        out_races.append(
            {
                "race_id": str(race.get("race_id", "")),
                "course": race.get("course"),
                "off": race.get("off_time") or race.get("off"),
                "top_pick": top_pick,
                "band_runner_count": len(band_runners),
                "no_pick_reason": None if top_pick else "NO_BAND_RUNNERS",
                "all_scored": scored,
            }
        )

    packet = {
        "generated_at": datetime.now(UTC).isoformat(),
        "date": date_str,
        "model_version": meta.get("version"),
        "model_classification": meta.get("classification"),
        "source": source_label,
        "mid_price_band": [band_lo, band_hi],
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "stake_authorised": False,
        "races": out_races,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"midprice_shadow_{date_tag}.json"
    out_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")

    picks = sum(1 for r in out_races if r["top_pick"])
    print(f"MIDPRICE SHADOW — {date_str} ({source_label})")
    print(f"  races={len(out_races)} picks={picks} band_runners={n_band_runners}")
    print(f"  -> {out_path.relative_to(ROOT)}")
    print("  PAPER ONLY: no Supabase, no Telegram, no live-scoring effect.")
    return packet


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = p.parse_args()
    score_date(args.date)


if __name__ == "__main__":
    main()
