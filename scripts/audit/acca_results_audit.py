from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def normalize_name(value: Any) -> str:
    return str(value or "").upper().split("(")[0].strip()


def normalize_course(value: Any) -> str:
    return str(value or "").strip()


def normalize_time(value: Any) -> str:
    return str(value or "").strip().replace(".", ":")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_results_index(date_str: str) -> dict[tuple[str, str], dict[str, Any]]:
    path = DATA / f"results_{date_str.replace('-', '_')}.json"
    payload = load_json(path, {})
    if isinstance(payload, dict):
        races = payload.get("results", [])
    elif isinstance(payload, list):
        races = payload
    else:
        races = []
    return {(normalize_course(race.get("course")), normalize_time(race.get("off"))): race for race in races}


def status_from_position(position: str) -> str:
    if not position:
        return "MISSING_POSITION"
    if position in {"NR", "WD", "PU", "F", "UR", "RO", "REF"}:
        return "NR"
    try:
        value = int(position)
    except ValueError:
        return "NR"
    if value == 1:
        return "WIN"
    if value <= 3:
        return "PLACE"
    return "MISS"


def outcome_for_leg(leg: dict[str, Any], results_index: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    race = results_index.get((normalize_course(leg["course"]), normalize_time(leg["off_time"])))
    if not race:
        return {"status": "MISSING_RESULT", "position": None}
    horse_id = leg.get("horse_id")
    target_name = normalize_name(leg["horse"])
    for runner in race.get("runners", []):
        if horse_id and runner.get("horse_id") == horse_id:
            position = str(runner.get("position") or "").strip().upper()
            return {"status": status_from_position(position), "position": position}
        if normalize_name(runner.get("horse")) == target_name:
            position = str(runner.get("position") or "").strip().upper()
            return {"status": status_from_position(position), "position": position}
    return {"status": "MISSING_RUNNER", "position": None}


def fold_status(legs: list[dict[str, Any]], outcomes: dict[str, dict[str, Any]]) -> str:
    statuses = [outcomes[leg["horse"]]["status"] for leg in legs]
    if any(status.startswith("MISSING") for status in statuses):
        return "INCOMPLETE"
    if any(status == "NR" for status in statuses):
        return "INCOMPLETE"
    return "HIT" if all(status == "WIN" for status in statuses) else "MISS"


def audit(date_str: str) -> dict[str, Any]:
    report = load_json(DATA / f"acca_lane_report_{date_str}.json", {})
    if not report:
        raise SystemExit(f"Missing ACCA lane report for {date_str}")

    results_index = load_results_index(date_str)
    candidate_outcomes = {candidate["horse"]: outcome_for_leg(candidate, results_index) for candidate in report.get("candidates", [])}

    fold_results: dict[str, Any] = {}
    for name, fold in report.get("folds", {}).items():
        if not fold.get("generated"):
            fold_results[name] = {"generated": False, "status": "SUPPRESSED"}
            continue
        fold_results[name] = {
            "generated": True,
            "status": fold_status(fold["legs"], candidate_outcomes),
            "legs": [
                {
                    "horse": leg["horse"],
                    "course": leg["course"],
                    "off_time": leg["off_time"],
                    "result": candidate_outcomes.get(leg["horse"], {}).get("status", "UNKNOWN"),
                    "position": candidate_outcomes.get(leg["horse"], {}).get("position"),
                }
                for leg in fold["legs"]
            ],
        }

    trap_outcomes = [
        {
            "horse": trap["horse"],
            "course": trap["course"],
            "off_time": trap["off_time"],
            "trap_flags": trap["trap_flags"],
            "result": candidate_outcomes.get(trap["horse"], {}).get("status", "UNKNOWN"),
        }
        for trap in report.get("trap_legs", [])
    ]

    sorted_by_vp = sorted(report.get("candidates", []), key=lambda item: float(item.get("vp", 0.0)), reverse=True)
    naive_top_vp = sorted_by_vp[:2]
    naive_status = fold_status(naive_top_vp, candidate_outcomes) if len(naive_top_vp) == 2 else None

    safe_winners = sum(
        1
        for candidate in report.get("candidates", [])
        if candidate["leg_role"] in {"BANKER", "GLUE", "BOOSTER"} and candidate_outcomes.get(candidate["horse"], {}).get("status") == "WIN"
    )
    no_acca_day_correct = None
    if report.get("day_regime") == "NO_ACCA_DAY":
        no_acca_day_correct = safe_winners < 2

    return {
        "date": date_str,
        "status": "SHADOW_OPERATOR_ONLY",
        "lane": "ACCA_LANE_V1",
        "day_regime": report.get("day_regime"),
        "fold_results": fold_results,
        "candidate_outcomes": candidate_outcomes,
        "trap_outcomes": trap_outcomes,
        "no_acca_day_correct": no_acca_day_correct,
        "naive_top_vp_2_fold_status": naive_status,
    }


def render_md(audit_report: dict[str, Any]) -> str:
    lines = [
        f"ACCA RESULTS AUDIT - {audit_report['date']}",
        "",
        f"Status: {audit_report['status']}",
        f"Day regime: {audit_report['day_regime']}",
        "",
        "Fold results:",
    ]
    for name, result in audit_report["fold_results"].items():
        lines.append(f"- {name}: {result['status']}")
    lines.extend(["", "Trap outcomes:"])
    for trap in audit_report["trap_outcomes"][:12]:
        lines.append(f"- {trap['off_time']} {trap['course']} | {trap['horse']} | {trap['result']} | {', '.join(trap['trap_flags'])}")
    lines.extend([
        "",
        f"Naive top-VP 2-fold status: {audit_report['naive_top_vp_2_fold_status']}",
        f"NO_ACCA_DAY correctness: {audit_report['no_acca_day_correct']}",
    ])
    return "\n".join(lines) + "\n"


def save(audit_report: dict[str, Any]) -> None:
    base = DATA / f"acca_results_audit_{audit_report['date']}"
    base.with_suffix(".json").write_text(json.dumps(audit_report, indent=2), encoding="utf-8")
    base.with_suffix(".md").write_text(render_md(audit_report), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit ACCA_LANE_V1 output against closed results")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    audit_report = audit(args.date)
    save(audit_report)
    print(f"ACCA_RESULTS_AUDIT PASS {args.date}")


if __name__ == "__main__":
    main()
