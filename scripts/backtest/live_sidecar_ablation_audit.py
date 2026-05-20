"""
Audit the live-weighted sidecars using persisted verdicts and matched results.

This is an audit-only script. It does not modify scoring logic or persist any
production verdict changes.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.intelligence.macro_regime.bha_macro_context import get_macro_context_for_race
from src.intelligence.velo_prime_ensemble import VeloPrimeEnsemble, _WEIGHTS
from src.velo.race_metadata_resolver import rest_fetch

OUTPUT_JSON = ROOT / "data" / "live_sidecar_ablation_audit_latest.json"
OUTPUT_MD = ROOT / "data" / "live_sidecar_ablation_audit_latest.md"

COMPONENTS = [
    "sqpe_v17",
    "improvement_score",
    "release_window_score",
    "market_deception_score",
    "place_prob",
    "comment_intel_score",
    "longshot_score",
]

LABELS = {
    "sqpe_v17": "SQPE baseline anchor",
    "improvement_score": "improvement_score",
    "release_window_score": "release_day_prob / release_window_score",
    "market_deception_score": "MDS",
    "place_prob": "place_prob",
    "comment_intel_score": "comment_intel_score",
    "longshot_score": "longshot_score",
}


def _code_from_race_type(race_type: str | None) -> str:
    text = (race_type or "").lower()
    return "jump" if any(term in text for term in ["hurdle", "chase", "nh flat"]) else "flat"


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _position_num(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _profit_from_sp(sp_dec: float | None, is_winner: bool) -> float | None:
    if sp_dec is None or sp_dec <= 0:
        return None
    return (sp_dec - 1.0) if is_winner else -1.0


def _p75(values: list[float]) -> float | None:
    cleaned = sorted(v for v in values if v is not None)
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return cleaned[0]
    idx = max(0, math.ceil(0.75 * len(cleaned)) - 1)
    return cleaned[idx]


def _fetch_latest_verdicts() -> list[dict[str, Any]]:
    rows = rest_fetch(
        "velo_verdicts",
        "race_id,generated_at,full_analysis,velo_prime_prob,top_rank_horse_id",
    )
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        race_id = row.get("race_id")
        generated_at = str(row.get("generated_at") or "")
        analysis = row.get("full_analysis")
        if not race_id or not isinstance(analysis, list) or not analysis:
            continue
        current = latest.get(str(race_id))
        if current is None or generated_at > str(current.get("generated_at") or ""):
            latest[str(race_id)] = row
    return list(latest.values())


def _fetch_races(race_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not race_ids:
        return {}
    rows = rest_fetch(
        "races",
        "race_id,date,time,course,race_type,distance_f",
        {"race_id": f"in.({','.join(race_ids)})"},
    )
    return {str(r["race_id"]): r for r in rows if r.get("race_id")}


def _fetch_runner_results(race_ids: list[str]) -> dict[tuple[str, str], dict[str, Any]]:
    if not race_ids:
        return {}
    rows = rest_fetch(
        "runner_results",
        "race_id,horse_id,position,sp_dec,is_winner",
        {"race_id": f"in.({','.join(race_ids)})"},
    )
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        race_id = row.get("race_id")
        horse_id = row.get("horse_id")
        if race_id and horse_id:
            lookup[(str(race_id), str(horse_id))] = row
    return lookup


def _build_race_inputs(verdict_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    race_ids = [str(v["race_id"]) for v in verdict_rows if v.get("race_id")]
    races = _fetch_races(race_ids)
    runner_results = _fetch_runner_results(race_ids)

    race_inputs: list[dict[str, Any]] = []
    for verdict in verdict_rows:
        race_id = str(verdict["race_id"])
        race_row = races.get(race_id)
        if not race_row:
            continue
        analysis = verdict["full_analysis"]
        runners: list[dict[str, Any]] = []
        matched_runner_count = 0
        min_sp = None
        for item in analysis:
            if not isinstance(item, dict):
                continue
            horse_id = str(item.get("horse_id") or "")
            result = runner_results.get((race_id, horse_id))
            sp_dec = _safe_float((result or {}).get("sp_dec"))
            if sp_dec is not None and sp_dec > 0:
                min_sp = sp_dec if min_sp is None else min(min_sp, sp_dec)
            if result:
                matched_runner_count += 1
            runners.append(
                {
                    "horse": item.get("horse") or item.get("horse_name"),
                    "horse_id": horse_id,
                    "race_id": race_id,
                    "sqpe_v17_prob": float(item.get("sqpe_v17_prob") or 0.0),
                    "improvement_score": _safe_float(item.get("improvement_score")),
                    "release_window_score": _safe_float(item.get("release_day_prob")),
                    "market_deception_score": _safe_float(item.get("market_deception_score")),
                    "place_prob": _safe_float(item.get("place_prob")),
                    "comment_intel_score": _safe_float(item.get("comment_intel_score")),
                    "longshot_score": _safe_float(item.get("longshot_prob")),
                    "sp_dec": sp_dec,
                    "position": _position_num((result or {}).get("position")),
                    "is_winner": bool((result or {}).get("is_winner")),
                }
            )
        if min_sp is not None:
            for runner in runners:
                runner["is_fav"] = bool(runner.get("sp_dec") == min_sp)
        else:
            for runner in runners:
                runner["is_fav"] = False
        if matched_runner_count == 0:
            continue
        macro_context = get_macro_context_for_race(
            str(race_row.get("date") or ""),
            _code_from_race_type(race_row.get("race_type")),
        )
        race_inputs.append(
            {
                "race_id": race_id,
                "course": race_row.get("course"),
                "time": race_row.get("time"),
                "date": race_row.get("date"),
                "runners": runners,
                "macro_context": macro_context,
            }
        )
    return race_inputs


def _pred_index(predictions: list, runners: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    horse_to_runner = {str(r.get("horse")): r for r in runners}
    out: dict[str, dict[str, Any]] = {}
    for pred in predictions:
        row = pred.to_dict()
        runner = horse_to_runner.get(str(row.get("horse")))
        if runner:
            row["horse_id"] = runner.get("horse_id")
            row["sp_dec"] = runner.get("sp_dec")
            row["position"] = runner.get("position")
            row["is_winner"] = runner.get("is_winner")
        out[str(row.get("horse_id") or row.get("horse"))] = row
    return out


def _ablate_runners(runners: list[dict[str, Any]], component: str) -> list[dict[str, Any]]:
    updated = []
    for row in runners:
        cloned = dict(row)
        if component == "sqpe_v17":
            cloned["sqpe_v17_prob"] = 0.0
        elif component in cloned and cloned.get(component) is not None:
            cloned[component] = 0.0
        updated.append(cloned)
    return updated


def _top_selection(predictions: list) -> dict[str, Any] | None:
    return predictions[0].to_dict() if predictions else None


def _classify_sidecar(
    sample_size: int,
    sr: float | None,
    frame: float | None,
    roi: float | None,
    base_sr: float,
    base_frame: float,
    avg_contribution: float,
) -> str:
    if sample_size < 20:
        return "LOW_SAMPLE"
    if roi is not None and roi > 0 and sr is not None and sr >= base_sr:
        return "HELPS_VALUE"
    if frame is not None and frame > base_frame and roi is not None and roi < 0:
        return "OVERBET_RISK"
    if sr is not None and sr >= base_sr and avg_contribution > 0:
        return "HELPS_PROBABILITY"
    if frame is not None and frame > base_frame:
        return "HELPS_FRAME"
    if roi is not None and roi < 0 and avg_contribution < 0:
        return "HARMFUL"
    return "HOLD"


def _action_for_classification(label: str) -> str:
    return {
        "HELPS_VALUE": "KEEP_LIVE",
        "HELPS_PROBABILITY": "KEEP_LIVE_BUT_MONITOR",
        "HELPS_FRAME": "KEEP_LIVE_BUT_MONITOR",
        "OVERBET_RISK": "BLOCK_CHANGE_PENDING_AUDIT",
        "HARMFUL": "BLOCK_CHANGE_PENDING_AUDIT",
        "LOW_SAMPLE": "KEEP_LIVE_BUT_MONITOR",
        "HOLD": "BLOCK_CHANGE_PENDING_AUDIT",
    }[label]


def run_audit() -> dict[str, Any]:
    verdicts = _fetch_latest_verdicts()
    races = _build_race_inputs(verdicts)
    ensemble = VeloPrimeEnsemble()

    baseline_matched = 0
    baseline_wins = 0
    baseline_places = 0
    baseline_profit = 0.0

    component_high_values: dict[str, list[float]] = defaultdict(list)
    top_rows_by_component: dict[str, list[dict[str, Any]]] = defaultdict(list)
    race_effects: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for race in races:
        baseline_predictions = ensemble.predict_race(race["runners"], macro_context=race["macro_context"])
        baseline_top = _top_selection(baseline_predictions)
        if not baseline_top:
            continue
        baseline_index = _pred_index(baseline_predictions, race["runners"])
        baseline_top = baseline_index.get(str(next(iter([k for k, v in baseline_index.items() if v.get("horse") == baseline_top.get("horse")]), baseline_top.get("horse"))), baseline_top)

        baseline_runner = next(
            (
                r for r in race["runners"]
                if str(r.get("horse_id") or "") == str(baseline_top.get("horse_id") or "")
                or str(r.get("horse") or "") == str(baseline_top.get("horse") or "")
            ),
            None,
        )
        if baseline_runner and baseline_runner.get("position") is not None:
            baseline_matched += 1
            baseline_wins += 1 if baseline_runner.get("is_winner") else 0
            baseline_places += 1 if (baseline_runner.get("position") or 99) in (1, 2, 3) else 0
            profit = _profit_from_sp(_safe_float(baseline_runner.get("sp_dec")), bool(baseline_runner.get("is_winner")))
            if profit is not None:
                baseline_profit += profit

        for component in COMPONENTS:
            value = None
            if component == "sqpe_v17":
                value = _safe_float(baseline_top.get("sqpe_v17_prob"))
            elif component == "release_window_score":
                value = _safe_float(baseline_top.get("release_window_score"))
                if value is None:
                    value = _safe_float(baseline_top.get("release_day_prob"))
            else:
                value = _safe_float(baseline_top.get(component))
            if value is not None:
                component_high_values[component].append(value)

            ablated_predictions = ensemble.predict_race(
                _ablate_runners(race["runners"], component),
                macro_context=race["macro_context"],
            )
            ablated_top = _top_selection(ablated_predictions)
            ablated_index = _pred_index(ablated_predictions, race["runners"])
            if not ablated_top:
                continue
            ablated_top = ablated_index.get(
                str(next(iter([k for k, v in ablated_index.items() if v.get("horse") == ablated_top.get("horse")]), ablated_top.get("horse"))),
                ablated_top,
            )
            base_prob = float(baseline_top.get("velo_prime_prob") or 0.0)
            after_prob = float(ablated_top.get("velo_prime_prob") or 0.0)
            same_horse_after = ablated_index.get(str(baseline_top.get("horse_id")))
            if same_horse_after is None:
                same_horse_after = next(
                    (v for v in ablated_index.values() if str(v.get("horse")) == str(baseline_top.get("horse"))),
                    None,
                )
            baseline_horse_after_prob = float((same_horse_after or {}).get("velo_prime_prob") or 0.0)
            race_effects[component].append(
                {
                    "race_id": race["race_id"],
                    "baseline_top_horse": baseline_top.get("horse"),
                    "ablated_top_horse": ablated_top.get("horse"),
                    "baseline_top_prob": base_prob,
                    "ablated_top_prob": after_prob,
                    "baseline_horse_after_prob": baseline_horse_after_prob,
                    "top_delta": base_prob - baseline_horse_after_prob,
                    "abs_top_delta": abs(base_prob - baseline_horse_after_prob),
                    "ranking_changed": baseline_top.get("horse_id") != ablated_top.get("horse_id"),
                    "vp30_membership_changed": (base_prob >= 0.30) != (baseline_horse_after_prob >= 0.30),
                }
            )

            top_rows_by_component[component].append(
                {
                    "race_id": race["race_id"],
                    "horse": baseline_top.get("horse"),
                    "horse_id": str(baseline_top.get("horse_id") or ""),
                    "component_value": value,
                    "sp_dec": baseline_runner.get("sp_dec") if baseline_runner else None,
                    "position": baseline_runner.get("position") if baseline_runner else None,
                    "is_winner": baseline_runner.get("is_winner") if baseline_runner else None,
                }
            )

    baseline_sr = (baseline_wins / baseline_matched) if baseline_matched else 0.0
    baseline_frame = (baseline_places / baseline_matched) if baseline_matched else 0.0
    baseline_roi = (baseline_profit / baseline_matched) if baseline_matched else 0.0

    sidecar_rows: list[dict[str, Any]] = []
    risk_register: list[dict[str, Any]] = []
    for component in COMPONENTS:
        effect_rows = race_effects[component]
        top_rows = top_rows_by_component[component]
        threshold = _p75(component_high_values[component])
        high_rows = [
            row for row in top_rows
            if row.get("component_value") is not None
            and threshold is not None
            and float(row["component_value"]) >= threshold
        ]
        matched_high = [row for row in high_rows if row.get("position") is not None]
        wins = sum(1 for row in matched_high if row.get("is_winner"))
        places = sum(1 for row in matched_high if (row.get("position") or 99) in (1, 2, 3))
        profits = [
            _profit_from_sp(_safe_float(row.get("sp_dec")), bool(row.get("is_winner")))
            for row in matched_high
        ]
        profits = [p for p in profits if p is not None]
        avg_sp_values = [_safe_float(row.get("sp_dec")) for row in matched_high]
        avg_sp_values = [v for v in avg_sp_values if v is not None]

        average_contribution = statistics.mean([row["top_delta"] for row in effect_rows]) if effect_rows else 0.0
        max_contribution = max([abs(row["top_delta"]) for row in effect_rows], default=0.0)
        gt_005 = sum(1 for row in effect_rows if row["abs_top_delta"] > 0.005)
        gt_01 = sum(1 for row in effect_rows if row["abs_top_delta"] > 0.01)
        top_sel_changes = sum(1 for row in effect_rows if row["ranking_changed"])
        vp30_changes = sum(1 for row in effect_rows if row["vp30_membership_changed"])

        sr = (wins / len(matched_high)) if matched_high else None
        frame = (places / len(matched_high)) if matched_high else None
        roi = (sum(profits) / len(matched_high)) if profits else None
        avg_sp = (sum(avg_sp_values) / len(avg_sp_values)) if avg_sp_values else None

        classification = _classify_sidecar(
            len(matched_high),
            sr,
            frame,
            roi,
            baseline_sr,
            baseline_frame,
            average_contribution,
        )
        action = _action_for_classification(classification)

        declared_weight = _WEIGHTS["sqpe_v17"] if component == "sqpe_v17" else _WEIGHTS[component]
        row = {
            "component": component,
            "label": LABELS[component],
            "declared_weight": declared_weight,
            "non_null_coverage": sum(1 for row in top_rows if row.get("component_value") is not None),
            "race_count": len(effect_rows),
            "average_contribution": round(average_contribution, 6),
            "max_contribution": round(max_contribution, 6),
            "changes_vp_gt_0_005": gt_005,
            "changes_vp_gt_0_01": gt_01,
            "changes_top_selection": top_sel_changes,
            "changes_vp30_membership": vp30_changes,
            "high_threshold": threshold,
            "high_sample_size": len(high_rows),
            "matched_high_sample_size": len(matched_high),
            "strike_rate_high": round(sr, 4) if sr is not None else None,
            "frame_rate_high": round(frame, 4) if frame is not None else None,
            "roi_high": round(roi, 4) if roi is not None else None,
            "average_sp_high": round(avg_sp, 4) if avg_sp is not None else None,
            "classification": classification,
            "action": action,
        }
        sidecar_rows.append(row)
        risk_register.append(
            {
                "sidecar": LABELS[component],
                "live_weight": declared_weight,
                "evidence_status": classification,
                "economic_status": "ROI_POSITIVE" if (roi is not None and roi > 0) else "ROI_NEGATIVE_OR_UNKNOWN",
                "action": action,
            }
        )

    helpful = sorted(
        [row for row in sidecar_rows if row["classification"] in ("HELPS_VALUE", "HELPS_PROBABILITY", "HELPS_FRAME")],
        key=lambda row: (row["classification"] == "HELPS_VALUE", row["average_contribution"]),
        reverse=True,
    )
    harmful = sorted(
        [row for row in sidecar_rows if row["classification"] in ("OVERBET_RISK", "HARMFUL")],
        key=lambda row: (row["classification"] == "HARMFUL", abs(row["average_contribution"]), -(row["roi_high"] or 0)),
        reverse=True,
    )

    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "sample": {
            "latest_race_verdicts": len(verdicts),
            "matched_races": len(races),
            "baseline_top_matched": baseline_matched,
            "baseline_sr": round(baseline_sr, 4),
            "baseline_frame": round(baseline_frame, 4),
            "baseline_roi": round(baseline_roi, 4),
        },
        "sidecars": sidecar_rows,
        "helpful": helpful[:5],
        "harmful": harmful[:5],
        "risk_register": risk_register,
    }


def write_outputs(payload: dict[str, Any]) -> None:
    def fmt_num(value: Any) -> str:
        return "" if value is None else f"{float(value):.4f}"

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Live Sidecar Ablation Audit",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Latest verdicts: `{payload['sample']['latest_race_verdicts']}`",
        f"- Matched races: `{payload['sample']['matched_races']}`",
        f"- Baseline matched top selections: `{payload['sample']['baseline_top_matched']}`",
        f"- Baseline SR / Frame / ROI: `{payload['sample']['baseline_sr']:.4f} / {payload['sample']['baseline_frame']:.4f} / {payload['sample']['baseline_roi']:.4f}`",
        "",
        "| Component | Weight | Non-null | Avg contrib | Max contrib | VP>0.005 | VP>0.01 | Top changes | VP30 changes | High n | Matched high n | SR high | Frame high | ROI high | Avg SP high | Classification | Action |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in payload["sidecars"]:
        lines.append(
            f"| {row['label']} | {row['declared_weight']:.2f} | {row['non_null_coverage']} | "
            f"{row['average_contribution']:.4f} | {row['max_contribution']:.4f} | "
            f"{row['changes_vp_gt_0_005']} | {row['changes_vp_gt_0_01']} | {row['changes_top_selection']} | "
            f"{row['changes_vp30_membership']} | {row['high_sample_size']} | {row['matched_high_sample_size']} | "
            f"{fmt_num(row['strike_rate_high'])} | "
            f"{fmt_num(row['frame_rate_high'])} | "
            f"{fmt_num(row['roi_high'])} | "
            f"{fmt_num(row['average_sp_high'])} | "
            f"{row['classification']} | {row['action']} |"
        )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = run_audit()
    write_outputs(payload)
    print(json.dumps(payload["sample"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
