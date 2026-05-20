from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

import sys
sys.path.insert(0, str(ROOT))

from scripts.acca_detector import assign_leg_role, choose_best_fold, classify_day
from scripts.acca_results_audit import load_results_index, outcome_for_leg, fold_status


MODES = [
    "BASELINE_ACCA",
    "WITHOUT_RACING_API_ENRICHMENT",
    "WITHOUT_CASHRUN",
    "WITHOUT_TRAP_FILTER",
    "WITHOUT_VP30_CORE",
    "BANKER_ONLY",
    "BANKER_PLUS_GLUE_ONLY",
]

TRAP_PENALTY_MAP = {
    "HIGH_DECOY_RISK": 18.0,
    "DX_GOING_BLOCKER": 12.0,
    "DX_NO_SIGNAL": 15.0,
    "WEAK_MARGIN": 8.0,
    "INDUSTRY_CONFLICT": 6.0,
    "UNRESOLVED_METADATA": 12.0,
    "TIER_X": 10.0,
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def replay_dates() -> list[str]:
    latest = load_json(DATA / "acca_replay_audit_latest.json", {})
    if latest.get("dates_replayed"):
        return latest["dates_replayed"]
    fallback = [
        "2026-05-06",
        "2026-05-05",
        "2026-05-04",
        "2026-05-03",
        "2026-05-02",
        "2026-05-01",
        "2026-05-07",
    ]
    available = []
    for date_str in fallback:
        if (DATA / f"acca_lane_report_{date_str}.json").exists():
            available.append(date_str)
    return available


def actual_regime_from_fold_results(fold_results: dict[str, Any]) -> str:
    if fold_results.get("speculative_6_fold", {}).get("status") == "HIT":
        return "ACCA_DAY_STRONG"
    if fold_results.get("controlled_5_fold", {}).get("status") == "HIT":
        return "ACCA_DAY_STRONG"
    if fold_results.get("strongest_4_fold", {}).get("status") == "HIT":
        return "ACCA_DAY_STRONG"
    if fold_results.get("strongest_3_fold", {}).get("status") == "HIT":
        return "ACCA_DAY_MEDIUM"
    if fold_results.get("strongest_2_fold", {}).get("status") == "HIT":
        return "ACCA_DAY_WEAK"
    return "NO_ACCA_DAY"


def normalize_reported_regime(day_regime: str) -> str:
    return {
        "ACCA_DAY_THIN": "ACCA_DAY_WEAK",
        "ACCA_DAY_PLAYABLE": "ACCA_DAY_MEDIUM",
    }.get(day_regime, day_regime)


def rescore_candidate(candidate: dict[str, Any], mode: str) -> dict[str, Any]:
    row = copy.deepcopy(candidate)
    score = float(row.get("leg_score", 0.0))
    breakdown = row.get("score_breakdown", {})
    trap_flags = list(row.get("trap_flags", []))
    cashrun_class = row.get("cashrun_class")
    vp_for_role = float(row.get("vp", 0.0))

    if mode == "WITHOUT_RACING_API_ENRICHMENT":
        enrichment = row.get("racing_api_enrichment_score")
        if enrichment is not None:
            score -= min(2.0, float(enrichment) / 10.0)
        row["racing_api_enrichment_score"] = None

    elif mode == "WITHOUT_CASHRUN":
        score -= float(breakdown.get("cashrun_score", 0.0) or 0.0)
        row["cashrun_class"] = "MISSING_OPTIONAL"
        row["cashrun_score"] = None
        cashrun_class = "MISSING_OPTIONAL"

    elif mode == "WITHOUT_TRAP_FILTER":
        restored = sum(TRAP_PENALTY_MAP.get(flag, 0.0) for flag in trap_flags)
        score += restored
        trap_flags = []

    elif mode == "WITHOUT_VP30_CORE":
        score -= float(breakdown.get("vp_confidence_score", 0.0) or 0.0)
        vp_for_role = 0.0

    score = round(max(0.0, min(100.0, score)), 2)
    row["leg_score"] = score
    row["trap_flags"] = trap_flags
    row["leg_role"] = assign_leg_role(
        score,
        vp_for_role,
        float(row.get("place_prob", 0.0) or 0.0),
        trap_flags,
        row.get("source_completeness", "LOW_SOURCE"),
        int(row.get("industry_confirmation_count", 0) or 0),
        str(cashrun_class or ""),
    )
    return row


def apply_mode(candidates: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    transformed = [rescore_candidate(candidate, mode) for candidate in candidates]
    if mode == "BANKER_ONLY":
        transformed = [candidate for candidate in transformed if candidate.get("leg_role") == "BANKER"]
    elif mode == "BANKER_PLUS_GLUE_ONLY":
        transformed = [candidate for candidate in transformed if candidate.get("leg_role") in {"BANKER", "GLUE"}]
    transformed.sort(key=lambda row: (-float(row.get("leg_score", 0.0)), row.get("off_time", "")))
    return transformed


def folds_for_candidates(candidates: list[dict[str, Any]], day_regime: str) -> dict[str, Any]:
    return {
        "strongest_2_fold": choose_best_fold(candidates, 2, day_regime) or {"generated": False, "status": "SUPPRESSED"},
        "strongest_3_fold": choose_best_fold(candidates, 3, day_regime) or {"generated": False, "status": "SUPPRESSED"},
        "strongest_4_fold": choose_best_fold(candidates, 4, day_regime) or {"generated": False, "status": "SUPPRESSED"},
        "controlled_5_fold": choose_best_fold(candidates, 5, day_regime) or {"generated": False, "status": "SUPPRESSED"},
        "speculative_6_fold": choose_best_fold(candidates, 6, day_regime) or {"generated": False, "status": "SUPPRESSED"},
    }


def evaluate_mode_for_day(date_str: str, mode: str, baseline_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = apply_mode(baseline_candidates, mode)
    day_regime = normalize_reported_regime(classify_day(candidates))
    folds = folds_for_candidates(candidates, day_regime)

    results_index = load_results_index(date_str)
    candidate_outcomes = {candidate["horse"]: outcome_for_leg(candidate, results_index) for candidate in candidates}
    fold_results = {}
    for fold_name, fold in folds.items():
        if not fold.get("generated"):
            fold_results[fold_name] = {"generated": False, "status": "SUPPRESSED"}
            continue
        fold_results[fold_name] = {
            "generated": True,
            "status": fold_status(fold["legs"], candidate_outcomes),
        }

    trap_candidates = [candidate for candidate in candidates if candidate.get("leg_role") == "TRAP"]
    trusted = [candidate for candidate in candidates if candidate.get("leg_role") in {"BANKER", "GLUE", "BOOSTER"}]
    trapped_winners = sum(1 for candidate in trap_candidates if candidate_outcomes.get(candidate["horse"], {}).get("status") == "WIN")
    trusted_failures = sum(1 for candidate in trusted if candidate_outcomes.get(candidate["horse"], {}).get("status") == "MISS")

    return {
        "date": date_str,
        "mode": mode,
        "candidate_legs": len(candidates),
        "average_leg_vp": round(sum(float(candidate.get("vp", 0.0) or 0.0) for candidate in candidates) / len(candidates), 4) if candidates else 0.0,
        "average_enrichment_score": round(
            sum(float(candidate.get("racing_api_enrichment_score")) for candidate in candidates if candidate.get("racing_api_enrichment_score") is not None)
            / max(1, sum(1 for candidate in candidates if candidate.get("racing_api_enrichment_score") is not None)),
            4,
        ) if any(candidate.get("racing_api_enrichment_score") is not None for candidate in candidates) else None,
        "day_regime": day_regime,
        "actual_regime": actual_regime_from_fold_results(fold_results),
        "regime_match": day_regime == actual_regime_from_fold_results(fold_results),
        "folds": {
            "2": {"generated": fold_results["strongest_2_fold"].get("generated", False), "result": fold_results["strongest_2_fold"].get("status")},
            "3": {"generated": fold_results["strongest_3_fold"].get("generated", False), "result": fold_results["strongest_3_fold"].get("status")},
            "4": {"generated": fold_results["strongest_4_fold"].get("generated", False), "result": fold_results["strongest_4_fold"].get("status")},
            "5": {"generated": fold_results["controlled_5_fold"].get("generated", False), "result": fold_results["controlled_5_fold"].get("status")},
            "6": {"generated": fold_results["speculative_6_fold"].get("generated", False), "result": fold_results["speculative_6_fold"].get("status")},
        },
        "trap_false_positives": trapped_winners,
        "trap_total": len(trap_candidates),
        "trusted_leg_failures": trusted_failures,
        "trusted_leg_total": len(trusted),
    }


def aggregate_mode(days: list[dict[str, Any]]) -> dict[str, Any]:
    totals_generated = {size: 0 for size in ("2", "3", "4", "5", "6")}
    totals_hits = {size: 0 for size in ("2", "3", "4", "5", "6")}
    for day in days:
        for size in ("2", "3", "4", "5", "6"):
            fold = day["folds"][size]
            if fold["generated"]:
                totals_generated[size] += 1
                if fold["result"] == "HIT":
                    totals_hits[size] += 1

    trap_total = sum(day["trap_total"] for day in days)
    trap_fp = sum(day["trap_false_positives"] for day in days)
    trusted_total = sum(day["trusted_leg_total"] for day in days)
    trusted_fail = sum(day["trusted_leg_failures"] for day in days)
    avg_leg_vp = round(sum(day["average_leg_vp"] for day in days) / len(days), 4) if days else 0.0

    enrichment_values = [day["average_enrichment_score"] for day in days if day["average_enrichment_score"] is not None]
    avg_enrichment = round(sum(enrichment_values) / len(enrichment_values), 4) if enrichment_values else None

    return {
        "days_covered": len(days),
        "dates": [day["date"] for day in days],
        "candidate_legs": sum(day["candidate_legs"] for day in days),
        "folds_generated": {size: totals_generated[size] for size in ("2", "3", "4", "5", "6")},
        "fold_hit_rates": {
            size: {
                "generated": totals_generated[size],
                "hits": totals_hits[size],
                "hit_rate": round(totals_hits[size] / totals_generated[size], 4) if totals_generated[size] else None,
            }
            for size in ("2", "3", "4", "5", "6")
        },
        "day_regime_accuracy": round(sum(1 for day in days if day["regime_match"]) / len(days), 4) if days else 0.0,
        "trap_false_positives": trap_fp,
        "trap_false_positive_rate": round(trap_fp / trap_total, 4) if trap_total else 0.0,
        "trusted_leg_failures": trusted_fail,
        "trusted_leg_failure_rate": round(trusted_fail / trusted_total, 4) if trusted_total else 0.0,
        "average_leg_vp": avg_leg_vp,
        "average_enrichment_score": avg_enrichment,
        "per_day": days,
    }


def composite_score(summary: dict[str, Any]) -> float:
    fold_rates = [
        stats["hit_rate"]
        for size, stats in summary["fold_hit_rates"].items()
        if size in {"2", "3", "4"} and stats["hit_rate"] is not None
    ]
    fold_component = sum(fold_rates) / len(fold_rates) if fold_rates else 0.0
    return round(
        summary["day_regime_accuracy"] * 0.4
        + fold_component * 0.4
        + (1.0 - summary["trusted_leg_failure_rate"]) * 0.1
        + (1.0 - summary["trap_false_positive_rate"]) * 0.1,
        4,
    )


def compare_to_baseline(mode_summary: dict[str, Any], baseline_summary: dict[str, Any]) -> str:
    mode_score = composite_score(mode_summary)
    baseline_score = composite_score(baseline_summary)
    if mode_score > baseline_score + 0.02:
        return "IMPROVES_BASELINE"
    if mode_score < baseline_score - 0.02:
        return "WORSENS_BASELINE"
    return "MIXED_VS_BASELINE"


def build_ablation_report() -> dict[str, Any]:
    dates = replay_dates()
    baseline_reports = {
        date_str: load_json(DATA / f"acca_lane_report_{date_str}.json", {})
        for date_str in dates
    }
    baseline_candidates = {
        date_str: baseline_reports[date_str].get("candidates", [])
        for date_str in dates
        if baseline_reports[date_str]
    }

    mode_summaries: dict[str, Any] = {}
    for mode in MODES:
        days = [
            evaluate_mode_for_day(date_str, mode, baseline_candidates[date_str])
            for date_str in dates
            if baseline_candidates.get(date_str)
        ]
        mode_summaries[mode] = aggregate_mode(days)

    baseline_summary = mode_summaries["BASELINE_ACCA"]
    for mode, summary in mode_summaries.items():
        summary["baseline_comparison"] = compare_to_baseline(summary, baseline_summary)

    return {
        "status": "SHADOW_OPERATOR_ONLY",
        "dates": dates,
        "modes": mode_summaries,
    }


def render_md(report: dict[str, Any]) -> str:
    lines = [
        "ACCA ABLATION REPLAY - LATEST",
        "",
        f"Status: {report['status']}",
        f"Dates covered: {', '.join(report['dates'])}",
        "",
    ]
    for mode in MODES:
        summary = report["modes"][mode]
        lines.append(f"{mode}")
        lines.append(f"- days covered: {summary['days_covered']}")
        lines.append(f"- candidate legs: {summary['candidate_legs']}")
        lines.append(f"- folds generated: {summary['folds_generated']}")
        lines.append(f"- fold hit rates: {summary['fold_hit_rates']}")
        lines.append(f"- day regime accuracy: {summary['day_regime_accuracy']}")
        lines.append(f"- trap false positives: {summary['trap_false_positives']} ({summary['trap_false_positive_rate']})")
        lines.append(f"- trusted-leg failures: {summary['trusted_leg_failures']} ({summary['trusted_leg_failure_rate']})")
        lines.append(f"- average leg VP: {summary['average_leg_vp']}")
        lines.append(f"- average enrichment score: {summary['average_enrichment_score']}")
        lines.append(f"- baseline comparison: {summary['baseline_comparison']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def save_report(report: dict[str, Any]) -> None:
    (DATA / "acca_ablation_replay_latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (DATA / "acca_ablation_replay_latest.md").write_text(render_md(report), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ACCA_LANE_V1 ablation replay against existing replay artifacts")
    parser.parse_args()
    report = build_ablation_report()
    save_report(report)
    print("ACCA_ABLATION_REPLAY PASS")


if __name__ == "__main__":
    main()
