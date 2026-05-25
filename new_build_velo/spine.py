"""New Build VELO ingest/process/learn spine.

This module replicates the shape of VELO's daily flow without copying the
clutter or touching Live/Shadow state:

1. ingest: parsed RP archive -> normalized New Build runners
2. process: normalized runners -> archive context signals
3. learn: outcome bridge -> sandbox learning state and append-only ledger

All outputs live under data/new_build/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
NEW_BUILD_ROOT = ROOT / "data" / "new_build"
NORMALIZED_ROOT = NEW_BUILD_ROOT / "normalized"
PROCESSED_ROOT = NEW_BUILD_ROOT / "processed"
LEARNING_ROOT = NEW_BUILD_ROOT / "learning"

TRUST_POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
RPR_POLICY = "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO"
SCORING_ALLOWED = False


@dataclass(frozen=True)
class RunnerRecord:
    source_date: str
    race_id: str | int | None
    course: str | None
    off_time: str | None
    race_title: str | None
    race_class: str | None
    race_type: str | None
    distance_yards: int | float | None
    going: str | None
    surface: str | None
    horse: str | None
    rp_horse_id: str | int | None
    normalized_name: str
    draw: str | int | None
    age: str | int | None
    country: str | None
    sex_colour: str | None
    trainer: str | None
    jockey: str | None
    owner: str | None
    sire: str | None
    dam: str | None
    dam_sire: str | None
    headgear: str | None
    headgear_first_time: bool
    gelding_first_time: bool
    wind_surgery: Any
    days_since_run: str | int | None
    form_figures: str | None
    forecast_odds: Any
    official_rating_archive_only: Any
    topspeed_archive_only: Any
    rp_rpr_archive_only: Any
    spotlight_comment_present: bool
    newspaper_comment_present: bool
    newspaper_tip_count: int
    non_runner: bool
    reserve: bool
    profile_url: str | None
    trust_policy: str = TRUST_POLICY
    velo_scoring_allowed: bool = SCORING_ALLOWED
    rpr_policy: str = RPR_POLICY
    rp_rpr_velo_allowed: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    resolved = path.resolve()
    allowed = NEW_BUILD_ROOT.resolve()
    if allowed not in resolved.parents and resolved != allowed:
        raise ValueError(f"New Build writes are restricted to {allowed}: {resolved}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def stable_id(*parts: Any) -> str:
    joined = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:20]


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def ingest_date(source_date: str, *, execute: bool = False) -> dict[str, Any]:
    racecard = load_json(PARSED_ROOT / source_date / "racecard_injection.json", {})
    rows: list[RunnerRecord] = []
    for race in racecard.get("races") or []:
        for runner in race.get("runners") or []:
            rows.append(
                RunnerRecord(
                    source_date=source_date,
                    race_id=race.get("race_id"),
                    course=race.get("course"),
                    off_time=race.get("race_time"),
                    race_title=race.get("race_title"),
                    race_class=race.get("race_class"),
                    race_type=race.get("race_type"),
                    distance_yards=race.get("distance_yards"),
                    going=race.get("going"),
                    surface=race.get("surface"),
                    horse=runner.get("horse"),
                    rp_horse_id=runner.get("horse_id"),
                    normalized_name=norm(runner.get("horse")),
                    draw=runner.get("draw"),
                    age=runner.get("age"),
                    country=runner.get("country"),
                    sex_colour=runner.get("sex_colour"),
                    trainer=runner.get("trainer"),
                    jockey=runner.get("jockey"),
                    owner=runner.get("owner"),
                    sire=runner.get("sire"),
                    dam=runner.get("dam"),
                    dam_sire=runner.get("damsire"),
                    headgear=runner.get("headgear"),
                    headgear_first_time=bool(runner.get("headgear_first_time")),
                    gelding_first_time=bool(runner.get("gelding_first_time")),
                    wind_surgery=runner.get("wind_surgery"),
                    days_since_run=runner.get("days_since_last_run"),
                    form_figures=runner.get("form_figures"),
                    forecast_odds=runner.get("forecast_odds"),
                    official_rating_archive_only=runner.get("official_rating"),
                    topspeed_archive_only=runner.get("topspeed"),
                    rp_rpr_archive_only=runner.get("rp_rpr_archive_only"),
                    spotlight_comment_present=bool(runner.get("spotlight_comment")),
                    newspaper_comment_present=bool(runner.get("diomed_comment")),
                    newspaper_tip_count=_to_int(runner.get("newspaper_tip_count")),
                    non_runner=bool(runner.get("non_runner")),
                    reserve=bool(runner.get("irish_reserve")),
                    profile_url=runner.get("horse_url"),
                )
            )

    payload = {
        "generated_at": utc_now(),
        "source_date": source_date,
        "stage": "ingest",
        "status": "PASS" if rows else "NO_RACECARD_ROWS",
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": False,
        "rpr_policy": RPR_POLICY,
        "runner_count": len(rows),
        "race_count": len({row.race_id for row in rows if row.race_id is not None}),
        "records": [asdict(row) | {"new_build_runner_id": stable_id(source_date, row.race_id, row.normalized_name)} for row in rows],
    }
    if execute:
        write_json(NORMALIZED_ROOT / source_date / "runners.json", payload)
    return payload


def _context_flags(row: dict[str, Any], race_tip_totals: dict[str, int]) -> list[str]:
    flags: list[str] = []
    if row.get("headgear_first_time"):
        flags.append("FIRST_TIME_HEADGEAR")
    if row.get("gelding_first_time"):
        flags.append("FIRST_TIME_GELDING")
    if row.get("wind_surgery"):
        flags.append("WIND_SURGERY_SIGNAL")
    if _to_int(row.get("days_since_run")) >= 180:
        flags.append("LAYOFF_WARNING")
    if row.get("newspaper_tip_count", 0) >= 6:
        flags.append("TIP_HEAT")
    race_key = str(row.get("race_id") or row.get("off_time") or "")
    if race_tip_totals.get(race_key, 0) and row.get("newspaper_tip_count", 0) / race_tip_totals[race_key] >= 0.45:
        flags.append("PUBLIC_OVERLOAD_CANDIDATE")
    if row.get("spotlight_comment_present") or row.get("newspaper_comment_present"):
        flags.append("HUMAN_CONTEXT_AVAILABLE")
    if row.get("sire") and row.get("dam"):
        flags.append("PEDIGREE_CONTEXT_AVAILABLE")
    if not flags:
        flags.append("LOW_ARCHIVE_SIGNAL")
    return flags


def process_date(source_date: str, *, execute: bool = False) -> dict[str, Any]:
    normalized = load_json(NORMALIZED_ROOT / source_date / "runners.json", None)
    if not normalized:
        normalized = ingest_date(source_date, execute=False)

    records = normalized.get("records") or []
    race_tip_totals: dict[str, int] = defaultdict(int)
    for row in records:
        race_key = str(row.get("race_id") or row.get("off_time") or "")
        race_tip_totals[race_key] += _to_int(row.get("newspaper_tip_count"))

    processed: list[dict[str, Any]] = []
    for row in records:
        flags = _context_flags(row, race_tip_totals)
        processed.append(
            {
                "new_build_runner_id": row["new_build_runner_id"],
                "source_date": source_date,
                "race_id": row.get("race_id"),
                "course": row.get("course"),
                "off_time": row.get("off_time"),
                "horse": row.get("horse"),
                "normalized_name": row.get("normalized_name"),
                "rp_horse_id": row.get("rp_horse_id"),
                "trainer": row.get("trainer"),
                "jockey": row.get("jockey"),
                "archive_context_flags": flags,
                "tip_heat": row.get("newspaper_tip_count", 0),
                "profile_context_available": bool(row.get("profile_url")),
                "rpr_seen_archive_only": row.get("rp_rpr_archive_only") not in (None, "", "-"),
                "trust_policy": TRUST_POLICY,
                "velo_scoring_allowed": False,
                "rpr_policy": RPR_POLICY,
                "rp_rpr_velo_allowed": False,
            }
        )

    flag_counts = Counter(flag for row in processed for flag in row["archive_context_flags"])
    payload = {
        "generated_at": utc_now(),
        "source_date": source_date,
        "stage": "process",
        "status": "PASS" if processed else "NO_NORMALIZED_ROWS",
        "runner_count": len(processed),
        "flag_counts": dict(flag_counts),
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": False,
        "rpr_policy": RPR_POLICY,
        "records": processed,
    }
    if execute:
        write_json(PROCESSED_ROOT / source_date / "runner_context.json", payload)
    return payload


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def learn(*, from_date: str, to_date: str, execute: bool = False) -> dict[str, Any]:
    bridge = load_json(PARSED_ROOT / "rp_archive_outcome_bridge.json", {})
    rows = bridge.get("rows") or []
    eligible = [
        row
        for row in rows
        if from_date <= str(row.get("race_date") or "") <= to_date
        and row.get("classification") == "OUTCOME_CONFIRMED"
        and row.get("identity_confidence", 0) >= 0.8
    ]

    state_path = LEARNING_ROOT / "sandbox_state.json"
    ledger_path = LEARNING_ROOT / "sandbox_events.jsonl"
    prior_state = load_json(state_path, {"version": 1, "learned_events": 0, "signal_counts": {}, "outcome_counts": {}})
    prior_ledger = _iter_jsonl(ledger_path)
    seen = {row.get("event_id") for row in prior_ledger}

    new_events: list[dict[str, Any]] = []
    for row in eligible:
        event_id = stable_id(row.get("race_date"), row.get("race_id"), row.get("rp_horse_id"), row.get("classification"))
        if event_id in seen:
            continue
        new_events.append(
            {
                "event_id": event_id,
                "learned_at": utc_now(),
                "race_date": row.get("race_date"),
                "race_id": row.get("race_id"),
                "horse": row.get("rp_horse_name"),
                "rp_horse_id": row.get("rp_horse_id"),
                "won": row.get("won"),
                "framed": row.get("framed"),
                "archive_context_flags": row.get("archive_context_flags") or [],
                "trust_policy": TRUST_POLICY,
                "velo_scoring_allowed": False,
                "rpr_policy": RPR_POLICY,
                "rpr_archive_only_excluded": True,
                "learning_target": "new_build_sandbox_only",
            }
        )

    signal_counts = Counter(prior_state.get("signal_counts") or {})
    outcome_counts = Counter(prior_state.get("outcome_counts") or {})
    for event in new_events:
        outcome_counts["won" if event.get("won") else "not_won"] += 1
        if event.get("framed"):
            outcome_counts["framed"] += 1
        for flag in event.get("archive_context_flags") or []:
            signal_counts[flag] += 1

    next_state = {
        "version": 1,
        "updated_at": utc_now(),
        "learning_target": "new_build_sandbox_only",
        "learned_events": int(prior_state.get("learned_events") or 0) + len(new_events),
        "last_window": {"from_date": from_date, "to_date": to_date},
        "signal_counts": dict(signal_counts),
        "outcome_counts": dict(outcome_counts),
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": False,
        "rpr_policy": RPR_POLICY,
        "rpr_archive_only_excluded": True,
        "live_velo_touched": False,
        "shadow_velo_touched": False,
    }

    payload = {
        "generated_at": utc_now(),
        "stage": "learn",
        "status": "PASS" if new_events else "OUTCOME_REQUIRED_BEFORE_LEARNING",
        "from_date": from_date,
        "to_date": to_date,
        "eligible_outcomes": len(eligible),
        "new_events": len(new_events),
        "state": next_state,
        "ledger_path": str(ledger_path),
        "state_path": str(state_path),
        "live_velo_touched": False,
        "shadow_velo_touched": False,
    }
    if execute:
        LEARNING_ROOT.mkdir(parents=True, exist_ok=True)
        if new_events:
            with ledger_path.open("a", encoding="utf-8") as handle:
                for event in new_events:
                    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        write_json(state_path, next_state)
        write_json(LEARNING_ROOT / "latest_learn_report.json", payload)
    return payload


def run_all(*, from_date: str, to_date: str, execute: bool = False) -> dict[str, Any]:
    dates = []
    start = datetime.strptime(from_date, "%Y-%m-%d").date()
    end = datetime.strptime(to_date, "%Y-%m-%d").date()
    cursor = start
    while cursor <= end:
        dates.append(cursor.isoformat())
        cursor = cursor.fromordinal(cursor.toordinal() + 1)

    ingest_reports = [ingest_date(day, execute=execute) for day in dates]
    process_reports = [process_date(day, execute=execute) for day in dates]
    learn_report = learn(from_date=from_date, to_date=to_date, execute=execute)
    payload = {
        "generated_at": utc_now(),
        "classification": "NEW_BUILD_REPLICA_LOOP_READY",
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "from_date": from_date,
        "to_date": to_date,
        "ingest": ingest_reports,
        "process": process_reports,
        "learn": learn_report,
        "live_velo_touched": False,
        "shadow_velo_touched": False,
        "trust_policy": TRUST_POLICY,
        "rpr_policy": RPR_POLICY,
    }
    if execute:
        write_json(NEW_BUILD_ROOT / "latest_loop_report.json", payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="New Build VELO clean ingest/process/learn replica.")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest_p = sub.add_parser("ingest")
    ingest_p.add_argument("--date", required=True)
    ingest_p.add_argument("--execute", action="store_true")
    process_p = sub.add_parser("process")
    process_p.add_argument("--date", required=True)
    process_p.add_argument("--execute", action="store_true")
    learn_p = sub.add_parser("learn")
    learn_p.add_argument("--from-date", required=True)
    learn_p.add_argument("--to-date", required=True)
    learn_p.add_argument("--execute", action="store_true")
    all_p = sub.add_parser("run-all")
    all_p.add_argument("--from-date", required=True)
    all_p.add_argument("--to-date", required=True)
    all_p.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "ingest":
        payload = ingest_date(args.date, execute=args.execute)
    elif args.command == "process":
        payload = process_date(args.date, execute=args.execute)
    elif args.command == "learn":
        payload = learn(from_date=args.from_date, to_date=args.to_date, execute=args.execute)
    else:
        payload = run_all(from_date=args.from_date, to_date=args.to_date, execute=args.execute)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0
