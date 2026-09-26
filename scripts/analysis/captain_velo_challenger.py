#!/usr/bin/env python3
"""Evaluate the frozen Captain Velo selective-value challenger.

Captain Velo is deliberately a decision layer, not a replacement production
forecast.  It combines the already-audited SQPE+MDS structural shadow with a
pre-off market prior, then abstains unless the independent structural view and
the available quote both clear fixed margins.

The historical holdout used here has already been inspected by the wider
forecasting laboratory.  Results are therefore retrospective diagnostics, not
fresh promotion evidence.  No model, weight, verdict, stake, gate, or database
state is written by this script.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analysis.prime_probability_calibration_challenger import (  # noqa: E402
    load_historical_races,
    split_chronologically,
)

MODEL_VERSION = "CAPTAIN_VELO_VALUE_V1"
EVIDENCE_END_DATE = "2026-09-24"
EPSILON = 1e-12

# These are frozen from the 2026-09-26 mechanism/calibration laboratory and
# the deliberately small decision contract tested in this challenger.
STRUCTURAL_WEIGHTS = {"sqpe_v17_prob": 0.45, "market_deception_score": 0.10}
STRUCTURAL_BETA = 0.42
MARKET_BLEND_ALPHA = 0.80
MIN_STRUCTURAL_MARKET_RATIO = 1.20
MIN_QUOTED_EXPECTED_EDGE = 0.10
MIN_DECIMAL_ODDS = 2.0
MAX_DECIMAL_ODDS = 20.0
BOOTSTRAP_SEED = 1981


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalise(values: list[float | None]) -> list[float] | None:
    if not values or any(value is None for value in values):
        return None
    positive = [max(float(value), 0.0) for value in values]
    total = sum(positive)
    return [value / total for value in positive] if total > 0.0 else None


def _power_transform(probabilities: list[float], beta: float) -> list[float]:
    powered = [max(probability, EPSILON) ** beta for probability in probabilities]
    total = sum(powered)
    return [value / total for value in powered]


def market_probabilities(field: list[dict[str, Any]]) -> list[float] | None:
    """Remove overround from the complete captured pre-off decimal quote field."""
    odds = [_num(row.get("sp_dec")) for row in field]
    if any(value is None or value <= 1.0 for value in odds):
        return None
    return _normalise([1.0 / float(value) for value in odds])


def structural_probabilities(field: list[dict[str, Any]]) -> list[float] | None:
    """Frozen SQPE+MDS probability surface; improvement is intentionally absent."""
    raw: list[float | None] = []
    for row in field:
        available = [
            (name, _num(row.get(name)))
            for name in STRUCTURAL_WEIGHTS
            if _num(row.get(name)) is not None
        ]
        denominator = sum(STRUCTURAL_WEIGHTS[name] for name, _value in available)
        raw.append(
            sum(STRUCTURAL_WEIGHTS[name] * float(value) for name, value in available) / denominator
            if denominator > 0.0
            else None
        )
    probabilities = _normalise(raw)
    return _power_transform(probabilities, STRUCTURAL_BETA) if probabilities is not None else None


def consensus_probabilities(field: list[dict[str, Any]]) -> list[float] | None:
    """Geometrically pool structural evidence with the market prior."""
    structural = structural_probabilities(field)
    market = market_probabilities(field)
    if structural is None or market is None:
        return None
    pooled = [
        max(model_probability, EPSILON) ** (1.0 - MARKET_BLEND_ALPHA)
        * max(market_probability, EPSILON) ** MARKET_BLEND_ALPHA
        for model_probability, market_probability in zip(structural, market, strict=True)
    ]
    return _normalise(pooled)


def score_field(field: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    market = market_probabilities(field)
    structural = structural_probabilities(field)
    consensus = consensus_probabilities(field)
    if market is None or structural is None or consensus is None:
        return None
    scored = []
    for index, row in enumerate(field):
        odds = float(row["sp_dec"])
        ratio = structural[index] / max(market[index], EPSILON)
        expected_edge = consensus[index] * odds - 1.0
        scored.append(
            {
                "index": index,
                "horse": row.get("horse"),
                "horse_id": row.get("horse_id"),
                "decimal_odds": odds,
                "market_probability": market[index],
                "structural_probability": structural[index],
                "consensus_probability": consensus[index],
                "structural_market_ratio": ratio,
                "quoted_expected_edge": expected_edge,
                "eligible": (
                    MIN_DECIMAL_ODDS <= odds <= MAX_DECIMAL_ODDS
                    and ratio >= MIN_STRUCTURAL_MARKET_RATIO
                    and expected_edge >= MIN_QUOTED_EXPECTED_EDGE
                ),
            }
        )
    return scored


def select_value_pick(field: list[dict[str, Any]]) -> dict[str, Any] | None:
    scored = score_field(field)
    if scored is None:
        return None
    eligible = [row for row in scored if row["eligible"]]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda row: (
            row["quoted_expected_edge"],
            row["structural_market_ratio"],
            row["consensus_probability"],
            -row["index"],
        ),
    )


def _quoted_pnl(race: dict[str, Any], index: int) -> float | None:
    odds = _num(race["source_field"][index].get("sp_dec"))
    if odds is None or odds <= 1.0:
        return None
    return odds - 1.0 if index == int(race["winner_index"]) else -1.0


def _top_index(values: list[float | None]) -> int | None:
    available = [index for index, value in enumerate(values) if value is not None]
    return max(available, key=lambda index: (float(values[index]), -index)) if available else None


def _summarise(rows: list[dict[str, Any]], pnl_key: str = "pnl") -> dict[str, Any]:
    usable = [row for row in rows if row.get(pnl_key) is not None]
    if not usable:
        return {"bets": 0, "wins": 0, "hit_rate": None, "profit": 0.0, "roi": None}
    pnl = [float(row[pnl_key]) for row in usable]
    wins = sum(value > 0.0 for value in pnl)
    return {
        "bets": len(usable),
        "wins": wins,
        "hit_rate": wins / len(usable),
        "profit": sum(pnl),
        "roi": statistics.fmean(pnl),
        "average_decimal_odds": statistics.fmean(float(row[f"{pnl_key}_odds"]) for row in usable),
    }


def _bootstrap_mean(values: list[float], samples: int, seed: int = BOOTSTRAP_SEED) -> list[float]:
    if not values or samples <= 0:
        return []
    rng = random.Random(seed)
    estimates = sorted(statistics.fmean(rng.choice(values) for _ in values) for _ in range(samples))
    lower_index = max(0, int(0.025 * samples) - 1)
    upper_index = min(samples - 1, int(0.975 * samples))
    return [estimates[lower_index], estimates[upper_index]]


def evaluate_policy(races: list[dict[str, Any]], bootstrap_samples: int = 5000) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    skipped = defaultdict(int)
    for race in races:
        field = race["source_field"]
        scored = score_field(field)
        if scored is None:
            skipped["incomplete_price_or_component_field"] += 1
            continue
        pick = select_value_pick(field)
        if pick is None:
            skipped["policy_abstention"] += 1
            continue

        market_index = _top_index([row["market_probability"] for row in scored])
        structural_index = _top_index([row["structural_probability"] for row in scored])
        g_index = _top_index([_num(row.get("g_prob")) for row in race["runners"]])
        base_index = _top_index([_num(row.get("base_prob")) for row in race["runners"]])
        indexes = {
            "pnl": int(pick["index"]),
            "market_pnl": market_index,
            "structural_pnl": structural_index,
            "g_pnl": g_index,
            "base_pnl": base_index,
        }
        row: dict[str, Any] = {
            "race_date": race["race_date"],
            "race_id": race["race_id"],
            "course": race.get("course"),
            "off_time": race.get("off_time"),
            "winner": race.get("winner_name"),
            "selection": pick["horse"],
            "selection_index": pick["index"],
            "decimal_odds": pick["decimal_odds"],
            "market_probability": pick["market_probability"],
            "structural_probability": pick["structural_probability"],
            "consensus_probability": pick["consensus_probability"],
            "structural_market_ratio": pick["structural_market_ratio"],
            "quoted_expected_edge": pick["quoted_expected_edge"],
        }
        for key, index in indexes.items():
            if index is None:
                row[key] = None
                row[f"{key}_odds"] = None
                row[f"{key}_selection"] = None
                continue
            row[key] = _quoted_pnl(race, index)
            row[f"{key}_odds"] = _num(field[index].get("sp_dec"))
            row[f"{key}_selection"] = field[index].get("horse")
        rows.append(row)

    summary = _summarise(rows)
    summary["roi_bootstrap_95pct"] = _bootstrap_mean(
        [float(row["pnl"]) for row in rows if row.get("pnl") is not None], bootstrap_samples
    )
    summary["average_structural_market_ratio"] = (
        statistics.fmean(float(row["structural_market_ratio"]) for row in rows) if rows else None
    )
    summary["average_quoted_expected_edge"] = (
        statistics.fmean(float(row["quoted_expected_edge"]) for row in rows) if rows else None
    )
    summary["benchmarks_on_same_races"] = {
        "captured_market_favourite": _summarise(rows, "market_pnl"),
        "production_g_top": _summarise(rows, "g_pnl"),
        "production_base_top": _summarise(rows, "base_pnl"),
        "structural_top": _summarise(rows, "structural_pnl"),
    }
    summary["paired_roi_delta_bootstrap_95pct"] = {
        label: _bootstrap_mean(
            [float(row["pnl"]) - float(row[key]) for row in rows if row.get(key) is not None],
            bootstrap_samples,
            BOOTSTRAP_SEED + offset,
        )
        for offset, (label, key) in enumerate(
            (("vs_market_favourite", "market_pnl"), ("vs_production_g", "g_pnl")), start=1
        )
    }
    monthly: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        monthly[str(row["race_date"])[:7]].append(row)
    summary["monthly"] = {month: _summarise(month_rows) for month, month_rows in sorted(monthly.items())}
    summary["skipped"] = dict(skipped)
    return {"summary": summary, "rows": rows}


def _block_summary(races: list[dict[str, Any]]) -> dict[str, Any]:
    dates = sorted({str(race["race_date"]) for race in races})
    return {
        "races": len(races),
        "start": dates[0] if dates else None,
        "end": dates[-1] if dates else None,
        "complete_price_fields": sum(market_probabilities(race["source_field"]) is not None for race in races),
    }


def run_challenger(
    races: list[dict[str, Any]],
    output_dir: Path,
    bootstrap_samples: int = 5000,
    source_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocks = split_chronologically(races)
    calibration = evaluate_policy(blocks["calibration"], bootstrap_samples)
    test = evaluate_policy(blocks["test"], bootstrap_samples)
    test_roi = test["summary"].get("roi")
    test_interval = test["summary"].get("roi_bootstrap_95pct") or []
    status = "RETROSPECTIVE_EDGE_NOT_REPLICATED"
    if test_roi is not None and test_roi > 0.0:
        status = "POSITIVE_POINT_ESTIMATE_NOT_FORWARD_PROVEN"
    if test_interval and test_interval[0] > 0.0:
        status = "RETROSPECTIVE_INTERVAL_POSITIVE_FORWARD_PROOF_STILL_REQUIRED"

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "model_version": MODEL_VERSION,
        "classification": "ANALYSIS_ONLY_RETROSPECTIVE_REUSED_HOLDOUT",
        "evidence_end_date": EVIDENCE_END_DATE,
        "truth_disclosure": (
            "The final chronological block was already inspected by earlier forecasting work and during "
            "challenger design. It is not a pristine holdout and cannot authorize promotion."
        ),
        "decision_contract": {
            "structural_features": list(STRUCTURAL_WEIGHTS),
            "structural_weights": STRUCTURAL_WEIGHTS,
            "structural_beta": STRUCTURAL_BETA,
            "market_source": "complete captured pre-off sp_dec field with overround removed",
            "market_blend_alpha": MARKET_BLEND_ALPHA,
            "minimum_structural_market_ratio": MIN_STRUCTURAL_MARKET_RATIO,
            "minimum_quoted_expected_edge": MIN_QUOTED_EXPECTED_EDGE,
            "decimal_odds_range": [MIN_DECIMAL_ODDS, MAX_DECIMAL_ODDS],
            "maximum_selections_per_race": 1,
            "abstention_allowed": True,
            "improvement_score_used": False,
            "sqpe_no_rpr_shadow_used": False,
        },
        "blocks": {name: _block_summary(block) for name, block in blocks.items()},
        "source_diagnostics": source_diagnostics or {},
        "calibration_block_diagnostic": calibration["summary"],
        "reused_test_block_diagnostic": test["summary"],
        "readout": {
            "status": status,
            "promotion_authorized": False,
            "next_gate": "fresh forward-only shadow settlement after 2026-09-24",
        },
        "safety": {
            "production_scoring_changed": False,
            "production_weights_changed": False,
            "verdicts_written": False,
            "stakes_written": False,
            "bets_placed": False,
            "supabase_writes": False,
            "gates_changed": False,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "captain_velo_challenger.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
    )
    with (output_dir / "captain_velo_reused_holdout_selections.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        rows = test["rows"]
        fields = list(rows[0]) if rows else ["race_date", "race_id", "selection", "pnl"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    cal = calibration["summary"]
    tst = test["summary"]
    market = tst["benchmarks_on_same_races"]["captured_market_favourite"]
    g_top = tst["benchmarks_on_same_races"]["production_g_top"]
    markdown = [
        "# Captain Velo Value Challenger",
        "",
        "- Classification: **retrospective analysis only; reused holdout**",
        f"- Readout: **{status}**",
        "- Production promotion: **not authorized**",
        "- Bets placed: **none**",
        "",
        "## The mechanism",
        "",
        "Captain Velo starts with the captured pre-off market as a prior and adds a deliberately small "
        "independent SQPE+MDS correction. It abstains unless structural probability is at least 1.20x the "
        "market probability and the available quote clears a 10% expected-edge buffer. Improvement score "
        "is excluded because the mechanism ablation found that it harmed combinations.",
        "",
        "## Chronological diagnostics",
        "",
        "| Block | Bets | Wins | Profit | ROI | 95% bootstrap ROI |",
        "|---|---:|---:|---:|---:|---:|",
        f"| Calibration | {cal['bets']} | {cal['wins']} | {cal['profit']:.2f} | {cal['roi']:.2%} | "
        f"{cal['roi_bootstrap_95pct'][0]:.2%} to {cal['roi_bootstrap_95pct'][1]:.2%} |",
        f"| Reused test | {tst['bets']} | {tst['wins']} | {tst['profit']:.2f} | {tst['roi']:.2%} | "
        f"{tst['roi_bootstrap_95pct'][0]:.2%} to {tst['roi_bootstrap_95pct'][1]:.2%} |",
        "",
        "## Same-race comparison on the reused test selections",
        "",
        "| Decision | Bets | Wins | Profit | ROI |",
        "|---|---:|---:|---:|---:|",
        f"| Captain Velo | {tst['bets']} | {tst['wins']} | {tst['profit']:.2f} | {tst['roi']:.2%} |",
        f"| Captured market favourite | {market['bets']} | {market['wins']} | {market['profit']:.2f} | {market['roi']:.2%} |",
        f"| Production G top | {g_top['bets']} | {g_top['wins']} | {g_top['profit']:.2f} | {g_top['roi']:.2%} |",
        "",
        "## Honest interpretation",
        "",
        "The point estimate can beat the comparison policies while still being unproven. The final block is "
        "not pristine, the bet count is modest, and long-priced winners create wide variance. Only races "
        "strictly after 2026-09-24 can accumulate valid promotion evidence.",
    ]
    (output_dir / "CAPTAIN_VELO_READOUT.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    args = parser.parse_args()
    races, diagnostics = load_historical_races(args.data_dir, args.start_date, args.end_date)
    summary = run_challenger(races, args.output_dir, args.bootstrap_samples, diagnostics)
    print(
        json.dumps(
            {
                "model_version": summary["model_version"],
                "readout": summary["readout"],
                "reused_test": summary["reused_test_block_diagnostic"],
                "output_dir": str(args.output_dir.resolve()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
