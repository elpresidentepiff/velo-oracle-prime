#!/usr/bin/env python3
"""Forward-only forecasting research lanes derived from the 2026-09-26 lab.

This packet is measurement-only.  It reads the already-persisted, pre-race
runner components for a scored day and emits three frozen shadow lanes:

* calibrated_g: temperature-calibrated production Prime/G probabilities;
* sqpe_mds: the production-pattern SQPE + MDS subset, without improvement;
* market_blind_core: the frozen pairwise-core ranker selected chronologically.

It never writes verdicts, canonical state, model files, weights, stakes,
notifications, or Supabase.  Dates inside the fitting/holdout window are
refused so the evidence accumulated by this runner is forward-only.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo.verdict_loader import load_verdicts  # noqa: E402

EVIDENCE_END_DATE = "2026-09-24"
MODEL_VERSION = "FORECASTING_SHADOW_PACKAGE_V1"
CALIBRATED_G_BETA = 0.43
SQPE_MDS_BETA = 0.42
SQPE_MDS_WEIGHTS = {"sqpe_v17_prob": 0.45, "market_deception_score": 0.10}
RANKER_GAMMA = 0.64
RANKER_COEFFICIENTS = {
    "sqpe_v17_prob": 1.829402157427119,
    "improvement_score": -2.5379787878905558,
    "market_deception_score": 13.391475438726784,
}
LANE_MODELS = {
    "calibrated_g": "CALIBRATED_G_SHADOW_V1",
    "sqpe_mds": "SQPE_MDS_SHADOW_V1",
    "market_blind_core": "MARKET_BLIND_CORE_SHADOW_V1",
}


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalise(values: list[float | None]) -> list[float | None]:
    positive = [max(value, 0.0) if value is not None else None for value in values]
    total = sum(value for value in positive if value is not None)
    if total <= 0.0:
        return [None] * len(values)
    return [None if value is None else value / total for value in positive]


def power_transform(values: list[float | None], beta: float) -> list[float | None]:
    powered = [None if value is None else max(value, 0.0) ** beta for value in values]
    return _normalise(powered)


def calibrated_g_probabilities(predictions: list[dict[str, Any]]) -> list[float | None]:
    return power_transform([_num(row.get("velo_prime_prob")) for row in predictions], CALIBRATED_G_BETA)


def sqpe_mds_probabilities(predictions: list[dict[str, Any]]) -> list[float | None]:
    raw: list[float | None] = []
    for row in predictions:
        available = [(name, _num(row.get(name))) for name in SQPE_MDS_WEIGHTS]
        available = [(name, value) for name, value in available if value is not None]
        denominator = sum(SQPE_MDS_WEIGHTS[name] for name, _value in available)
        raw.append(
            sum(SQPE_MDS_WEIGHTS[name] * value for name, value in available) / denominator
            if denominator > 0.0
            else None
        )
    return power_transform(_normalise(raw), SQPE_MDS_BETA)


def market_blind_core_probabilities(predictions: list[dict[str, Any]]) -> list[float | None]:
    if not predictions:
        return []
    scores = [
        sum(RANKER_COEFFICIENTS[name] * (_num(row.get(name)) or 0.0) for name in RANKER_COEFFICIENTS)
        for row in predictions
    ]
    maximum = max(scores)
    exponentials = [math.exp(max(-50.0, min(0.0, RANKER_GAMMA * (score - maximum)))) for score in scores]
    total = sum(exponentials)
    return [value / total for value in exponentials]


def _ranks(probabilities: list[float | None]) -> list[int | None]:
    order = sorted(
        (index for index, value in enumerate(probabilities) if value is not None),
        key=lambda index: (-float(probabilities[index]), index),
    )
    ranks: list[int | None] = [None] * len(probabilities)
    for rank, index in enumerate(order, start=1):
        ranks[index] = rank
    return ranks


def build_packet(date: str, verdicts: list[dict[str, Any]], load_method: str) -> dict[str, Any]:
    races = []
    lane_agreement = {lane: 0 for lane in LANE_MODELS}
    for verdict in sorted(verdicts, key=lambda row: str(row.get("race_id"))):
        full_analysis = verdict.get("full_analysis")
        if isinstance(full_analysis, str):
            try:
                full_analysis = json.loads(full_analysis)
            except json.JSONDecodeError:
                full_analysis = {}
        predictions = [row for row in ((full_analysis or {}).get("predictions") or []) if isinstance(row, dict)]
        if not predictions:
            continue

        live_probabilities = [_num(row.get("velo_prime_prob")) for row in predictions]
        live_ranks = _ranks(live_probabilities)
        lane_probabilities = {
            "calibrated_g": calibrated_g_probabilities(predictions),
            "sqpe_mds": sqpe_mds_probabilities(predictions),
            "market_blind_core": market_blind_core_probabilities(predictions),
        }
        lanes = {}
        for lane, probabilities in lane_probabilities.items():
            ranks = _ranks(probabilities)
            runners = sorted(
                (
                    {
                        "horse": row.get("horse"),
                        "horse_id": row.get("horse_id"),
                        "probability": None if probabilities[index] is None else round(float(probabilities[index]), 8),
                        "rank": ranks[index],
                        "live_rank": live_ranks[index],
                    }
                    for index, row in enumerate(predictions)
                ),
                key=lambda row: (row["rank"] is None, row["rank"] or 0),
            )
            top = runners[0] if runners and runners[0]["rank"] == 1 else None
            agrees = bool(top and top.get("live_rank") == 1)
            lane_agreement[lane] += int(agrees)
            lanes[lane] = {
                "model_name": LANE_MODELS[lane],
                "top_pick": top,
                "agrees_with_live_top_pick": agrees,
                "runners": runners,
            }
        races.append(
            {
                "race_id": str(verdict.get("race_id") or ""),
                "verdict_generated_at": verdict.get("generated_at"),
                "lanes": lanes,
            }
        )

    return {
        "date": date,
        "generated_at": datetime.now(UTC).isoformat(),
        "model_version": MODEL_VERSION,
        "classification": "FORWARD_ONLY_SHADOW_ANALYSIS",
        "evidence_window_ended": EVIDENCE_END_DATE,
        "source": "Supabase velo_verdicts.full_analysis.predictions[]",
        "verdict_load_method": load_method,
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "stake_authorised": False,
        "supabase_write_authorised": False,
        "promotion_authorised": False,
        "parameters": {
            "calibrated_g": {"beta": CALIBRATED_G_BETA, "ranking_must_match_live": True},
            "sqpe_mds": {"weights": SQPE_MDS_WEIGHTS, "beta": SQPE_MDS_BETA},
            "market_blind_core": {
                "gamma": RANKER_GAMMA,
                "coefficients": RANKER_COEFFICIENTS,
                "raw_odds_features": [],
            },
        },
        "promotion_gate": ">=300 forward settled disagreement races per lane plus operator decision",
        "race_count": len(races),
        "lane_agreement_with_live": lane_agreement,
        "races": races,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Forward-only Velo forecasting shadow package.")
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    if args.date <= EVIDENCE_END_DATE:
        print(f"[REFUSED] {args.date} is inside the fitted/evaluated evidence window through {EVIDENCE_END_DATE}.")
        return 2

    try:
        from dotenv import load_dotenv

        load_dotenv(str(ROOT / ".env"))
    except Exception:
        pass
    verdicts, method = load_verdicts(
        args.date,
        select="race_id,generated_at,full_analysis",
    )
    if method != "race_id":
        print(f"[REFUSED] verdict_loader method={method}; exact race-date membership is required.")
        return 2
    packet = build_packet(args.date, verdicts, method)
    if not packet["races"]:
        print(f"[FAIL] No complete runner fields were available for {args.date}.")
        return 1
    tag = args.date.replace("-", "_")
    output = ROOT / "data" / "reports" / f"forecasting_shadow_package_{tag}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    print(
        f"FORECASTING_SHADOW_PACKAGE {args.date}: races={packet['race_count']} "
        f"agreement={packet['lane_agreement_with_live']} -> {output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
