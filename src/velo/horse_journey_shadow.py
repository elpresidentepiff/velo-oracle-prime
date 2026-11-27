"""Time-safe Horse Journey / Handicap Release evidence, shadow only.

This module translates already-captured runner facts and historical runs into
auditable *factual pattern tags*.  It is deliberately not a probability model:
there are no weights, recommendations, price rules, rankings, or Prime writes.

It is safe to call only with history strictly before ``race_date``.  A caller
that supplies an on/after-date run gets an explicit rejected packet rather than
a potentially leaked journey narrative.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "horse_journey_shadow_v1"
SOURCE_CONTRACT = "rp_capture_plus_racing_horse_runs_before_race_date"


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _utc(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else None


def _norm(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _same_course(run: Mapping[str, Any], runner: Mapping[str, Any]) -> bool:
    """Match source IDs first; exact normalized course text is only fallback."""
    current_id = str(runner.get("course_id") or "").strip()
    historical_id = str(run.get("course_id") or "").strip()
    if current_id and historical_id:
        return current_id == historical_id
    current_name = _norm(runner.get("course") or runner.get("course_name"))
    historical_name = _norm(run.get("course"))
    return bool(current_name and historical_name and current_name == historical_name)


def _same_distance(run: Mapping[str, Any], runner: Mapping[str, Any]) -> bool:
    try:
        current = float(runner.get("distance_f") or runner.get("dist_f"))
        historical = float(run.get("distance_f") or run.get("dist_f"))
    except (TypeError, ValueError):
        return False
    return abs(current - historical) <= 0.5


def _signal(code: str, **evidence: Any) -> dict[str, Any]:
    return {"code": code, "evidence": {key: value for key, value in evidence.items() if value is not None}}


def build_horse_journey_shadow(
    *,
    race_id: str,
    horse_id: str,
    race_date: str,
    runner: Mapping[str, Any],
    historical_runs: Iterable[Mapping[str, Any]],
    source_captured_at: str | None,
    race_off_time_utc: str | None,
) -> dict[str, Any]:
    """Build an evidence-only journey packet for one intended runner.

    ``historical_runs`` must be sourced under a strict ``run_date < race_date``
    query.  The core validates that promise again, so a post-race rebuild cannot
    silently learn from the runner's same-day result.
    """
    race_day = _date(race_date)
    identity_ok = bool(str(race_id).strip() and str(horse_id).strip())
    reasons: list[str] = []
    if race_day is None:
        reasons.append("INVALID_RACE_DATE")
    if not identity_ok:
        reasons.append("UNPROVEN_CANONICAL_IDENTITY")
    captured_at = _utc(source_captured_at)
    off_time = _utc(race_off_time_utc)
    if captured_at is None:
        reasons.append("MISSING_SOURCE_CAPTURE_TIME")
    if off_time is None:
        reasons.append("MISSING_RACE_OFF_TIME")
    elif captured_at is not None and captured_at >= off_time:
        reasons.append("NOT_CAPTURED_PRE_OFF")

    valid_history: list[Mapping[str, Any]] = []
    rejected_history_rows = 0
    for raw_run in historical_runs:
        run_day = _date(raw_run.get("run_date"))
        if run_day is None or race_day is None or run_day >= race_day:
            rejected_history_rows += 1
            continue
        valid_history.append(raw_run)
    valid_history.sort(key=lambda item: str(item.get("run_date") or ""), reverse=True)
    if rejected_history_rows:
        reasons.append("POST_CUTOFF_OR_INVALID_HISTORY_REJECTED")
    if not valid_history:
        reasons.append("NO_TIME_SAFE_HISTORY")

    facts: list[dict[str, Any]] = []
    current_or = _int(
        runner.get("current_or") or runner.get("or") or runner.get("official_rating") or runner.get("ofr")
    )
    winning_runs = [run for run in valid_history if _int(run.get("position_int")) == 1]
    last_win = winning_runs[0] if winning_runs else None
    last_win_or = _int(last_win.get("official_rating")) if last_win else None
    if current_or is not None and last_win_or is not None:
        delta = current_or - last_win_or
        if delta <= 0:
            facts.append(_signal("JOURNEY_MARK_AT_OR_BELOW_LAST_WIN", current_or=current_or, last_win_or=last_win_or, delta=delta))
        elif delta <= 3:
            facts.append(_signal("JOURNEY_MARK_NEAR_LAST_WIN", current_or=current_or, last_win_or=last_win_or, delta=delta))

    if last_win and _same_course(last_win, runner):
        facts.append(_signal("JOURNEY_RETURN_TO_WINNING_COURSE", last_win_date=last_win.get("run_date")))
    if last_win and _same_distance(last_win, runner):
        facts.append(_signal("JOURNEY_RETURN_TO_WINNING_DISTANCE", last_win_date=last_win.get("run_date")))

    current_jockey = str(runner.get("jockey_id") or "").strip()
    prior_jockey = str(valid_history[0].get("jockey_id") or "").strip() if valid_history else ""
    if current_jockey and prior_jockey and current_jockey != prior_jockey:
        facts.append(_signal("JOURNEY_JOCKEY_CHANGE", previous_jockey_id=prior_jockey, current_jockey_id=current_jockey))

    if valid_history:
        latest_day = _date(valid_history[0].get("run_date"))
        days_since = (race_day - latest_day).days if race_day and latest_day else None
        if days_since is not None and 14 <= days_since <= 45:
            facts.append(_signal("JOURNEY_STANDARD_RETURN_WINDOW", days_since_run=days_since))

    stable_heat = runner.get("stable_heat")
    try:
        stable_heat_num = float(stable_heat)
    except (TypeError, ValueError):
        stable_heat_num = None
    if stable_heat_num is not None and stable_heat_num >= 15.0:
        facts.append(_signal("JOURNEY_STABLE_WARM", stable_heat_pct=round(stable_heat_num, 1)))

    factual_codes = {fact["code"] for fact in facts}
    corroborators = {
        "JOURNEY_RETURN_TO_WINNING_COURSE", "JOURNEY_RETURN_TO_WINNING_DISTANCE",
        "JOURNEY_STANDARD_RETURN_WINDOW", "JOURNEY_STABLE_WARM", "JOURNEY_JOCKEY_CHANGE",
    }
    if (
        factual_codes & {"JOURNEY_MARK_AT_OR_BELOW_LAST_WIN", "JOURNEY_MARK_NEAR_LAST_WIN"}
        and len(factual_codes & corroborators) >= 1
    ):
        facts.append(_signal("JOURNEY_HANDICAP_RELEASE_PATTERN", corroborating_facts=sorted(factual_codes & corroborators)))

    return {
        "schema_version": SCHEMA_VERSION,
        "source_contract": SOURCE_CONTRACT,
        "race_id": str(race_id),
        "horse_id": str(horse_id),
        "race_date": str(race_date),
        "source_captured_at": captured_at.isoformat() if captured_at else None,
        "race_off_time_utc": off_time.isoformat() if off_time else None,
        "captured_before_off": bool(captured_at and off_time and captured_at < off_time),
        "history_rows_used": len(valid_history),
        "history_rows_rejected": rejected_history_rows,
        "factual_signals": facts,
        "factual_tags": [fact["code"] for fact in facts],
        "training_eligible": not reasons,
        "ineligibility_reasons": reasons,
        "shadow_only": True,
        "production_prime_consumed": False,
        "model_probability": None,
        "ranking_effect": "NONE",
        "execution_effect": "NONE",
        "promotion_effect": "NONE",
    }
