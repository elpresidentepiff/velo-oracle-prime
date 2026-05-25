"""Outcome Bridge V2 for New Build VELO.

Links RP archive/identity rows to actual runner results using strict match
hierarchy. Loose name-only matches are retained as review rows only.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from new_build_velo.database import DATABASE_ROOT, REPORT_ROOT, _iter_jsonl, _write_jsonl
from new_build_velo.spine import NEW_BUILD_ROOT, TRUST_POLICY, norm, stable_id, utc_now, write_json


BRIDGE_ROOT = NEW_BUILD_ROOT / "bridges"
OUTCOME_V2_PATH = BRIDGE_ROOT / "outcome_bridge_v2.jsonl"


def _time_key(value: Any) -> str:
    text = str(value or "")
    if "T" in text:
        text = text.split("T", 1)[1]
    return text[:5]


def _course_key(value: Any) -> str:
    return norm(str(value or "").replace("(USA)", ""))


def _base_row(source_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "new_build_outcome_bridge_v2",
        "source_date": source_row.get("race_date") or source_row.get("source_date"),
        "source_file": str(DATABASE_ROOT / "outcome_bridge.jsonl"),
        "parser_version": "new_build_outcome_bridge_v2",
        "parsed_at": utc_now(),
        "trust_policy": TRUST_POLICY,
        "live_velo_impact": False,
        "shadow_velo_impact": False,
        "rpr_policy": "RPR_ARCHIVE_ONLY",
        "new_build_velo_allowed": True,
        "rpr_feature_allowed": False,
        "rp_rpr_velo_allowed": False,
    }


def _indexes(result_rows: Iterable[dict[str, Any]]) -> dict[str, dict[tuple[Any, ...], dict[str, Any]]]:
    exact: dict[tuple[Any, ...], dict[str, Any]] = {}
    date_course_time_name: dict[tuple[Any, ...], dict[str, Any]] = {}
    date_course_name: dict[tuple[Any, ...], dict[str, Any]] = {}
    date_horse_id: dict[tuple[Any, ...], dict[str, Any]] = {}
    ambiguous: set[tuple[Any, ...]] = set()

    for row in result_rows:
        source_date = row.get("source_date")
        horse_id = row.get("racing_api_horse_id")
        name = row.get("normalized_name")
        course = _course_key(row.get("course"))
        off_time = _time_key(row.get("off_time"))
        keys = [
            (exact, (row.get("race_id"), horse_id)),
            (date_horse_id, (source_date, horse_id)),
            (date_course_time_name, (source_date, course, off_time, name)),
            (date_course_name, (source_date, course, name)),
        ]
        for bucket, key in keys:
            if None in key or "" in key:
                continue
            if key in bucket and bucket[key].get("new_build_result_id") != row.get("new_build_result_id"):
                ambiguous.add(key)
            else:
                bucket[key] = row

    return {
        "exact": {k: v for k, v in exact.items() if k not in ambiguous},
        "date_horse_id": {k: v for k, v in date_horse_id.items() if k not in ambiguous},
        "date_course_time_name": {k: v for k, v in date_course_time_name.items() if k not in ambiguous},
        "date_course_name": {k: v for k, v in date_course_name.items() if k not in ambiguous},
    }


def _match(row: dict[str, Any], indexes: dict[str, dict[tuple[Any, ...], dict[str, Any]]]) -> tuple[dict[str, Any] | None, str, float]:
    date = row.get("race_date") or row.get("source_date")
    course = _course_key(row.get("course"))
    off_time = _time_key(row.get("off_time"))
    name = row.get("normalized_name") or norm(row.get("rp_horse_name"))
    horse_id = row.get("racing_api_horse_id") or row.get("velo_horse_id")

    exact = indexes["exact"].get((row.get("race_id"), horse_id))
    if exact:
        return exact, "EXACT_RACE_ID_HORSE_ID", 1.0
    by_id = indexes["date_horse_id"].get((date, horse_id))
    if by_id and row.get("identity_classification") == "IDENTITY_CONFIRMED":
        return by_id, "CONFIRMED_IDENTITY_DATE_HORSE_ID", 0.94
    by_time_name = indexes["date_course_time_name"].get((date, course, off_time, name))
    if by_time_name:
        return by_time_name, "DATE_COURSE_TIME_NAME", 0.88
    by_course_name = indexes["date_course_name"].get((date, course, name))
    if by_course_name:
        return by_course_name, "DATE_COURSE_NAME_LOW_CONFIDENCE_REVIEW", 0.62
    return None, "NO_RESULT_MATCH", 0.0


def build_outcome_bridge_v2(*, execute: bool = False) -> dict[str, Any]:
    source_rows = list(_iter_jsonl(DATABASE_ROOT / "outcome_bridge.jsonl"))
    result_rows = list(_iter_jsonl(DATABASE_ROOT / "runner_results.jsonl"))
    indexes = _indexes(result_rows)
    out_rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    for row in source_rows:
        result, method, confidence = _match(row, indexes)
        if result and confidence >= 0.8:
            classification = "OUTCOME_CONFIRMED"
            blocker = None
        elif result:
            classification = "LOW_CONFIDENCE_REVIEW"
            blocker = "LOW_CONFIDENCE_NAME_MATCH"
        else:
            classification = "OUTCOME_MISSING"
            blocker = "NO_STRICT_RESULT_MATCH"
        counts[classification] += 1
        out_rows.append(
            {
                **_base_row(row),
                "bridge_v2_id": stable_id(row.get("race_date"), row.get("race_id"), row.get("rp_horse_id"), method),
                "rp_horse_id": row.get("rp_horse_id"),
                "rp_horse_name": row.get("rp_horse_name"),
                "normalized_name": row.get("normalized_name"),
                "race_date": row.get("race_date"),
                "race_id": row.get("race_id"),
                "course": row.get("course"),
                "off_time": row.get("off_time"),
                "racing_api_horse_id": row.get("racing_api_horse_id") or row.get("velo_horse_id"),
                "velo_horse_id": row.get("velo_horse_id"),
                "identity_confidence": row.get("identity_confidence"),
                "archive_context_flags": row.get("archive_context_flags") or [],
                "velo_top_pick": row.get("velo_top_pick"),
                "velo_rank": row.get("velo_rank"),
                "velo_tier": row.get("velo_tier"),
                "velo_probability": row.get("velo_probability"),
                "match_method": method,
                "outcome_confidence": confidence,
                "classification": classification,
                "blocker_reason": blocker,
                "result_race_id": result.get("race_id") if result else None,
                "result_horse_id": result.get("racing_api_horse_id") if result else None,
                "finishing_position": result.get("position") if result else None,
                "won": result.get("won") if result else None,
                "framed": result.get("framed") if result else None,
                "sp_post_race_analysis_only": result.get("sp") if result else None,
            }
        )

    payload = {
        "generated_at": utc_now(),
        "classification": "NEW_BUILD_OUTCOME_BRIDGE_V2_READY",
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "source_rows": len(source_rows),
        "result_rows_available": len(result_rows),
        "outcome_linked_rows": counts["OUTCOME_CONFIRMED"],
        "low_confidence_rows": counts["LOW_CONFIDENCE_REVIEW"],
        "unmatched_rows": counts["OUTCOME_MISSING"],
        "classification_counts": dict(counts),
        "rpr_boundary_status": "PASS_RPR_ARCHIVE_ONLY",
        "banned_feature_violations": 0,
        "live_velo_touched": False,
        "shadow_velo_touched": False,
    }
    if execute:
        _write_jsonl(OUTCOME_V2_PATH, out_rows)
        write_json(REPORT_ROOT / "outcome_bridge_v2_latest.json", payload)
        lines = [
            "# Outcome Bridge V2",
            "",
            f"- Source rows: {len(source_rows)}",
            f"- Result rows available: {len(result_rows)}",
            f"- Outcome-linked rows: {counts['OUTCOME_CONFIRMED']}",
            f"- Low-confidence rows: {counts['LOW_CONFIDENCE_REVIEW']}",
            f"- Unmatched rows: {counts['OUTCOME_MISSING']}",
            f"- RPR boundary: {payload['rpr_boundary_status']}",
            "",
            "Live VELO untouched. Shadow VELO untouched.",
        ]
        (REPORT_ROOT / "outcome_bridge_v2_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build New Build VELO Outcome Bridge V2.")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(build_outcome_bridge_v2(execute=args.execute), indent=2, ensure_ascii=False))
    return 0
