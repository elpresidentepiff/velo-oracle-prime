"""Clean feature assembler for New Build VELO.

Feature rows are sandbox-only and exclude RPR/post-race leakage. Archive fields
can be represented as flags/counts, but banned raw fields are not emitted.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from new_build_velo.database import DATABASE_ROOT, REPORT_ROOT, _iter_jsonl, _write_jsonl
from new_build_velo.outcomes import OUTCOME_V2_PATH
from new_build_velo.spine import NEW_BUILD_ROOT, TRUST_POLICY, norm, stable_id, utc_now, write_json


FEATURE_ROOT = NEW_BUILD_ROOT / "features"
FEATURE_PATH = FEATURE_ROOT / "runner_features.jsonl"
BANNED_FEATURE_KEYS = {
    "rpr",
    "rpr_archive_only",
    "rp_rpr_archive_only",
    "official_rating_archive_only",
    "topspeed_archive_only",
    "sp",
    "sp_post_race_analysis_only",
    "won",
    "framed",
    "position",
    "finishing_position",
}
ALLOWED_RPR_POLICY_KEYS = {"rpr_policy", "rpr_feature_allowed"}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _index_context() -> dict[tuple[str | None, str | None], dict[str, Any]]:
    out: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    for row in _iter_jsonl(DATABASE_ROOT / "rp_context_flags.jsonl"):
        out[(row.get("source_date"), row.get("normalized_name"))] = row
    return out


def _index_outcomes() -> dict[tuple[str | None, str | None], dict[str, Any]]:
    out: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    path = OUTCOME_V2_PATH if OUTCOME_V2_PATH.exists() else DATABASE_ROOT / "outcome_bridge.jsonl"
    for row in _iter_jsonl(path):
        out[(row.get("race_date") or row.get("source_date"), row.get("normalized_name"))] = row
    return out


def _rpdc_memory() -> dict[str, dict[str, Any]]:
    aggregate: dict[str, dict[str, Any]] = defaultdict(lambda: {"seen": 0, "tag_count": 0, "release_score_total": 0.0, "cash_windows": 0})
    for row in _iter_jsonl(DATABASE_ROOT / "rpdc_memory.jsonl"):
        key = row.get("normalized_name") or norm(row.get("horse"))
        if not key:
            continue
        agg = aggregate[key]
        agg["seen"] += 1
        agg["tag_count"] += _to_int(row.get("rpdc_tag_count"))
        agg["release_score_total"] += _to_float(row.get("rpdc_release_score"))
        if row.get("rpdc_cash_window_flag"):
            agg["cash_windows"] += 1
    for key, agg in aggregate.items():
        seen = max(1, agg["seen"])
        agg["release_score_avg"] = agg["release_score_total"] / seen
    return aggregate


def _history_memory() -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    trainer: dict[str, dict[str, int]] = defaultdict(lambda: {"runs": 0, "wins": 0, "frames": 0})
    jockey: dict[str, dict[str, int]] = defaultdict(lambda: {"runs": 0, "wins": 0, "frames": 0})
    for row in _iter_jsonl(DATABASE_ROOT / "runner_results.jsonl"):
        for bucket, key in ((trainer, norm(row.get("trainer"))), (jockey, norm(row.get("jockey")))):
            if not key:
                continue
            bucket[key]["runs"] += 1
            if row.get("won"):
                bucket[key]["wins"] += 1
            if row.get("framed"):
                bucket[key]["frames"] += 1
    return trainer, jockey


def _feature_violation(row: dict[str, Any]) -> list[str]:
    bad: list[str] = []
    for key in row:
        lowered = key.lower()
        if lowered in ALLOWED_RPR_POLICY_KEYS:
            continue
        if lowered in BANNED_FEATURE_KEYS or "rpr" in lowered:
            bad.append(key)
    return bad


def build_features(*, execute: bool = False) -> dict[str, Any]:
    context = _index_context()
    outcomes = _index_outcomes()
    rpdc = _rpdc_memory()
    trainer_memory, jockey_memory = _history_memory()
    rows: list[dict[str, Any]] = []
    violations: list[str] = []
    coverage: Counter[str] = Counter()

    for runner in _iter_jsonl(DATABASE_ROOT / "runners.jsonl"):
        source_date = runner.get("source_date")
        name = runner.get("normalized_name")
        ctx = context.get((source_date, name), {})
        outcome = outcomes.get((source_date, name), {})
        trainer_key = norm(runner.get("trainer"))
        jockey_key = norm(runner.get("jockey"))
        trainer = trainer_memory.get(trainer_key, {"runs": 0, "wins": 0, "frames": 0})
        jockey = jockey_memory.get(jockey_key, {"runs": 0, "wins": 0, "frames": 0})
        rpdc_row = rpdc.get(name or "", {"seen": 0, "tag_count": 0, "release_score_avg": 0.0, "cash_windows": 0})
        archive_flags = ctx.get("archive_context_flags") or outcome.get("archive_context_flags") or []
        row = {
            "feature_row_id": stable_id(source_date, runner.get("race_id"), runner.get("racing_api_horse_id") or runner.get("horse")),
            "source": "new_build_feature_assembler",
            "source_date": source_date,
            "source_file": str(DATABASE_ROOT / "runners.jsonl"),
            "parser_version": "new_build_feature_assembler_v1",
            "parsed_at": utc_now(),
            "trust_policy": TRUST_POLICY,
            "live_velo_impact": False,
            "shadow_velo_impact": False,
            "rpr_policy": "RPR_ARCHIVE_ONLY",
            "new_build_velo_allowed": True,
            "rpr_feature_allowed": False,
            "race_id": runner.get("race_id"),
            "course_key": norm(runner.get("course")),
            "horse_key": name,
            "trainer_key": trainer_key,
            "jockey_key": jockey_key,
            "owner_key": norm(runner.get("owner")),
            "sire_key": norm(runner.get("sire")),
            "dam_key": norm(runner.get("dam")),
            "age": _to_int(runner.get("age")),
            "draw": _to_int(runner.get("draw")),
            "days_since_run": _to_int(runner.get("days_since_run")),
            "has_headgear": bool(runner.get("headgear")),
            "wind_surgery_flag": bool(runner.get("wind_surgery")),
            "archive_flag_count": len(archive_flags),
            "has_human_context": "HUMAN_CONTEXT_AVAILABLE" in archive_flags,
            "tip_heat_flag": "TIP_HEAT" in archive_flags or "MARKET_OVERHYPE_RISK" in archive_flags,
            "pedigree_context_flag": "PEDIGREE_CONTEXT_AVAILABLE" in archive_flags or "PEDIGREE_POSITIVE" in archive_flags,
            "trainer_runs": trainer["runs"],
            "trainer_win_rate": trainer["wins"] / trainer["runs"] if trainer["runs"] else 0.0,
            "trainer_frame_rate": trainer["frames"] / trainer["runs"] if trainer["runs"] else 0.0,
            "jockey_runs": jockey["runs"],
            "jockey_win_rate": jockey["wins"] / jockey["runs"] if jockey["runs"] else 0.0,
            "jockey_frame_rate": jockey["frames"] / jockey["runs"] if jockey["runs"] else 0.0,
            "rpdc_seen": rpdc_row["seen"],
            "rpdc_tag_count": rpdc_row["tag_count"],
            "rpdc_release_score_avg": rpdc_row["release_score_avg"],
            "rpdc_cash_window_count": rpdc_row["cash_windows"],
            "outcome_linked": outcome.get("classification") == "OUTCOME_CONFIRMED",
            "outcome_bridge_classification": outcome.get("classification"),
        }
        bad = _feature_violation(row)
        violations.extend(bad)
        for field, value in row.items():
            if value not in (None, "", 0, False):
                coverage[field] += 1
        rows.append(row)

    payload = {
        "generated_at": utc_now(),
        "classification": "NEW_BUILD_FEATURES_READY" if not violations else "NEW_BUILD_FEATURES_BLOCKED_BANNED_FIELDS",
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "feature_rows": len(rows),
        "banned_feature_violations": len(violations),
        "rpr_excluded": not violations,
        "outcome_linked_rows": sum(1 for row in rows if row.get("outcome_linked")),
        "coverage": dict(coverage),
        "live_velo_touched": False,
        "shadow_velo_touched": False,
    }
    if execute:
        _write_jsonl(FEATURE_PATH, rows)
        write_json(REPORT_ROOT / "feature_coverage_latest.json", payload)
        lines = [
            "# New Build Feature Coverage",
            "",
            f"- Feature rows: {len(rows)}",
            f"- Outcome-linked rows: {payload['outcome_linked_rows']}",
            f"- Banned/RPR violations: {len(violations)}",
            f"- RPR excluded: {payload['rpr_excluded']}",
            "",
            "No Live VELO, Shadow VELO, scoring, or model promotion touched.",
        ]
        (REPORT_ROOT / "feature_coverage_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build New Build VELO sandbox feature rows.")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(build_features(execute=args.execute), indent=2, ensure_ascii=False))
    return 0
