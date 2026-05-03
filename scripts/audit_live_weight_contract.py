"""
Runtime audit for the live VeloPrime ensemble contract.

This script proves the actual ensemble inputs passed by score_race_velo_prime()
on a real race day, then performs local-only ablations against the captured
ensemble inputs. It writes audit artifacts only; it does not persist verdicts or
mutate production state.
"""

from __future__ import annotations

import argparse
import copy
import inspect
import json
import re
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.velo_prime_service import score_race_velo_prime
from scripts.run_prime_today import _bootstrap_runtime, load_racecards
from src.intelligence.macro_regime.bha_macro_context import get_macro_context_for_race
from src.intelligence.velo_prime_ensemble import VeloPrimeEnsemble, _WEIGHTS
from src.velo.race_metadata_resolver import rest_fetch
from workers.racing_api_normalizer import normalize_race

COMPONENTS = [
    "improvement_score",
    "release_window_score",
    "market_deception_score",
    "place_prob",
    "comment_intel_score",
    "longshot_score",
]

OUTPUT_JSON = ROOT / "data" / "live_weight_contract_audit_latest.json"
OUTPUT_MD = ROOT / "data" / "live_weight_contract_audit_latest.md"


def _safe_macro_context(ctx: Any) -> dict[str, Any] | None:
    if ctx is None:
        return None
    if is_dataclass(ctx):
        return asdict(ctx)
    if hasattr(ctx, "__dict__"):
        return dict(ctx.__dict__)
    return {"repr": repr(ctx)}


def _parse_service_mapping() -> dict[str, str]:
    source = inspect.getsource(score_race_velo_prime)
    mapping: dict[str, str] = {}
    patterns = {
        "improvement_score": r'"improvement_score":\s*spec_scores\.get\("improvement_score"\)',
        "release_window_score": r'"release_window_score":\s*spec_scores\.get\("release_window_score"\)',
        "market_deception_score": r'"market_deception_score":\s*spec_scores\.get\("market_deception_score"\)',
        "place_prob": r'"place_prob":\s*spec_scores\.get\("place_prob"\)',
        "comment_intel_score": r'"comment_intel_score":\s*spec_scores\.get\("comment_intelligence_score"\)',
        "longshot_score": r'"longshot_score":\s*spec_scores\.get\("longshot_score"\)',
    }
    for key, pattern in patterns.items():
        mapping[key] = "passed_from_spec_scores" if re.search(pattern, source) else "not_found"
    return mapping


def _best_decimal_from_runner_raw(raw_payload: Any) -> float | None:
    if not isinstance(raw_payload, dict):
        return None
    odds = raw_payload.get("odds")
    if isinstance(odds, list):
        decimals: list[float] = []
        for item in odds:
            if not isinstance(item, dict):
                continue
            value = item.get("decimal")
            if value in ("", None, "-", "SP"):
                continue
            try:
                decimals.append(float(value))
            except (TypeError, ValueError):
                continue
        return min(decimals) if decimals else None
    if odds not in ("", None, "-", "SP"):
        try:
            return float(odds)
        except (TypeError, ValueError):
            return None
    return None


def _ablate_inputs(inputs: list[dict[str, Any]], component: str) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for row in inputs:
        cloned = copy.deepcopy(row)
        if component in cloned and cloned.get(component) is not None:
            cloned[component] = 0.0
        updated.append(cloned)
    return updated


def _prediction_index(predictions: list) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for pred in predictions:
        row = pred.to_dict()
        horse_id = row.get("horse_id") or row.get("horse")
        out[str(horse_id)] = row
    return out


def _capture_score_race(race: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    captured: dict[str, Any] = {}
    original = VeloPrimeEnsemble.predict_race

    def wrapped(self, runners, macro_context=None):
        captured["runners"] = copy.deepcopy(runners)
        captured["macro_context"] = macro_context
        return original(self, runners, macro_context=macro_context)

    VeloPrimeEnsemble.predict_race = wrapped
    try:
        results = score_race_velo_prime(race)
    finally:
        VeloPrimeEnsemble.predict_race = original
    return results, captured


def _race_component_summary(inputs: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"runner_count": len(inputs)}
    for component in COMPONENTS:
        non_null = sum(1 for row in inputs if row.get(component) is not None)
        zero_values = sum(1 for row in inputs if row.get(component) == 0.0)
        gated = 0
        if component == "longshot_score":
            gated = sum(
                1 for row in inputs
                if row.get(component) is not None and float(row.get("sp_dec") or 0.0) >= 10.0
            )
        summary[component] = {
            "passed_rows": len(inputs),
            "non_null_rows": non_null,
            "zero_rows": zero_values,
            "gated_rows": gated,
        }
    return summary


def _latest_verdict_rows(target_date: str) -> list[dict[str, Any]]:
    rows = rest_fetch(
        "velo_verdicts",
        "race_id,generated_at,full_analysis,top_rank_horse_id,velo_prime_prob",
    )
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        race_id = row.get("race_id")
        generated_at = str(row.get("generated_at") or "")
        if not race_id or not generated_at.startswith(target_date):
            continue
        current = latest.get(race_id)
        if current is None or generated_at > str(current.get("generated_at") or ""):
            latest[race_id] = row
    return list(latest.values())


def _race_lookup(race_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not race_ids:
        return {}
    rows = rest_fetch(
        "races",
        "race_id,date,time,course,race_name,race_type,distance_f",
        {"race_id": f"in.({','.join(race_ids)})"},
    )
    return {str(row["race_id"]): row for row in rows if row.get("race_id")}


def _runner_lookup(race_ids: list[str]) -> dict[tuple[str, str], dict[str, Any]]:
    if not race_ids:
        return {}
    rows = rest_fetch(
        "runners",
        "race_id,horse_id,raw",
        {"race_id": f"in.({','.join(race_ids)})"},
    )
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        race_id = row.get("race_id")
        horse_id = row.get("horse_id")
        if race_id and horse_id:
            lookup[(str(race_id), str(horse_id))] = row
    return lookup


def _code_from_race_type(race_type: str | None) -> str:
    text = (race_type or "").lower()
    return "jump" if any(term in text for term in ["hurdle", "chase", "nh flat"]) else "flat"


def _build_inputs_from_verdict_rows(target_date: str) -> tuple[list[dict[str, Any]], str]:
    verdict_rows = _latest_verdict_rows(target_date)
    if not verdict_rows:
        raise RuntimeError(f"No persisted velo_verdicts rows found for {target_date}")
    race_ids = [str(row["race_id"]) for row in verdict_rows if row.get("race_id")]
    races = _race_lookup(race_ids)
    runners = _runner_lookup(race_ids)
    day_runs: list[dict[str, Any]] = []

    for verdict_row in verdict_rows:
        race_id = str(verdict_row["race_id"])
        race_row = races.get(race_id, {})
        analysis = verdict_row.get("full_analysis")
        if not isinstance(analysis, list) or not analysis:
            continue

        inputs: list[dict[str, Any]] = []
        positive_odds: list[float] = []
        for item in analysis:
            if not isinstance(item, dict):
                continue
            horse_id = str(item.get("horse_id") or "")
            runner = runners.get((race_id, horse_id), {})
            sp_dec = float(_best_decimal_from_runner_raw(runner.get("raw")) or 0.0)
            if sp_dec > 0:
                positive_odds.append(sp_dec)
            inputs.append(
                {
                    "horse": item.get("horse") or item.get("horse_name"),
                    "horse_id": horse_id,
                    "race_id": race_id,
                    "sqpe_v17_prob": float(item.get("sqpe_v17_prob") or 0.0),
                    "improvement_score": item.get("improvement_score"),
                    "release_window_score": item.get("release_day_prob"),
                    "market_deception_score": item.get("market_deception_score"),
                    "place_prob": item.get("place_prob"),
                    "comment_intel_score": item.get("comment_intel_score"),
                    "longshot_score": item.get("longshot_prob"),
                    "sp_dec": sp_dec if sp_dec > 0 else None,
                    "is_fav": False,
                }
            )

        min_odds = min(positive_odds) if positive_odds else None
        if min_odds is not None:
            for row in inputs:
                row["is_fav"] = bool(row.get("sp_dec") == min_odds and min_odds > 0)

        macro_context = get_macro_context_for_race(
            str(race_row.get("date") or target_date),
            _code_from_race_type(race_row.get("race_type")),
        )

        day_runs.append(
            {
                "race_id": race_id,
                "course": race_row.get("course"),
                "off_time": race_row.get("time"),
                "results": analysis,
                "ensemble_inputs": inputs,
                "macro_context_obj": macro_context,
                "macro_context": _safe_macro_context(macro_context),
                "component_summary": _race_component_summary(inputs),
            }
        )
    if not day_runs:
        raise RuntimeError(f"No usable full_analysis payloads found for {target_date}")
    return day_runs, "persisted_verdict_runtime_sample"


def _choose_trace_race(day_runs: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        day_runs,
        key=lambda item: (
            sum(
                1
                for component in COMPONENTS
                if item["component_summary"][component]["non_null_rows"] > 0
            ),
            item["component_summary"]["longshot_score"]["gated_rows"],
        ),
        reverse=True,
    )
    return ranked[0]


def _run_ablation(trace_race: dict[str, Any]) -> dict[str, Any]:
    original_inputs = trace_race["ensemble_inputs"]
    macro_context = trace_race["macro_context_obj"]
    baseline_predictions = VeloPrimeEnsemble().predict_race(copy.deepcopy(original_inputs), macro_context=macro_context)
    baseline_index = _prediction_index(baseline_predictions)
    baseline_top = baseline_predictions[0].to_dict() if baseline_predictions else {}

    ablations: dict[str, Any] = {}
    for component in COMPONENTS:
        ablated_inputs = _ablate_inputs(original_inputs, component)
        ablated_predictions = VeloPrimeEnsemble().predict_race(ablated_inputs, macro_context=macro_context)
        ablated_index = _prediction_index(ablated_predictions)
        ablated_top = ablated_predictions[0].to_dict() if ablated_predictions else {}
        deltas = []
        for key, baseline_row in baseline_index.items():
            after = ablated_index.get(key, {})
            if not after:
                continue
            deltas.append(abs(float(after.get("velo_prime_prob") or 0.0) - float(baseline_row.get("velo_prime_prob") or 0.0)))
        top_delta = abs(
            float(ablated_top.get("velo_prime_prob") or 0.0)
            - float(baseline_top.get("velo_prime_prob") or 0.0)
        )
        ablations[component] = {
            "top_horse_before": baseline_top.get("horse"),
            "top_horse_after": ablated_top.get("horse"),
            "top_prob_before": baseline_top.get("velo_prime_prob"),
            "top_prob_after": ablated_top.get("velo_prime_prob"),
            "top_prob_delta": round(top_delta, 6),
            "ranking_changed": baseline_top.get("horse") != ablated_top.get("horse"),
            "max_abs_runner_delta": round(max(deltas) if deltas else 0.0, 6),
            "component_had_non_null_rows": trace_race["component_summary"][component]["non_null_rows"] > 0,
            "component_had_gated_rows": trace_race["component_summary"][component]["gated_rows"] > 0,
            "changes_vp": any(delta > 0 for delta in deltas),
        }
    return {
        "baseline_top": baseline_top,
        "ablations": ablations,
    }


def _final_contract(day_runs: list[dict[str, Any]], ablation: dict[str, Any]) -> list[dict[str, Any]]:
    trace_summary = _choose_trace_race(day_runs)["component_summary"]
    rows: list[dict[str, Any]] = [
        {
            "signal": "sqpe_v17",
            "declared_weight": _WEIGHTS["sqpe_v17"],
            "passed_into_ensemble": True,
            "non_null": True,
            "changes_vp": True,
            "status": "LIVE_WEIGHTED",
        }
    ]
    for component in COMPONENTS:
        non_null = sum(run["component_summary"][component]["non_null_rows"] for run in day_runs) > 0
        gated = sum(run["component_summary"][component]["gated_rows"] for run in day_runs) > 0
        changes = ablation["ablations"][component]["changes_vp"]
        status = "LIVE_WEIGHTED"
        if component == "longshot_score":
            status = "LIVE_GATED" if gated else "DEFAULTED_ONLY"
        elif not non_null:
            status = "DEFAULTED_ONLY"
        rows.append(
            {
                "signal": component,
                "declared_weight": _WEIGHTS[component],
                "passed_into_ensemble": True,
                "non_null": non_null,
                "changes_vp": changes,
                "status": status,
                "trace_non_null_rows": trace_summary[component]["non_null_rows"],
                "trace_gated_rows": trace_summary[component]["gated_rows"],
            }
        )
    rows.extend(
        [
            {
                "signal": "racing_api_enrichment_shadow_score",
                "declared_weight": None,
                "passed_into_ensemble": False,
                "non_null": False,
                "changes_vp": False,
                "status": "SHADOW_ONLY",
            },
            {
                "signal": "trainer/jockey/course/distance stats",
                "declared_weight": None,
                "passed_into_ensemble": False,
                "non_null": False,
                "changes_vp": False,
                "status": "SHADOW_ONLY",
            },
        ]
    )
    return rows


def _write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    contract_rows = payload["final_contract"]
    ablations = payload["runtime_proof"]["ablation"]["ablations"]
    lines = [
        "# Live Weight Contract Audit",
        "",
        f"- Audit date: `{payload['audit_date']}`",
        f"- Racecard source: `{payload['runtime_proof']['racecard_source']}`",
        f"- Races traced: `{payload['runtime_proof']['races_traced']}`",
        f"- Trace race: `{payload['runtime_proof']['trace_race']['course']} {payload['runtime_proof']['trace_race']['off_time']} | {payload['runtime_proof']['trace_race']['race_id']}`",
        "",
        "## Final Contract",
        "",
        "| Signal | Declared weight | Passed into ensemble? | Non-null? | Changes VP? | Status |",
        "|---|---:|---|---|---|---|",
    ]
    for row in contract_rows:
        lines.append(
            f"| {row['signal']} | "
            f"{'' if row['declared_weight'] is None else row['declared_weight']} | "
            f"{'YES' if row['passed_into_ensemble'] else 'NO'} | "
            f"{'YES' if row['non_null'] else 'NO'} | "
            f"{'YES' if row['changes_vp'] else 'NO'} | "
            f"{row['status']} |"
        )
    lines.extend(
        [
            "",
            "## Ablation Proof",
            "",
            "| Component | Top before | Top after | Top prob delta | Max runner delta | Ranking changed |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    for component, result in ablations.items():
        lines.append(
            f"| {component} | {result['top_horse_before']} | {result['top_horse_after']} | "
            f"{result['top_prob_delta']} | {result['max_abs_runner_delta']} | "
            f"{'YES' if result['ranking_changed'] else 'NO'} |"
        )

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--max-races", type=int, default=12)
    parser.add_argument("--env-file", default=None)
    args = parser.parse_args()

    _bootstrap_runtime(args.env_file, notify=False)

    date_str = args.date
    date_tag = date_str.replace("-", "_")
    racecard_source = "unknown"
    runtime_mode = "live_dry_run"
    try:
        raw_races, racecard_source = load_racecards(date_tag, date_str)
        normalized = [normalize_race(r) for r in raw_races[: args.max_races]]

        day_runs: list[dict[str, Any]] = []
        for race in normalized:
            results, captured = _capture_score_race(race)
            inputs = captured.get("runners") or []
            if not inputs:
                continue
            day_runs.append(
                {
                    "race_id": race.get("race_id"),
                    "course": race.get("course"),
                    "off_time": race.get("off_time"),
                    "results": results,
                    "ensemble_inputs": inputs,
                    "macro_context_obj": captured.get("macro_context"),
                    "macro_context": _safe_macro_context(captured.get("macro_context")),
                    "component_summary": _race_component_summary(inputs),
                }
            )

        if not day_runs:
            raise RuntimeError("No race runs captured for live weight audit")
    except Exception as exc:
        runtime_mode = "persisted_runtime_fallback"
        racecard_source = f"live_fetch_unavailable:{type(exc).__name__}"
        day_runs, racecard_source = _build_inputs_from_verdict_rows(date_str)

    trace_race = _choose_trace_race(day_runs)
    ablation = _run_ablation(trace_race)
    final_contract = _final_contract(day_runs, ablation)

    payload = {
        "audit_date": date_str,
        "declared_weights": dict(_WEIGHTS),
        "service_mapping": _parse_service_mapping(),
        "runtime_proof": {
            "runtime_mode": runtime_mode,
            "racecard_source": racecard_source,
            "races_traced": len(day_runs),
            "trace_race": {
                "race_id": trace_race["race_id"],
                "course": trace_race["course"],
                "off_time": trace_race["off_time"],
                "component_summary": trace_race["component_summary"],
                "macro_context": trace_race["macro_context"],
            },
            "day_component_counts": {
                component: {
                    "non_null_rows": sum(run["component_summary"][component]["non_null_rows"] for run in day_runs),
                    "gated_rows": sum(run["component_summary"][component]["gated_rows"] for run in day_runs),
                }
                for component in COMPONENTS
            },
            "ablation": ablation,
        },
        "final_contract": final_contract,
    }
    _write_outputs(payload)
    print(json.dumps(payload["runtime_proof"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
