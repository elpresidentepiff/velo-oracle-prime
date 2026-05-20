from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


PREFERRED_DATES = [
    "2026-05-06",
    "2026-05-05",
    "2026-05-04",
    "2026-05-03",
    "2026-05-02",
    "2026-05-01",
    "2026-05-07",
]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def available_verdict_dates() -> set[str]:
    dates = set()
    for path in DATA.glob("velo_prime_verdicts_*.json"):
        token = path.stem.replace("velo_prime_verdicts_", "")
        if len(token) == 10 and "-" in token:
            dates.add(token)
        else:
            dates.add(token.replace("_", "-"))
    return dates


def available_result_dates() -> set[str]:
    dates = set()
    for path in DATA.glob("results_*.json"):
        token = path.stem.replace("results_", "")
        dates.add(token.replace("_", "-"))
    return dates


def preferred_replay_dates(limit: int | None = None) -> tuple[list[str], list[str]]:
    verdicts = available_verdict_dates()
    results = available_result_dates()
    available = verdicts & results
    covered: list[str] = []
    missing: list[str] = []

    for date_str in PREFERRED_DATES:
        if date_str in available:
            covered.append(date_str)
        else:
            missing.append(date_str)

    extras = sorted(date for date in available if date not in covered)
    if limit is not None:
        remaining = max(0, limit - len(covered))
        covered.extend(extras[-remaining:])
    else:
        covered.extend(extras)
    return covered, missing


def run_script(script_name: str, date_str: str) -> None:
    script_path = ROOT / "scripts" / script_name
    subprocess.run([sys.executable, str(script_path), "--date", date_str], cwd=ROOT, check=True)


def normalize_regime_for_report(day_regime: str) -> str:
    mapping = {
        "ACCA_DAY_THIN": "ACCA_DAY_WEAK",
        "ACCA_DAY_PLAYABLE": "ACCA_DAY_MEDIUM",
    }
    return mapping.get(day_regime, day_regime)


def actual_regime_from_audit(fold_results: dict[str, Any]) -> str:
    statuses = {
        2: fold_results.get("strongest_2_fold", {}).get("status"),
        3: fold_results.get("strongest_3_fold", {}).get("status"),
        4: fold_results.get("strongest_4_fold", {}).get("status"),
        5: fold_results.get("controlled_5_fold", {}).get("status"),
        6: fold_results.get("speculative_6_fold", {}).get("status"),
    }
    if any(statuses[size] == "HIT" for size in (6, 5, 4)):
        return "ACCA_DAY_STRONG"
    if statuses[3] == "HIT":
        return "ACCA_DAY_MEDIUM"
    if statuses[2] == "HIT":
        return "ACCA_DAY_WEAK"
    return "NO_ACCA_DAY"


def recommended_calibration(day: dict[str, Any]) -> str:
    if day["winners_incorrectly_trapped"] > 0:
        return "Loosen trap calibration on high-VP / high-industry legs and review decoy thresholds."
    if day["trusted_leg_failures"] > 2:
        return "Tighten banker/glue thresholds and raise metadata or place-prob floor."
    if day["reported_day_regime"] == "NO_ACCA_DAY" and day["no_acca_day_correct"] is True:
        return "Keep suppression logic unchanged; day filter behaved correctly."
    if day["reported_day_regime"] == "ACCA_DAY_STRONG" and day["fold_hit_count"] >= 3:
        return "Keep strong-day regime but replay more dates before trusting 5/6-fold output."
    return "Collect more replay days before changing the detector."


def analyze_day(date_str: str) -> dict[str, Any]:
    run_script("acca_detector.py", date_str)
    run_script("acca_results_audit.py", date_str)

    lane = load_json(DATA / f"acca_lane_report_{date_str}.json", {})
    audit = load_json(DATA / f"acca_results_audit_{date_str}.json", {})

    fold_results = audit.get("fold_results", {})
    fold_summary = {
        2: fold_results.get("strongest_2_fold", {"generated": False, "status": "SUPPRESSED"}),
        3: fold_results.get("strongest_3_fold", {"generated": False, "status": "SUPPRESSED"}),
        4: fold_results.get("strongest_4_fold", {"generated": False, "status": "SUPPRESSED"}),
        5: fold_results.get("controlled_5_fold", {"generated": False, "status": "SUPPRESSED"}),
        6: fold_results.get("speculative_6_fold", {"generated": False, "status": "SUPPRESSED"}),
    }

    trap_outcomes = audit.get("trap_outcomes", [])
    candidate_outcomes = audit.get("candidate_outcomes", {})
    candidates = lane.get("candidates", [])
    trusted = [candidate for candidate in candidates if candidate.get("leg_role") in {"BANKER", "GLUE", "BOOSTER"}]

    winners_incorrectly_trapped = sum(1 for trap in trap_outcomes if trap.get("result") == "WIN")
    trusted_leg_failures = sum(1 for candidate in trusted if candidate_outcomes.get(candidate["horse"], {}).get("status") == "MISS")
    trap_count = len(trap_outcomes)
    fold_hit_count = sum(1 for result in fold_summary.values() if result.get("status") == "HIT")

    reported_day_regime = normalize_regime_for_report(lane.get("day_regime", "NO_ACCA_DAY"))
    actual_regime = actual_regime_from_audit(fold_results)

    return {
        "date": date_str,
        "candidates_scanned": lane.get("candidates_scanned", 0),
        "metadata_coverage": lane.get("source_summary", {}).get("metadata_coverage", 0.0),
        "cashrun_status": lane.get("cashrun_status"),
        "racing_api_enrichment_status": lane.get("racing_api_enrichment_status"),
        "reported_day_regime": reported_day_regime,
        "actual_regime": actual_regime,
        "regime_match": reported_day_regime == actual_regime,
        "folds": {
            "2_fold": {"generated": fold_summary[2].get("generated", False), "result": fold_summary[2].get("status")},
            "3_fold": {"generated": fold_summary[3].get("generated", False), "result": fold_summary[3].get("status")},
            "4_fold": {"generated": fold_summary[4].get("generated", False), "result": fold_summary[4].get("status")},
            "5_fold": {"generated": fold_summary[5].get("generated", False), "result": fold_summary[5].get("status")},
            "6_fold": {"generated": fold_summary[6].get("generated", False), "result": fold_summary[6].get("status")},
        },
        "trap_count": trap_count,
        "winners_incorrectly_trapped": winners_incorrectly_trapped,
        "losers_incorrectly_trusted": trusted_leg_failures,
        "trusted_leg_total": len(trusted),
        "fold_hit_count": fold_hit_count,
        "no_acca_day_correct": audit.get("no_acca_day_correct"),
        "naive_top_vp_2_fold_status": audit.get("naive_top_vp_2_fold_status"),
        "recommended_calibration_change": recommended_calibration({
            "winners_incorrectly_trapped": winners_incorrectly_trapped,
            "trusted_leg_failures": trusted_leg_failures,
            "reported_day_regime": reported_day_regime,
            "no_acca_day_correct": audit.get("no_acca_day_correct"),
            "fold_hit_count": fold_hit_count,
        }),
    }


def aggregate(days: list[dict[str, Any]], skipped: list[str]) -> dict[str, Any]:
    totals_generated = {2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    totals_hit = {2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    regime_matches = sum(1 for day in days if day["regime_match"])

    for day in days:
        for size in (2, 3, 4, 5, 6):
            fold = day["folds"][f"{size}_fold"]
            if fold["generated"]:
                totals_generated[size] += 1
                if fold["result"] == "HIT":
                    totals_hit[size] += 1

    trapped_total = sum(day["trap_count"] for day in days)
    trapped_winners = sum(day["winners_incorrectly_trapped"] for day in days)
    trusted_total = sum(day["trusted_leg_total"] for day in days)
    trusted_failures = sum(day["losers_incorrectly_trusted"] for day in days)

    cashrun_present_days = [day for day in days if day["cashrun_status"] == "PRESENT"]
    cashrun_missing_days = [day for day in days if day["cashrun_status"] != "PRESENT"]
    enrichment_used_days = [day for day in days if day["racing_api_enrichment_status"] == "USED"]

    return {
        "status": "SHADOW_OPERATOR_ONLY",
        "dates_replayed": [day["date"] for day in days],
        "dates_skipped": skipped,
        "days": days,
        "total_days_replayed": len(days),
        "regime_accuracy": round(regime_matches / len(days), 4) if days else 0.0,
        "fold_hit_rates": {
            str(size): {
                "generated": totals_generated[size],
                "hits": totals_hit[size],
                "hit_rate": round(totals_hit[size] / totals_generated[size], 4) if totals_generated[size] else None,
            }
            for size in (2, 3, 4, 5, 6)
        },
        "trap_false_positive_rate": round(trapped_winners / trapped_total, 4) if trapped_total else 0.0,
        "trusted_leg_failure_rate": round(trusted_failures / trusted_total, 4) if trusted_total else 0.0,
        "racing_api_enrichment_impact": {
            "days_used": len(enrichment_used_days),
            "days_missing": len(days) - len(enrichment_used_days),
            "note": "Coverage is visible in replay. Causal lift is not isolated without an enrichment-off ablation.",
        },
        "cashrun_missing_impact": {
            "days_present": len(cashrun_present_days),
            "days_missing": len(cashrun_missing_days),
            "note": "Replay records presence vs missing, but causal impact needs a CASHRUN on/off comparison.",
        },
        "calibration_recommendations": [
            "Replay more dates before trusting 5-fold or 6-fold output beyond shadow.",
            "Review trap logic on strong-VP winners incorrectly flagged as decoys.",
            "Run a Racing API enrichment on/off ablation before claiming structural lift.",
            "Run a CASHRUN on/off comparison once enough overlapping days exist.",
            "Require full metadata coverage before any 5-fold or 6-fold is generated.",
        ],
    }


def render_md(summary: dict[str, Any]) -> str:
    lines = [
        "ACCA REPLAY AUDIT - LATEST",
        "",
        f"Status: {summary['status']}",
        f"Total days replayed: {summary['total_days_replayed']}",
        f"Regime accuracy: {summary['regime_accuracy']}",
        f"Dates replayed: {', '.join(summary['dates_replayed'])}",
    ]
    if summary["dates_skipped"]:
        lines.append(f"Dates skipped: {', '.join(summary['dates_skipped'])}")
    lines.extend(["", "Fold hit rates:"])
    for size, stats in summary["fold_hit_rates"].items():
        lines.append(f"- {size}-fold: generated={stats['generated']} hits={stats['hits']} hit_rate={stats['hit_rate']}")
    lines.extend([
        "",
        f"Trap false-positive rate: {summary['trap_false_positive_rate']}",
        f"Trusted-leg failure rate: {summary['trusted_leg_failure_rate']}",
        "",
        "Per-day summary:",
    ])
    for day in summary["days"]:
        lines.append(
            f"- {day['date']} | scanned={day['candidates_scanned']} | metadata={day['metadata_coverage']} | cashrun={day['cashrun_status']} | enrichment={day['racing_api_enrichment_status']} | regime={day['reported_day_regime']} actual={day['actual_regime']} match={day['regime_match']} | traps={day['trap_count']} | trapped_winners={day['winners_incorrectly_trapped']} | trusted_failures={day['losers_incorrectly_trusted']}"
        )
        for size in (2, 3, 4, 5, 6):
            fold = day["folds"][f"{size}_fold"]
            lines.append(f"  - {size}-fold: generated={fold['generated']} result={fold['result']}")
        lines.append(f"  - calibration: {day['recommended_calibration_change']}")
    lines.extend(["", "Calibration recommendations:"])
    for item in summary["calibration_recommendations"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def save_summary(summary: dict[str, Any]) -> None:
    (DATA / "acca_replay_audit_latest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (DATA / "acca_replay_audit_latest.md").write_text(render_md(summary), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay ACCA_LANE_V1 across locally available closed-result days")
    parser.add_argument("--limit", type=int, default=20, help="Maximum replay dates to include")
    args = parser.parse_args()

    dates, missing = preferred_replay_dates(limit=args.limit)
    days = [analyze_day(date_str) for date_str in dates]
    summary = aggregate(days, missing)
    save_summary(summary)
    print(f"ACCA_REPLAY_AUDIT PASS days={summary['total_days_replayed']} regime_accuracy={summary['regime_accuracy']}")


if __name__ == "__main__":
    main()
