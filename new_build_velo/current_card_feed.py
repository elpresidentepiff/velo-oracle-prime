"""Current-card Passport Feed for New Build VELO.

This is an analyst feed, not a betting engine. It joins upcoming Racing Post
racecards to the Passport Bank and champion passport feature schema, then
writes New Build-only artifacts under data/new_build/.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from new_build_velo.passport_bank import PASSPORT_FEATURE_COLS, _date_from_text, _rpr_violations
from new_build_velo.spine import NEW_BUILD_ROOT, PARSED_ROOT, TRUST_POLICY, norm, stable_id


ROOT = Path(__file__).resolve().parents[1]
CURRENT_CARD_ROOT = NEW_BUILD_ROOT / "current_cards"
REPORT_ROOT = NEW_BUILD_ROOT / "reports"
FEED_JSONL_PATH = CURRENT_CARD_ROOT / "current_card_passport_feed_latest.jsonl"
REPORT_JSON_PATH = REPORT_ROOT / "current_card_passport_feed_latest.json"
REPORT_MD_PATH = REPORT_ROOT / "current_card_passport_feed_latest.md"
PASSPORT_PATH = NEW_BUILD_ROOT / "passports" / "horse_passports_v1.jsonl"
PASSPORT_FEATURE_PATH = NEW_BUILD_ROOT / "features" / "rp_profile_passport_features_latest.parquet"
CHAMPION_REGISTRY_PATH = NEW_BUILD_ROOT / "models" / "champion" / "champion_registry.json"
INTENT_FEATURE_PATH = NEW_BUILD_ROOT / "training" / "intent_features.parquet"

RPR_POLICY = "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO"
RPR_POLICY_KEYS = {"rpr_policy", "rp_rpr_velo_allowed", "rpr_feature_allowed"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _assert_new_build_path(path: Path) -> None:
    resolved = path.resolve()
    allowed = NEW_BUILD_ROOT.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"New Build writes are restricted to {allowed}: {resolved}")


def _write_json(path: Path, payload: Any) -> None:
    _assert_new_build_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> int:
    _assert_new_build_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_passports() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(PASSPORT_PATH):
        uid = row.get("horse_rp_uid")
        if uid not in (None, ""):
            out[str(uid)] = row
    return out


def _load_passport_features() -> dict[str, dict[str, Any]]:
    if not PASSPORT_FEATURE_PATH.exists():
        return {}
    df = pd.read_parquet(PASSPORT_FEATURE_PATH)
    rows = df.where(pd.notna(df), None).to_dict("records")
    return {str(row["horse_rp_uid"]): row for row in rows if row.get("horse_rp_uid") not in (None, "")}


def _load_champion_passport_features() -> list[str]:
    registry = _load_json(CHAMPION_REGISTRY_PATH, {})
    groups = registry.get("feature_groups") or {}
    passport = groups.get("passport_layer")
    if passport:
        return [str(item) for item in passport]
    return [feature for feature in registry.get("features_frozen", []) if str(feature).startswith("pp_")]


def _load_intent_keys() -> set[tuple[str, str]]:
    if not INTENT_FEATURE_PATH.exists():
        return set()
    try:
        df = pd.read_parquet(INTENT_FEATURE_PATH, columns=["race_id", "horse"])
    except Exception:
        df = pd.read_parquet(INTENT_FEATURE_PATH)
        if not {"race_id", "horse"}.issubset(df.columns):
            return set()
        df = df[["race_id", "horse"]]
    return {(str(row.race_id), norm(row.horse)) for row in df.itertuples(index=False)}


def _racecard_source(capture_date: str, path: Path) -> str:
    text = f"{capture_date} {path.as_posix()}".lower()
    if "big-race-entries" in text:
        return "big_race_entries"
    date_value = _date_from_text(capture_date) or _date_from_text(path.as_posix())
    if date_value and date_value >= "2026-05-26":
        return "upcoming_racecard"
    return "current_racecard"


def _source_rank(source: str) -> int:
    return {
        "current_racecard": 0,
        "upcoming_racecard": 1,
        "big_race_entries": 2,
    }.get(source, 9)


def _iter_current_racecards() -> list[tuple[Path, dict[str, Any], str]]:
    cards: list[tuple[Path, dict[str, Any], str]] = []
    for path in sorted(PARSED_ROOT.glob("*/racecard_injection.json")):
        data = _load_json(path, {})
        capture_date = data.get("capture_date") or path.parent.name
        source = _racecard_source(capture_date, path)
        if source in {"upcoming_racecard", "big_race_entries"}:
            cards.append((path, data, source))
    return cards


def _missing_reason(
    *,
    passport_found: bool,
    champion_features_available: bool,
    intent_features_available: bool,
    runner: dict[str, Any],
) -> str | None:
    if not passport_found:
        return "UNRACED_OR_NO_FORM_HISTORY_OR_NOT_IN_PASSPORT_BANK"
    if not champion_features_available:
        return "PASSPORT_FOUND_BUT_CHAMPION_FEATURES_INCOMPLETE"
    if not intent_features_available:
        return "INTENT_FEATURES_NOT_AVAILABLE_FOR_CURRENT_RACE"
    if runner.get("non_runner"):
        return "NON_RUNNER"
    return None


def _passport_summary(passport: dict[str, Any] | None) -> dict[str, Any]:
    if not passport:
        return {}
    return {
        "career_runs": passport.get("career_runs"),
        "win_rate": passport.get("win_rate"),
        "place_rate": passport.get("place_rate"),
        "days_since_last_run": passport.get("days_since_last_run"),
        "layoff_flag": passport.get("layoff_flag"),
        "avg_sp_last5": passport.get("avg_sp_last5"),
        "jockey_continuity": passport.get("jockey_continuity"),
        "or_trajectory": passport.get("or_trajectory"),
        "or_change_last3": passport.get("or_change_last3"),
        "class_movement": passport.get("class_movement"),
        "cash_run_candidate": passport.get("cash_run_candidate"),
        "setup_run_candidate": passport.get("setup_run_candidate"),
    }


def _reason_codes(
    *,
    passport: dict[str, Any] | None,
    feature: dict[str, Any] | None,
    runner: dict[str, Any],
    intent_features_available: bool,
) -> list[str]:
    codes: list[str] = []
    if not passport:
        codes.append("MISSING_PASSPORT")
        return codes
    if _to_int(passport.get("career_runs")) <= 1:
        codes.append("UNEXPOSED_PROFILE")
    if str(passport.get("layoff_flag") or "").startswith("FRESH"):
        codes.append("LAYOFF_PATTERN")
    if passport.get("jockey_continuity"):
        codes.append("JOCKEY_CONTINUITY")
    if passport.get("cash_run_candidate"):
        codes.append("CASH_RUN_CANDIDATE")
    if passport.get("setup_run_candidate"):
        codes.append("SETUP_RUN_CANDIDATE")
    if _to_float(passport.get("place_rate")) >= 0.5:
        codes.append("STRONG_PLACE_PROFILE")
    if _to_float(passport.get("avg_sp_last5"), 999.0) <= 5.0:
        codes.append("HISTORICAL_MARKET_RESPECT")
    if _to_float(passport.get("or_change_last3")) > 0:
        codes.append("OR_RISING")
    if _to_float(passport.get("or_change_last3")) < 0:
        codes.append("OR_FALLING")
    if runner.get("headgear_first_time"):
        codes.append("FIRST_TIME_HEADGEAR")
    if runner.get("wind_surgery"):
        codes.append("WIND_SURGERY_FLAG")
    if feature and feature.get("pp_course_seen") is None:
        codes.append("COURSE_SEEN_NEEDS_TARGET_COURSE_COMPUTE")
    if not intent_features_available:
        codes.append("NO_INTENT_SCORE_FOR_CURRENT_RACE")
    return codes


def _passport_strength(passport: dict[str, Any] | None) -> float:
    if not passport:
        return -1.0
    score = 0.0
    score += min(_to_float(passport.get("career_runs")) / 20.0, 1.5)
    score += _to_float(passport.get("place_rate")) * 2.0
    score += _to_float(passport.get("win_rate")) * 1.5
    avg_sp = _to_float(passport.get("avg_sp_last5"), 99.0)
    if avg_sp <= 4:
        score += 1.0
    elif avg_sp <= 8:
        score += 0.5
    if passport.get("jockey_continuity"):
        score += 0.25
    if passport.get("cash_run_candidate"):
        score += 0.35
    if passport.get("setup_run_candidate"):
        score += 0.25
    if _to_float(passport.get("or_change_last3")) > 0:
        score += 0.25
    return round(score, 4)


def _current_card_feature_check() -> dict[str, Any]:
    champion_features = _load_champion_passport_features()
    feature_rows = _load_passport_features()
    sample_rows = list(feature_rows.values())
    present = [col for col in champion_features if sample_rows and col in sample_rows[0]]
    null_rates = {}
    if sample_rows:
        df = pd.DataFrame(sample_rows)
        for col in champion_features:
            null_rates[col] = round(float(df[col].isna().mean() * 100), 2) if col in df.columns else 100.0
    violations = _rpr_violations(sample_rows)
    return {
        "feature_columns_present": present,
        "missing_champion_passport_features": [col for col in champion_features if col not in present],
        "null_rates": null_rates,
        "schema_compatible": set(champion_features).issubset(set(present)),
        "rpr_violations": len(violations),
        "rpr_violation_keys": violations,
    }


def build_current_card_feed(*, execute: bool = False) -> dict[str, Any]:
    passports = _load_passports()
    passport_features = _load_passport_features()
    champion_passport_features = _load_champion_passport_features()
    intent_keys = _load_intent_keys()
    feature_check = _current_card_feature_check()
    feed_by_id: dict[str, dict[str, Any]] = {}
    race_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    races_seen: set[str] = set()

    for source_file, card, source in _iter_current_racecards():
        for race in card.get("races", []):
            race_date = _date_from_text(race.get("race_time")) or _date_from_text(card.get("capture_date")) or card.get("capture_date")
            race_id = str(race.get("race_id") or stable_id(source_file, race.get("race_time"), race.get("course"), race.get("race_title")))
            race_key = stable_id(race_date, race_id, race.get("course"), race.get("race_time"))
            races_seen.add(race_key)
            for runner in race.get("runners", []):
                uid = str(runner.get("horse_id")) if runner.get("horse_id") not in (None, "") else None
                passport = passports.get(uid or "")
                feature = passport_features.get(uid or "")
                passport_found = passport is not None
                champion_available = bool(feature) and all(col in feature for col in champion_passport_features)
                intent_available = (race_id, norm(runner.get("horse"))) in intent_keys
                feed_row_id = stable_id(race_key, uid, runner.get("horse"))
                row = {
                    "feed_row_id": feed_row_id,
                    "source": "new_build_current_card_feed_v1",
                    "source_file": str(source_file),
                    "race_source": source,
                    "race_id": race_id,
                    "course": race.get("course"),
                    "off_time": race.get("race_time"),
                    "race_date": race_date,
                    "race_title": race.get("race_title"),
                    "horse": runner.get("horse"),
                    "normalized_name": norm(runner.get("horse")),
                    "rp_uid": uid,
                    "trainer": runner.get("trainer"),
                    "jockey": runner.get("jockey"),
                    "draw": runner.get("draw"),
                    "age": runner.get("age"),
                    "forecast_odds": runner.get("forecast_odds"),
                    "passport_found": passport_found,
                    "champion_features_available": champion_available,
                    "intent_features_available": intent_available,
                    "missing_reason": _missing_reason(
                        passport_found=passport_found,
                        champion_features_available=champion_available,
                        intent_features_available=intent_available,
                        runner=runner,
                    ),
                    "passport_summary": _passport_summary(passport),
                    "passport_strength_score": _passport_strength(passport),
                    "reason_codes": _reason_codes(
                        passport=passport,
                        feature=feature,
                        runner=runner,
                        intent_features_available=intent_available,
                    ),
                    "trust_policy": TRUST_POLICY,
                    "velo_scoring_allowed": False,
                    "live_velo_impact": False,
                    "shadow_velo_impact": False,
                    "rpr_policy": RPR_POLICY,
                    "rpr_feature_allowed": False,
                    "rp_rpr_velo_allowed": False,
                }
                existing = feed_by_id.get(feed_row_id)
                if existing is None or _source_rank(row["race_source"]) < _source_rank(existing["race_source"]):
                    feed_by_id[feed_row_id] = row

    feed_rows = list(feed_by_id.values())
    for row in feed_rows:
        race_key = stable_id(row.get("race_date"), row.get("race_id"), row.get("course"), row.get("off_time"))
        race_groups[race_key].append(row)
    rpr_violations = _rpr_violations(feed_rows)
    runner_count = len(feed_rows)
    passport_count = sum(1 for row in feed_rows if row["passport_found"])
    champion_count = sum(1 for row in feed_rows if row["champion_features_available"])
    intent_count = sum(1 for row in feed_rows if row["intent_features_available"])
    missing_rows = [row for row in feed_rows if not row["passport_found"]]
    no_form_rows = [row for row in missing_rows if row["missing_reason"] == "UNRACED_OR_NO_FORM_HISTORY_OR_NOT_IN_PASSPORT_BANK"]
    race_reports = _build_race_reports(race_groups)
    payload = {
        "generated_at": utc_now(),
        "status": "PASS",
        "classification": "CURRENT_CARD_FEED_READY" if not rpr_violations else "CURRENT_CARD_FEED_BLOCKED",
        "feature_matrix_validation": feature_check,
        "races_processed": len(races_seen),
        "runners_processed": runner_count,
        "passport_coverage": {
            "found": passport_count,
            "total": runner_count,
            "coverage_pct": round(passport_count / runner_count * 100, 2) if runner_count else 0.0,
        },
        "champion_feature_coverage": {
            "found": champion_count,
            "total": runner_count,
            "coverage_pct": round(champion_count / runner_count * 100, 2) if runner_count else 0.0,
        },
        "intent_feature_coverage": {
            "found": intent_count,
            "total": runner_count,
            "coverage_pct": round(intent_count / runner_count * 100, 2) if runner_count else 0.0,
        },
        "missing_horses": [
            {
                "race_date": row["race_date"],
                "course": row["course"],
                "horse": row["horse"],
                "rp_uid": row["rp_uid"],
                "trainer": row["trainer"],
                "missing_reason": row["missing_reason"],
            }
            for row in missing_rows[:100]
        ],
        "missing_horse_count": len(missing_rows),
        "unraced_new_horse_count": len(no_form_rows),
        "rpr_violations": len(rpr_violations),
        "rpr_violation_keys": rpr_violations,
        "race_reports": race_reports,
        "rules": {
            "new_build_only": True,
            "no_training": True,
            "no_live_engine": True,
            "old_live_velo_untouched": True,
            "shadow_velo_untouched": True,
            "no_betting": True,
            "no_telegram": True,
            "rpr_archive_only": True,
        },
    }
    if execute:
        _write_jsonl(FEED_JSONL_PATH, feed_rows)
        _write_json(REPORT_JSON_PATH, payload)
        REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_MD_PATH.write_text(_feed_markdown(payload), encoding="utf-8")
    return payload


def _build_race_reports(race_groups: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    reports = []
    for rows in race_groups.values():
        if not rows:
            continue
        ranked = sorted(rows, key=lambda row: row["passport_strength_score"], reverse=True)
        champion_available = [row for row in ranked if row["champion_features_available"]]
        intent_available = [row for row in ranked if row["intent_features_available"]]
        missing = [row for row in rows if not row["passport_found"]]
        warnings = []
        if missing:
            warnings.append(f"{len(missing)} missing/unraced passport rows")
        if not intent_available:
            warnings.append("No current-race intent feature rows available")
        reports.append(
            {
                "race_date": rows[0]["race_date"],
                "course": rows[0]["course"],
                "off_time": rows[0]["off_time"],
                "race_id": rows[0]["race_id"],
                "race_title": rows[0]["race_title"],
                "runner_count": len(rows),
                "passport_coverage": sum(1 for row in rows if row["passport_found"]),
                "champion_feature_coverage": len(champion_available),
                "intent_feature_coverage": len(intent_available),
                "top_3_by_champion_read_availability": [
                    _compact_runner(row) for row in champion_available[:3]
                ],
                "strongest_passport_horse": _compact_runner(ranked[0]) if ranked and ranked[0]["passport_found"] else None,
                "strongest_intent_candidate": _compact_runner(intent_available[0]) if intent_available else None,
                "missing_data_warnings": warnings,
                "unraced_new_horse_warnings": [_compact_runner(row) for row in missing[:5]],
            }
        )
    return sorted(reports, key=lambda row: (str(row.get("race_date")), str(row.get("off_time")), str(row.get("course"))))


def _compact_runner(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "horse": row.get("horse"),
        "rp_uid": row.get("rp_uid"),
        "trainer": row.get("trainer"),
        "passport_strength_score": row.get("passport_strength_score"),
        "reason_codes": row.get("reason_codes", [])[:8],
        "missing_reason": row.get("missing_reason"),
    }


def _feed_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Current-Card Passport Feed",
        f"Generated: {payload['generated_at']}",
        "",
        "## Summary",
        f"- **Classification**: `{payload['classification']}`",
        f"- **Races processed**: {payload['races_processed']}",
        f"- **Runners processed**: {payload['runners_processed']}",
        f"- **Passport coverage**: {payload['passport_coverage']['found']} / {payload['passport_coverage']['total']} ({payload['passport_coverage']['coverage_pct']}%)",
        f"- **Champion feature coverage**: {payload['champion_feature_coverage']['found']} / {payload['champion_feature_coverage']['total']} ({payload['champion_feature_coverage']['coverage_pct']}%)",
        f"- **Intent feature coverage**: {payload['intent_feature_coverage']['found']} / {payload['intent_feature_coverage']['total']} ({payload['intent_feature_coverage']['coverage_pct']}%)",
        f"- **Missing horses**: {payload['missing_horse_count']}",
        f"- **Unraced/new horses**: {payload['unraced_new_horse_count']}",
        f"- **RPR violations**: {payload['rpr_violations']}",
        "",
        "## Feature Matrix Validation",
        f"- **Schema compatible**: `{payload['feature_matrix_validation']['schema_compatible']}`",
        f"- **Missing champion passport features**: `{payload['feature_matrix_validation']['missing_champion_passport_features']}`",
        "- **RPR check**: no model feature RPR leaks" if payload["rpr_violations"] == 0 else "- **RPR check**: violations present",
        "",
        "## Race Analyst Read",
    ]
    for race in payload["race_reports"][:80]:
        lines += [
            "",
            f"### {race['race_date']} {race['course']} {race['off_time']}",
            f"- **Race**: {race.get('race_title')}",
            f"- **Coverage**: passport {race['passport_coverage']}/{race['runner_count']} | champion {race['champion_feature_coverage']}/{race['runner_count']} | intent {race['intent_feature_coverage']}/{race['runner_count']}",
        ]
        strongest = race.get("strongest_passport_horse")
        if strongest:
            lines.append(f"- **Strongest passport horse**: {strongest['horse']} ({', '.join(strongest.get('reason_codes', []))})")
        else:
            lines.append("- **Strongest passport horse**: none")
        if race.get("strongest_intent_candidate"):
            lines.append(f"- **Strongest intent candidate**: {race['strongest_intent_candidate']['horse']}")
        else:
            lines.append("- **Strongest intent candidate**: unavailable")
        top3 = race.get("top_3_by_champion_read_availability") or []
        if top3:
            lines.append("- **Top 3 by champion-read availability**: " + ", ".join(row["horse"] for row in top3))
        warnings = race.get("missing_data_warnings") or []
        if warnings:
            lines.append("- **Warnings**: " + "; ".join(warnings))
    lines += [
        "",
        "## Boundaries",
        "- Analyst feed only. No staking, no picks, no Telegram.",
        "- New Build only. Old Live VÉLØ and Shadow VÉLØ untouched.",
        "- RPR remains archive-only and is not emitted as a model feature.",
    ]
    return "\n".join(lines)
