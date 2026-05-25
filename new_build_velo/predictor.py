"""Sandbox predictor shell for New Build VELO.

Transparent baselines only. No model promotion, no old VP formula, no RPR.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from typing import Any

from new_build_velo.database import REPORT_ROOT, _iter_jsonl, _write_jsonl
from new_build_velo.features import BANNED_FEATURE_KEYS, FEATURE_PATH
from new_build_velo.spine import NEW_BUILD_ROOT, TRUST_POLICY, stable_id, utc_now, write_json


PREDICTION_ROOT = NEW_BUILD_ROOT / "predictions"
PREDICTION_PATH = PREDICTION_ROOT / "sandbox_predictions.jsonl"


def _bad_keys(row: dict[str, Any]) -> list[str]:
    allowed = {"rpr_policy", "rpr_feature_allowed"}
    return [key for key in row if key.lower() not in allowed and (key.lower() in BANNED_FEATURE_KEYS or "rpr" in key.lower())]


def _baseline_score(row: dict[str, Any]) -> float:
    trainer = float(row.get("trainer_win_rate") or 0.0)
    jockey = float(row.get("jockey_win_rate") or 0.0)
    rpdc = float(row.get("rpdc_release_score_avg") or 0.0)
    context = min(float(row.get("archive_flag_count") or 0.0), 5.0) / 20.0
    trap_penalty = 0.04 if row.get("tip_heat_flag") else 0.0
    return max(0.0, trainer * 0.35 + jockey * 0.25 + rpdc * 0.25 + context - trap_penalty)


def build_predictions(*, execute: bool = False) -> dict[str, Any]:
    feature_rows = list(_iter_jsonl(FEATURE_PATH))
    violations = [bad for row in feature_rows for bad in _bad_keys(row)]
    by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in feature_rows:
        by_race[str(row.get("race_id") or row.get("source_date"))].append(row)

    predictions: list[dict[str, Any]] = []
    for race_key, rows in by_race.items():
        scored = [(row, _baseline_score(row)) for row in rows]
        total = sum(score for _, score in scored)
        count = max(1, len(scored))
        if total <= 0:
            total = float(count)
            scored = [(row, 1.0) for row, _ in scored]
        ranked = sorted(scored, key=lambda item: item[1], reverse=True)
        for rank, (row, score) in enumerate(ranked, start=1):
            predictions.append(
                {
                    "prediction_id": stable_id(row.get("source_date"), row.get("race_id"), row.get("horse_key"), "sandbox_baseline"),
                    "source": "new_build_sandbox_predictor",
                    "source_date": row.get("source_date"),
                    "source_file": str(FEATURE_PATH),
                    "parser_version": "new_build_sandbox_predictor_v1",
                    "predicted_at": utc_now(),
                    "trust_policy": TRUST_POLICY,
                    "live_velo_impact": False,
                    "shadow_velo_impact": False,
                    "rpr_policy": "RPR_ARCHIVE_ONLY",
                    "new_build_velo_allowed": True,
                    "rpr_feature_allowed": False,
                    "race_key": race_key,
                    "race_id": row.get("race_id"),
                    "horse_key": row.get("horse_key"),
                    "rank": rank,
                    "random_baseline_probability": 1.0 / count,
                    "trainer_jockey_memory_score": float(row.get("trainer_win_rate") or 0.0) * 0.6 + float(row.get("jockey_win_rate") or 0.0) * 0.4,
                    "rpdc_memory_score": float(row.get("rpdc_release_score_avg") or 0.0),
                    "context_score": min(float(row.get("archive_flag_count") or 0.0), 5.0) / 5.0,
                    "sandbox_probability": score / total,
                    "baseline_family": "transparent_memory_context_baseline",
                    "outcome_linked": row.get("outcome_linked"),
                }
            )

    payload = {
        "generated_at": utc_now(),
        "classification": "NEW_BUILD_SANDBOX_PREDICTIONS_READY" if not violations else "NEW_BUILD_SANDBOX_PREDICTIONS_BLOCKED",
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "feature_rows": len(feature_rows),
        "prediction_rows": len(predictions),
        "race_count": len(by_race),
        "banned_feature_violations": len(violations),
        "rpr_excluded": not violations,
        "live_velo_touched": False,
        "shadow_velo_touched": False,
    }
    if execute:
        _write_jsonl(PREDICTION_PATH, predictions)
        write_json(REPORT_ROOT / "sandbox_prediction_baselines_latest.json", payload)
        lines = [
            "# New Build Sandbox Prediction Baselines",
            "",
            f"- Feature rows: {len(feature_rows)}",
            f"- Prediction rows: {len(predictions)}",
            f"- Race count: {len(by_race)}",
            f"- Banned/RPR violations: {len(violations)}",
            f"- RPR excluded: {payload['rpr_excluded']}",
            "",
            "Transparent baselines only. No Live VELO, Shadow VELO, model promotion, or old VP formula.",
        ]
        (REPORT_ROOT / "sandbox_prediction_baselines_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build New Build VELO sandbox baseline predictions.")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(build_predictions(execute=args.execute), indent=2, ensure_ascii=False))
    return 0
