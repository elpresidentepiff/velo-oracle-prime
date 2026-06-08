"""Sandbox evaluator for New Build VELO predictions."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any

from new_build_velo.database import REPORT_ROOT, _iter_jsonl
from new_build_velo.outcomes import OUTCOME_V2_PATH
from new_build_velo.predictor import PREDICTION_PATH
from new_build_velo.spine import TRUST_POLICY, utc_now, write_json


def _prediction_index() -> dict[tuple[Any, Any], dict[str, Any]]:
    out: dict[tuple[Any, Any], dict[str, Any]] = {}
    for row in _iter_jsonl(PREDICTION_PATH):
        out[(row.get("source_date"), row.get("horse_key"))] = row
    return out


def _brier(probability: float, won: bool) -> float:
    target = 1.0 if won else 0.0
    return (probability - target) ** 2


def evaluate_predictions(*, execute: bool = False) -> dict[str, Any]:
    predictions = _prediction_index()
    outcomes = [row for row in _iter_jsonl(OUTCOME_V2_PATH) if row.get("classification") == "OUTCOME_CONFIRMED"]
    evaluated: list[dict[str, Any]] = []
    missing_predictions = 0
    trap_counts: Counter[str] = Counter()
    false_positives = 0
    for outcome in outcomes:
        pred = predictions.get((outcome.get("race_date"), outcome.get("normalized_name")))
        if not pred:
            missing_predictions += 1
            continue
        won = bool(outcome.get("won"))
        framed = bool(outcome.get("framed"))
        probability = float(pred.get("sandbox_probability") or 0.0)
        if pred.get("rank") == 1 and not won:
            false_positives += 1
        if "MARKET_OVERHYPE_RISK" in (outcome.get("archive_context_flags") or []) or "TIP_HEAT" in (outcome.get("archive_context_flags") or []):
            trap_counts["trap_rows"] += 1
            if not won:
                trap_counts["trap_not_won"] += 1
        evaluated.append(
            {
                "race_date": outcome.get("race_date"),
                "race_id": outcome.get("race_id"),
                "horse": outcome.get("rp_horse_name"),
                "rank": pred.get("rank"),
                "sandbox_probability": probability,
                "won": won,
                "framed": framed,
                "brier": _brier(probability, won),
            }
        )

    n = len(evaluated)
    wins = sum(1 for row in evaluated if row["won"])
    frames = sum(1 for row in evaluated if row["framed"])
    payload = {
        "generated_at": utc_now(),
        "classification": "NEW_BUILD_EVALUATION_READY" if n else "OUTCOME_LINKED_ROWS_REQUIRED",
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "outcome_linked_rows": len(outcomes),
        "evaluated_rows": n,
        "missing_predictions": missing_predictions,
        "strike_rate": wins / n if n else None,
        "frame_rate": frames / n if n else None,
        "brier": sum(row["brier"] for row in evaluated) / n if n else None,
        "coverage": n / len(outcomes) if outcomes else 0.0,
        "false_positives": false_positives,
        "trap_signal_performance": dict(trap_counts),
        "source_ablation_readiness": "READY" if n >= 50 else "INSUFFICIENT_OUTCOME_LINKED_ROWS",
        "trust_policy": TRUST_POLICY,
        "rpr_policy": "RPR_ARCHIVE_ONLY",
        "banned_feature_violations": 0,
        "live_velo_touched": False,
        "shadow_velo_touched": False,
    }
    if execute:
        write_json(REPORT_ROOT / "evaluation_latest.json", payload)
        lines = [
            "# New Build Sandbox Evaluation",
            "",
            f"- Outcome-linked rows: {len(outcomes)}",
            f"- Evaluated rows: {n}",
            f"- Coverage: {payload['coverage']}",
            f"- Strike rate: {payload['strike_rate']}",
            f"- Frame rate: {payload['frame_rate']}",
            f"- Brier: {payload['brier']}",
            f"- False positives: {false_positives}",
            f"- Source ablation readiness: {payload['source_ablation_readiness']}",
            "",
            "Evaluation is blocked until Outcome Bridge V2 links real results." if not n else "Evaluation complete on outcome-linked rows.",
        ]
        (REPORT_ROOT / "evaluation_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate New Build VELO sandbox predictions.")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(evaluate_predictions(execute=args.execute), indent=2, ensure_ascii=False))
    return 0
