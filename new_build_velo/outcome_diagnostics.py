"""Outcome match diagnostics for New Build VELO.

Explains why archive rows do or do not link to result truth. This is a
diagnostic layer only; it never relaxes matching rules or mutates old VELO.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from typing import Any

from new_build_velo.database import DATABASE_ROOT, REPORT_ROOT, _iter_jsonl
from new_build_velo.outcomes import OUTCOME_V2_PATH
from new_build_velo.spine import TRUST_POLICY, norm, utc_now, write_json


def _date_range(values: list[str]) -> dict[str, str | None]:
    clean = sorted(v for v in values if v)
    return {"min": clean[0] if clean else None, "max": clean[-1] if clean else None}


def _time_key(value: Any) -> str:
    text = str(value or "")
    if "T" in text:
        text = text.split("T", 1)[1]
    return text[:5]


def _course_key(value: Any) -> str:
    return norm(str(value or "").replace("(USA)", ""))


def build_outcome_match_diagnostics(*, execute: bool = False) -> dict[str, Any]:
    bridge_rows = list(_iter_jsonl(OUTCOME_V2_PATH))
    result_rows = list(_iter_jsonl(DATABASE_ROOT / "runner_results.jsonl"))
    result_dates = sorted({str(row.get("source_date") or "") for row in result_rows if row.get("source_date")})
    bridge_dates = sorted({str(row.get("race_date") or row.get("source_date") or "") for row in bridge_rows})
    result_dates_set = set(result_dates)

    result_races_by_date_course: dict[tuple[str, str], set[str]] = defaultdict(set)
    result_names_by_date_course: dict[tuple[str, str], set[str]] = defaultdict(set)
    result_times_by_date_course: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in result_rows:
        date = str(row.get("source_date") or "")
        course = _course_key(row.get("course"))
        result_races_by_date_course[(date, course)].add(str(row.get("race_id") or ""))
        result_names_by_date_course[(date, course)].add(str(row.get("normalized_name") or ""))
        result_times_by_date_course[(date, course)].add(_time_key(row.get("off_time")))

    reasons: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    for row in bridge_rows:
        date = str(row.get("race_date") or row.get("source_date") or "")
        course = _course_key(row.get("course"))
        name = str(row.get("normalized_name") or "")
        if row.get("classification") == "OUTCOME_CONFIRMED":
            reasons["LINKED"] += 1
            continue
        if date not in result_dates_set:
            reason = "RESULT_DATE_MISSING"
        elif not result_races_by_date_course.get((date, course)):
            reason = "RESULT_COURSE_MISSING_FOR_DATE"
        elif name not in result_names_by_date_course.get((date, course), set()):
            reason = "HORSE_NAME_MISSING_IN_RESULT_COURSE"
        else:
            reason = "STRICT_KEYS_PRESENT_BUT_NO_MATCH"
        reasons[reason] += 1
        if len(samples) < 25:
            samples.append(
                {
                    "horse": row.get("rp_horse_name"),
                    "race_date": date,
                    "course": row.get("course"),
                    "off_time": row.get("off_time"),
                    "race_id": row.get("race_id"),
                    "failed_reason": reason,
                    "available_result_dates_nearby": [d for d in result_dates if abs(_date_to_int(d) - _date_to_int(date)) <= 2],
                    "result_times_same_course": sorted(result_times_by_date_course.get((date, course), set())),
                    "proposed_safe_next_step": _next_step(reason),
                }
            )

    payload = {
        "generated_at": utc_now(),
        "classification": "NEW_BUILD_OUTCOME_DIAGNOSTICS_READY",
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "bridge_rows": len(bridge_rows),
        "result_rows": len(result_rows),
        "bridge_date_range": _date_range(bridge_dates),
        "result_date_range": _date_range(result_dates),
        "bridge_dates": bridge_dates,
        "result_dates_count": len(result_dates),
        "reason_counts": dict(reasons),
        "sample_unmatched": samples,
        "primary_blocker": reasons.most_common(1)[0][0] if reasons else None,
        "recommended_next_step": _overall_next_step(reasons),
        "trust_policy": TRUST_POLICY,
        "rpr_policy": "RPR_ARCHIVE_ONLY",
        "banned_feature_violations": 0,
        "live_velo_touched": False,
        "shadow_velo_touched": False,
    }
    if execute:
        write_json(REPORT_ROOT / "outcome_match_diagnostics_latest.json", payload)
        lines = [
            "# New Build Outcome Match Diagnostics",
            "",
            f"- Bridge rows: {len(bridge_rows)}",
            f"- Result rows: {len(result_rows)}",
            f"- Bridge date range: {payload['bridge_date_range']['min']} to {payload['bridge_date_range']['max']}",
            f"- Result date range: {payload['result_date_range']['min']} to {payload['result_date_range']['max']}",
            f"- Primary blocker: {payload['primary_blocker']}",
            f"- Recommended next step: {payload['recommended_next_step']}",
            "",
            "## Reason Counts",
        ]
        for reason, count in reasons.most_common():
            lines.append(f"- {reason}: {count}")
        lines.extend(["", "## Sample Unmatched"])
        for sample in samples[:10]:
            lines.append(
                f"- {sample['race_date']} {sample['course']} {sample['off_time']} — "
                f"{sample['horse']} — {sample['failed_reason']} — {sample['proposed_safe_next_step']}"
            )
        lines.extend(["", "Live VELO untouched. Shadow VELO untouched. No match rules relaxed."])
        (REPORT_ROOT / "outcome_match_diagnostics_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def _date_to_int(value: str) -> int:
    try:
        return int(value.replace("-", ""))
    except Exception:
        return 0


def _next_step(reason: str) -> str:
    if reason == "RESULT_DATE_MISSING":
        return "capture/import Racing API or trusted result file for this date before bridge repair"
    if reason == "RESULT_COURSE_MISSING_FOR_DATE":
        return "verify course naming and result coverage for this date"
    if reason == "HORSE_NAME_MISSING_IN_RESULT_COURSE":
        return "inspect identity bridge aliases before any fuzzy match"
    return "inspect strict key mismatch manually"


def _overall_next_step(reasons: Counter[str]) -> str:
    if reasons.get("RESULT_DATE_MISSING", 0) >= max(1, sum(reasons.values()) * 0.8):
        return "IMPORT_RESULTS_FOR_RP_ARCHIVE_DATES"
    if reasons.get("RESULT_COURSE_MISSING_FOR_DATE"):
        return "AUDIT_COURSE_DATE_RESULT_COVERAGE"
    if reasons.get("HORSE_NAME_MISSING_IN_RESULT_COURSE"):
        return "IMPROVE_IDENTITY_ALIASES"
    return "MANUAL_OUTCOME_MATCH_REVIEW"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explain New Build VELO outcome bridge misses.")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(build_outcome_match_diagnostics(execute=args.execute), indent=2, ensure_ascii=False))
    return 0
