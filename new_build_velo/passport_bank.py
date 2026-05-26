"""Passport Bank coverage and feature bridge for New Build VELO.

This module stays inside the New Build lane. It reads Racing Post archive
artifacts and writes only under data/new_build/. It does not train models,
touch Live VELO, touch Shadow VELO, or allow RPR into model-ready features.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from new_build_velo.spine import NEW_BUILD_ROOT, PARSED_ROOT, TRUST_POLICY, norm, utc_now


ROOT = Path(__file__).resolve().parents[1]
PASSPORT_PATH = NEW_BUILD_ROOT / "passports" / "horse_passports_v1.jsonl"
QUEUE_LATEST_PATH = NEW_BUILD_ROOT / "rp_scrape_queue" / "passport_queue_latest.jsonl"
PHASE2_QUEUE_PATH = NEW_BUILD_ROOT / "rp_scrape_queue" / "passport_queue_phase2_latest.jsonl"
COVERAGE_JSON_PATH = NEW_BUILD_ROOT / "reports" / "passport_coverage_map_latest.json"
COVERAGE_MD_PATH = NEW_BUILD_ROOT / "reports" / "passport_coverage_map_latest.md"
FEATURE_PARQUET_PATH = NEW_BUILD_ROOT / "features" / "rp_profile_passport_features_latest.parquet"
FEATURE_REPORT_PATH = NEW_BUILD_ROOT / "reports" / "rp_profile_passport_feature_matrix_latest.md"
FEATURE_JSON_PATH = NEW_BUILD_ROOT / "reports" / "rp_profile_passport_feature_matrix_latest.json"
HISTORICAL_PASSPORT_FEATURES = NEW_BUILD_ROOT / "training" / "passport_features.parquet"

RPR_POLICY = "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO"
PROFILE_FEATURE_SOURCE = "rp_profile_passport_bank_v1"

PASSPORT_FEATURE_COLS = [
    "pp_career_runs",
    "pp_win_rate",
    "pp_place_rate",
    "pp_days_since_last",
    "pp_layoff",
    "pp_avg_sp_last5",
    "pp_jockey_continuity",
    "pp_course_seen",
    "pp_or_change_3",
    "pp_class_moved_up",
    "pp_class_moved_down",
]

RPR_POLICY_KEYS = {"rpr_policy", "rp_rpr_velo_allowed", "rpr_feature_allowed"}
DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    _assert_new_build_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    _assert_new_build_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def _assert_new_build_path(path: Path) -> None:
    resolved = path.resolve()
    allowed = NEW_BUILD_ROOT.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"New Build writes are restricted to {allowed}: {resolved}")


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _uid(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _date_from_text(value: str | None) -> str | None:
    if not value:
        return None
    match = DATE_RE.search(str(value))
    return match.group(0) if match else None


def _racecard_source(capture_date: str, path: Path) -> str:
    text = f"{capture_date} {path.as_posix()}".lower()
    if "big-race-entries" in text:
        return "big_race_entries"
    date_value = _date_from_text(capture_date) or _date_from_text(path.as_posix())
    if date_value and date_value >= "2026-05-26":
        return "upcoming_racecard"
    return "current_racecard"


def _passport_key(row: dict[str, Any]) -> str:
    uid = row.get("horse_rp_uid")
    if uid not in (None, ""):
        return str(uid)
    return f"name:{norm(row.get('horse_name'))}"


def load_passports() -> tuple[list[dict[str, Any]], set[str], int]:
    rows = _read_jsonl(PASSPORT_PATH)
    seen: set[str] = set()
    duplicates = 0
    for row in rows:
        key = _passport_key(row)
        if key in seen:
            duplicates += 1
        seen.add(key)
    ids = {str(row.get("horse_rp_uid")) for row in rows if row.get("horse_rp_uid") not in (None, "")}
    return rows, ids, duplicates


def load_latest_queue() -> dict[str, dict[str, Any]]:
    rows = _read_jsonl(QUEUE_LATEST_PATH)
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        uid = _uid(row.get("rp_uid"))
        if uid:
            out[uid] = row
    return out


def collect_racecard_horses() -> dict[str, dict[str, Any]]:
    horses: dict[str, dict[str, Any]] = {}
    for path in sorted(PARSED_ROOT.glob("*/racecard_injection.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        capture_date = data.get("capture_date") or path.parent.name
        source = _racecard_source(capture_date, path)
        source_date = _date_from_text(capture_date) or capture_date
        for race in data.get("races", []):
            course = race.get("course")
            race_time = race.get("race_time")
            race_source_date = _date_from_text(race_time) or source_date
            race_title = race.get("race_title")
            for runner in race.get("runners", []):
                uid = _uid(runner.get("horse_id"))
                name = runner.get("horse")
                key = uid or f"name:{norm(name)}"
                row = horses.setdefault(
                    key,
                    {
                        "rp_uid": uid,
                        "name": name,
                        "normalized_name": norm(name),
                        "profile_url": runner.get("horse_url"),
                        "trainer": runner.get("trainer"),
                        "sources": set(),
                        "source_dates": set(),
                        "courses": set(),
                        "race_refs": [],
                    },
                )
                row["rp_uid"] = row.get("rp_uid") or uid
                row["name"] = row.get("name") or name
                row["profile_url"] = row.get("profile_url") or runner.get("horse_url")
                row["trainer"] = row.get("trainer") or runner.get("trainer")
                row["sources"].add(source)
                row["source_dates"].add(race_source_date)
                if course:
                    row["courses"].add(course)
                row["race_refs"].append(
                    {
                        "source": source,
                        "source_date": race_source_date,
                        "course": course,
                        "race_time": race_time,
                        "race_title": race_title,
                        "source_file": str(path),
                    }
                )
    return horses


def _public_horse_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["sources"] = sorted(out.get("sources", []))
    out["source_dates"] = sorted(out.get("source_dates", []))
    out["courses"] = sorted(out.get("courses", []))
    return out


def _rpr_violations(rows: Iterable[dict[str, Any]]) -> list[str]:
    bad: list[str] = []
    for row in rows:
        for key in row:
            lowered = key.lower()
            if lowered in RPR_POLICY_KEYS:
                continue
            if "rpr" in lowered:
                bad.append(key)
    return sorted(set(bad))


def _trainer_coverage(racecard_horses: dict[str, dict[str, Any]], passport_ids: set[str]) -> list[dict[str, Any]]:
    by_trainer: dict[str, dict[str, Any]] = defaultdict(lambda: {"active_horses": 0, "passport_horses": 0, "missing_horses": 0})
    for horse in racecard_horses.values():
        trainer = horse.get("trainer") or "UNKNOWN"
        bucket = by_trainer[trainer]
        bucket["active_horses"] += 1
        if horse.get("rp_uid") in passport_ids:
            bucket["passport_horses"] += 1
        else:
            bucket["missing_horses"] += 1
    rows = []
    for trainer, stats in by_trainer.items():
        active = stats["active_horses"]
        rows.append(
            {
                "trainer": trainer,
                **stats,
                "coverage_pct": round(stats["passport_horses"] / active * 100, 2) if active else 0.0,
            }
        )
    return sorted(rows, key=lambda r: (-r["active_horses"], r["trainer"]))[:50]


def _course_date_coverage(racecard_horses: dict[str, dict[str, Any]], passport_ids: set[str]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(lambda: {"runners": 0, "passport_runners": 0, "missing_runners": 0})
    seen: set[tuple[str, str, str, str]] = set()
    for horse in racecard_horses.values():
        uid = horse.get("rp_uid") or horse.get("normalized_name")
        for ref in horse.get("race_refs", []):
            key = (ref.get("source_date") or "", ref.get("course") or "UNKNOWN", ref.get("source") or "")
            seen_key = (*key, uid or "")
            if seen_key in seen:
                continue
            seen.add(seen_key)
            bucket = buckets[key]
            bucket["runners"] += 1
            if horse.get("rp_uid") in passport_ids:
                bucket["passport_runners"] += 1
            else:
                bucket["missing_runners"] += 1
    rows = []
    for (source_date, course, source), stats in buckets.items():
        runners = stats["runners"]
        rows.append(
            {
                "source_date": source_date,
                "course": course,
                "source": source,
                **stats,
                "coverage_pct": round(stats["passport_runners"] / runners * 100, 2) if runners else 0.0,
            }
        )
    return sorted(rows, key=lambda r: (str(r["source_date"]), str(r["course"]), str(r["source"])))


def build_coverage_map(*, execute: bool = False) -> dict[str, Any]:
    passports, passport_ids, duplicate_count = load_passports()
    racecard_horses = collect_racecard_horses()
    queue = load_latest_queue()
    passport_rows_with_rpr = _rpr_violations(passports)
    active_rows = list(racecard_horses.values())
    active_with_passport = [row for row in active_rows if row.get("rp_uid") in passport_ids]
    missing_active = [row for row in active_rows if row.get("rp_uid") not in passport_ids]
    upcoming = [row for row in active_rows if "upcoming_racecard" in row.get("sources", set())]
    upcoming_with_passport = [row for row in upcoming if row.get("rp_uid") in passport_ids]
    big_entries = [row for row in active_rows if "big_race_entries" in row.get("sources", set())]
    big_entries_with_passport = [row for row in big_entries if row.get("rp_uid") in passport_ids]
    no_form_rows = []
    for horse in missing_active:
        uid = horse.get("rp_uid")
        qrow = queue.get(uid or "")
        if qrow and qrow.get("status") == "CAPTURED_NEEDS_FORM_HISTORY_OR_NO_RUNS":
            no_form_rows.append(horse)
    missing_high_priority = sorted(
        (_public_horse_row(row) for row in missing_active),
        key=lambda row: (
            0 if "upcoming_racecard" in row.get("sources", []) else 1,
            0 if "big_race_entries" in row.get("sources", []) else 1,
            str(row.get("trainer") or ""),
            str(row.get("name") or ""),
        ),
    )[:100]
    source_counts = Counter(source for row in active_rows for source in row.get("sources", set()))
    payload = {
        "generated_at": utc_now(),
        "status": "PASS",
        "total_passports": len(passports),
        "active_racecard_horses": len(active_rows),
        "active_racecard_horses_with_passport": len(active_with_passport),
        "active_racecard_coverage_pct": round(len(active_with_passport) / len(active_rows) * 100, 2) if active_rows else 0.0,
        "upcoming_racecard_horses": len(upcoming),
        "upcoming_racecard_with_passport": len(upcoming_with_passport),
        "upcoming_racecard_coverage_pct": round(len(upcoming_with_passport) / len(upcoming) * 100, 2) if upcoming else 0.0,
        "big_race_entries_horses": len(big_entries),
        "big_race_entries_with_passport": len(big_entries_with_passport),
        "big_race_entries_coverage_pct": round(len(big_entries_with_passport) / len(big_entries) * 100, 2) if big_entries else 0.0,
        "missing_high_priority_count": len(missing_active),
        "missing_high_priority_horses": missing_high_priority,
        "unraced_no_form_horses": [_public_horse_row(row) for row in no_form_rows[:100]],
        "unraced_no_form_count": len(no_form_rows),
        "trainer_level_coverage": _trainer_coverage(racecard_horses, passport_ids),
        "course_date_coverage": _course_date_coverage(racecard_horses, passport_ids),
        "source_counts": dict(source_counts),
        "duplicate_check": {"duplicate_passport_uids": duplicate_count},
        "rpr_violation_check": {"violations": len(passport_rows_with_rpr), "keys": passport_rows_with_rpr},
        "rules": {
            "new_build_only": True,
            "old_live_velo_untouched": True,
            "shadow_velo_untouched": True,
            "do_not_train": True,
            "rpr_archive_only": True,
        },
    }
    if execute:
        _write_json(COVERAGE_JSON_PATH, payload)
        COVERAGE_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
        COVERAGE_MD_PATH.write_text(_coverage_markdown(payload), encoding="utf-8")
    return payload


def _coverage_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Passport Coverage Map",
        f"Generated: {payload['generated_at']}",
        "",
        "## Summary",
        f"- **Total passports**: {payload['total_passports']}",
        f"- **Active racecard horses**: {payload['active_racecard_horses']}",
        f"- **Active racecard coverage**: {payload['active_racecard_horses_with_passport']} / {payload['active_racecard_horses']} ({payload['active_racecard_coverage_pct']}%)",
        f"- **Upcoming racecard coverage**: {payload['upcoming_racecard_with_passport']} / {payload['upcoming_racecard_horses']} ({payload['upcoming_racecard_coverage_pct']}%)",
        f"- **Big Race Entries coverage**: {payload['big_race_entries_with_passport']} / {payload['big_race_entries_horses']} ({payload['big_race_entries_coverage_pct']}%)",
        f"- **Missing high-priority horses**: {payload['missing_high_priority_count']}",
        f"- **Unraced/no-form horses**: {payload['unraced_no_form_count']}",
        f"- **Duplicate passport UIDs**: {payload['duplicate_check']['duplicate_passport_uids']}",
        f"- **RPR violations**: {payload['rpr_violation_check']['violations']}",
        "",
        "## Source Counts",
        "| Source | Horses |",
        "|---|---:|",
    ]
    for source, count in sorted(payload["source_counts"].items()):
        lines.append(f"| {source} | {count} |")
    lines += ["", "## Missing High-Priority Horses (Top 30)", "| RP UID | Horse | Sources | Trainer |", "|---|---|---|---|"]
    for row in payload["missing_high_priority_horses"][:30]:
        lines.append(f"| {row.get('rp_uid')} | {row.get('name')} | {', '.join(row.get('sources', []))} | {row.get('trainer')} |")
    lines += ["", "## Trainer Coverage (Top 30)", "| Trainer | Active | Passport | Missing | Coverage |", "|---|---:|---:|---:|---:|"]
    for row in payload["trainer_level_coverage"][:30]:
        lines.append(
            f"| {row['trainer']} | {row['active_horses']} | {row['passport_horses']} | {row['missing_horses']} | {row['coverage_pct']}% |"
        )
    lines += ["", "## Course/Date Coverage", "| Date | Course | Source | Runners | Passport | Missing | Coverage |", "|---|---|---|---:|---:|---:|---:|"]
    for row in payload["course_date_coverage"][:80]:
        lines.append(
            f"| {row['source_date']} | {row['course']} | {row['source']} | {row['runners']} | {row['passport_runners']} | {row['missing_runners']} | {row['coverage_pct']}% |"
        )
    lines += [
        "",
        "## Interpretation",
        "- `UNRACED_OR_NO_FORM_HISTORY` is not a scrape failure; it means the profile exists but no usable form-history passport could be built yet.",
        "- Review-only raw profile links remain held unless they match active racecard evidence.",
        "- RPR remains archive-only and is not emitted into the profile passport feature matrix.",
    ]
    return "\n".join(lines)


def _phase2_priority(horse: dict[str, Any], trainer_volume: Counter[str], queue_row: dict[str, Any] | None) -> tuple[int, str]:
    sources = horse.get("sources", set())
    if "upcoming_racecard" in sources:
        return 10, "UPCOMING_DECLARED_RUNNER_WITHOUT_PASSPORT"
    if "big_race_entries" in sources:
        return 20, "BIG_RACE_ENTRY_WITHOUT_PASSPORT"
    trainer = horse.get("trainer") or ""
    if trainer and trainer_volume[trainer] >= 8:
        return 30, "ACTIVE_HIGH_VOLUME_TRAINER_WITHOUT_PASSPORT"
    if queue_row and queue_row.get("source") == "top_rated_flat":
        return 40, "TOP_RATED_ACTIVE_FLAT_WITHOUT_PASSPORT"
    if queue_row and any(item.get("source") == "raw_profile_link_review" for item in queue_row.get("sources", [])):
        return 50, "REVIEW_LINK_UPGRADED_BY_ACTIVE_EVIDENCE"
    return 60, "ACTIVE_RACECARD_WITHOUT_PASSPORT"


def build_phase2_queue(*, execute: bool = False) -> dict[str, Any]:
    _, passport_ids, _ = load_passports()
    racecard_horses = collect_racecard_horses()
    latest_queue = load_latest_queue()
    trainer_volume = Counter(row.get("trainer") or "" for row in racecard_horses.values())
    rows: list[dict[str, Any]] = []
    for horse in racecard_horses.values():
        uid = horse.get("rp_uid")
        if uid in passport_ids:
            continue
        queue_row = latest_queue.get(uid or "")
        priority, reason = _phase2_priority(horse, trainer_volume, queue_row)
        latest_status = queue_row.get("status") if queue_row else None
        if latest_status == "CAPTURED_NEEDS_FORM_HISTORY_OR_NO_RUNS":
            status = "UNRACED_OR_NO_FORM_HISTORY"
            capture_allowed = False
        elif latest_status == "NEEDS_SOURCE_REVIEW":
            status = "NEEDS_SOURCE_REVIEW_ACTIVE_MATCH"
            capture_allowed = False
        else:
            status = "QUEUED_FOR_CAPTURE"
            capture_allowed = bool(horse.get("profile_url"))
        rows.append(
            {
                "rp_uid": uid,
                "name": horse.get("name"),
                "normalized_name": horse.get("normalized_name"),
                "trainer": horse.get("trainer"),
                "profile_url": horse.get("profile_url"),
                "phase2_priority": priority,
                "status": status,
                "capture_allowed": capture_allowed,
                "reason": reason,
                "sources": sorted(horse.get("sources", [])),
                "source_dates": sorted(horse.get("source_dates", [])),
                "courses": sorted(horse.get("courses", [])),
                "already_passported": False,
                "trust_policy": TRUST_POLICY,
                "velo_scoring_allowed": False,
                "rpr_policy": RPR_POLICY,
                "rpr_feature_allowed": False,
            }
        )
    rows.sort(key=lambda r: (r["phase2_priority"], r["status"], str(r.get("name") or "")))
    status_counts = Counter(row["status"] for row in rows)
    payload = {
        "generated_at": utc_now(),
        "queue_path": str(PHASE2_QUEUE_PATH),
        "phase2_queue_rows": len(rows),
        "capture_allowed_rows": sum(1 for row in rows if row["capture_allowed"]),
        "unraced_no_form_rows": status_counts.get("UNRACED_OR_NO_FORM_HISTORY", 0),
        "review_only_upgraded_rows": status_counts.get("NEEDS_SOURCE_REVIEW_ACTIVE_MATCH", 0),
        "status_counts": dict(status_counts),
        "top_50": rows[:50],
        "rules": {
            "no_blind_review_link_scrape": True,
            "append_only": True,
            "rpr_archive_only": True,
        },
    }
    if execute:
        _write_jsonl(PHASE2_QUEUE_PATH, rows)
    return payload


def passport_to_feature_row(passport: dict[str, Any]) -> dict[str, Any]:
    class_movement = str(passport.get("class_movement") or "").upper()
    layoff_flag = str(passport.get("layoff_flag") or "").upper()
    return {
        "horse_rp_uid": _uid(passport.get("horse_rp_uid")),
        "horse": passport.get("horse_name"),
        "source": PROFILE_FEATURE_SOURCE,
        "source_file": str(PASSPORT_PATH),
        "trust_policy": TRUST_POLICY,
        "live_velo_impact": False,
        "shadow_velo_impact": False,
        "new_build_velo_allowed": True,
        "rpr_policy": "RPR_ARCHIVE_ONLY",
        "rpr_feature_allowed": False,
        "pp_career_runs": _safe_float(passport.get("career_runs")),
        "pp_win_rate": _safe_float(passport.get("win_rate")),
        "pp_place_rate": _safe_float(passport.get("place_rate")),
        "pp_days_since_last": _safe_float(passport.get("days_since_last_run")),
        "pp_layoff": None if not layoff_flag else (0.0 if layoff_flag == "ACTIVE" else 1.0),
        "pp_avg_sp_last5": _safe_float(passport.get("avg_sp_last5")),
        "pp_jockey_continuity": 1.0 if passport.get("jockey_continuity") else 0.0,
        "pp_course_seen": None,
        "pp_or_change_3": _safe_float(passport.get("or_change_last3")),
        "pp_class_moved_up": 1.0 if class_movement == "UP" else 0.0 if class_movement == "DOWN" else None,
        "pp_class_moved_down": 1.0 if class_movement == "DOWN" else 0.0 if class_movement == "UP" else None,
    }


def build_feature_matrix(*, execute: bool = False) -> dict[str, Any]:
    passports, passport_ids, duplicate_count = load_passports()
    racecard_horses = collect_racecard_horses()
    rows = [passport_to_feature_row(row) for row in passports]
    rpr_violations = _rpr_violations(rows)
    df = pd.DataFrame(rows)
    feature_coverage = {
        col: round(float(df[col].notna().mean() * 100), 2) if col in df.columns and len(df) else 0.0
        for col in PASSPORT_FEATURE_COLS
    }
    historical_cols: list[str] = []
    if HISTORICAL_PASSPORT_FEATURES.exists():
        historical_cols = list(pd.read_parquet(HISTORICAL_PASSPORT_FEATURES).columns)
    missing_historical_features = [col for col in PASSPORT_FEATURE_COLS if col not in df.columns]
    active_horse_ids = {row.get("rp_uid") for row in racecard_horses.values() if row.get("rp_uid")}
    active_with_features = len(active_horse_ids & passport_ids)
    payload = {
        "generated_at": utc_now(),
        "feature_path": str(FEATURE_PARQUET_PATH),
        "passports_converted": len(rows),
        "feature_coverage": feature_coverage,
        "missing_fields": [col for col, pct in feature_coverage.items() if pct == 0.0],
        "schema_match_vs_historical_passport_features": {
            "historical_path": str(HISTORICAL_PASSPORT_FEATURES),
            "historical_columns_present": bool(historical_cols),
            "model_feature_columns_present": [col for col in PASSPORT_FEATURE_COLS if col in df.columns],
            "missing_historical_model_features": missing_historical_features,
            "profile_level_not_race_level": True,
            "race_id_join_key_available": False,
        },
        "current_card_usability": {
            "active_racecard_horses": len(active_horse_ids),
            "active_racecard_horses_with_profile_features": active_with_features,
            "coverage_pct": round(active_with_features / len(active_horse_ids) * 100, 2) if active_horse_ids else 0.0,
        },
        "duplicate_passport_uids": duplicate_count,
        "rpr_violations": len(rpr_violations),
        "rpr_violation_keys": rpr_violations,
        "classification": "PASSPORT_FEATURE_BRIDGE_READY" if not rpr_violations else "PASSPORT_FEATURE_BRIDGE_BLOCKED",
    }
    if execute:
        _assert_new_build_path(FEATURE_PARQUET_PATH)
        FEATURE_PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(FEATURE_PARQUET_PATH, index=False)
        _write_json(FEATURE_JSON_PATH, payload)
        FEATURE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        FEATURE_REPORT_PATH.write_text(_feature_markdown(payload), encoding="utf-8")
    return payload


def _feature_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# RP Profile Passport Feature Matrix",
        f"Generated: {payload['generated_at']}",
        "",
        "## Summary",
        f"- **Passports converted**: {payload['passports_converted']}",
        f"- **Feature path**: `{payload['feature_path']}`",
        f"- **Classification**: `{payload['classification']}`",
        f"- **RPR violations**: {payload['rpr_violations']}",
        f"- **Current-card usability**: {payload['current_card_usability']['active_racecard_horses_with_profile_features']} / {payload['current_card_usability']['active_racecard_horses']} ({payload['current_card_usability']['coverage_pct']}%)",
        "",
        "## Feature Coverage",
        "| Feature | Coverage |",
        "|---|---:|",
    ]
    for col, pct in payload["feature_coverage"].items():
        lines.append(f"| `{col}` | {pct}% |")
    schema = payload["schema_match_vs_historical_passport_features"]
    lines += [
        "",
        "## Schema Match Notes",
        f"- Historical passport model columns present: `{schema['historical_columns_present']}`",
        f"- Model feature columns present: `{len(schema['model_feature_columns_present'])}` / {len(PASSPORT_FEATURE_COLS)}",
        f"- Race-level join key available: `{schema['race_id_join_key_available']}`",
        "- `pp_course_seen` is intentionally blank at profile level because it needs the target race course.",
        "- No RPR field is emitted as a model-ready feature.",
    ]
    return "\n".join(lines)


def run_phase2(*, execute: bool = False) -> dict[str, Any]:
    coverage = build_coverage_map(execute=execute)
    queue = build_phase2_queue(execute=execute)
    feature = build_feature_matrix(execute=execute)
    return {
        "generated_at": utc_now(),
        "status": "PASS" if execute else "DRY_RUN",
        "coverage": {
            "total_passports": coverage["total_passports"],
            "active_racecard_coverage_pct": coverage["active_racecard_coverage_pct"],
            "upcoming_racecard_coverage_pct": coverage["upcoming_racecard_coverage_pct"],
            "big_race_entries_coverage_pct": coverage["big_race_entries_coverage_pct"],
            "missing_high_priority_count": coverage["missing_high_priority_count"],
            "unraced_no_form_count": coverage["unraced_no_form_count"],
        },
        "phase2_queue": {
            "rows": queue["phase2_queue_rows"],
            "capture_allowed_rows": queue["capture_allowed_rows"],
            "unraced_no_form_rows": queue["unraced_no_form_rows"],
        },
        "feature_bridge": {
            "passports_converted": feature["passports_converted"],
            "current_card_usability": feature["current_card_usability"],
            "rpr_violations": feature["rpr_violations"],
            "classification": feature["classification"],
        },
        "classification": "PASSPORT_BANK_PHASE2_READY" if feature["classification"] == "PASSPORT_FEATURE_BRIDGE_READY" else "PASSPORT_FEATURE_BRIDGE_BLOCKED",
    }
