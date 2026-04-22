from __future__ import annotations

from collections import Counter
from datetime import datetime
from itertools import islice
from typing import Any


def _coerce_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        candidate = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            return None
    return None


def _latest_order_key(row: dict[str, Any], timestamp_fields: tuple[str, ...]) -> tuple:
    for field in timestamp_fields:
        parsed = _coerce_timestamp(row.get(field))
        if parsed is not None:
            return (parsed, str(row.get("id", "")))
    fallback = tuple(str(row.get(field, "")) for field in timestamp_fields)
    return fallback + (str(row.get("id", "")),)


def dedupe_latest_rows(
    rows: list[dict[str, Any]],
    *,
    key_fields: tuple[str, ...],
    timestamp_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    latest: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        if any(part in (None, "") for part in key):
            continue
        current = latest.get(key)
        if current is None or _latest_order_key(row, timestamp_fields) >= _latest_order_key(current, timestamp_fields):
            latest[key] = row
    return list(latest.values())


def dedupe_latest_sigma_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return dedupe_latest_rows(rows, key_fields=("race_id",), timestamp_fields=("created_at", "date"))


def dedupe_latest_truth_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return dedupe_latest_rows(rows, key_fields=("race_id",), timestamp_fields=("generated_at", "race_date"))


def dedupe_latest_rpdc_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return dedupe_latest_rows(rows, key_fields=("race_id", "horse_id"), timestamp_fields=("generated_at", "run_date"))


def review_race_ids(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({str(row.get("race_id")) for row in rows if row.get("race_id") not in (None, "")})


def chunked(values: list[str], size: int = 100) -> list[list[str]]:
    iterator = iter(values)
    chunks: list[list[str]] = []
    while chunk := list(islice(iterator, size)):
        chunks.append(chunk)
    return chunks


def truth_by_race(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["race_id"]: row for row in dedupe_latest_truth_rows(rows) if row.get("race_id")}


def truth_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[Any, dict[str, Any]]]:
    deduped = dedupe_latest_truth_rows(rows)
    by_event = {row["doctrine_event_id"]: row for row in deduped if row.get("doctrine_event_id")}
    by_race = {row["race_id"]: row for row in deduped if row.get("race_id")}
    return {"by_event": by_event, "by_race": by_race}


def truth_for_sigma_row(
    sigma_row: dict[str, Any],
    lookup: dict[str, dict[Any, dict[str, Any]]],
    *,
    stats: dict[str, int] | None = None,
) -> dict[str, Any]:
    doctrine_event_id = sigma_row.get("doctrine_event_id")
    race_id = sigma_row.get("race_id")
    if doctrine_event_id:
        row = lookup.get("by_event", {}).get(doctrine_event_id)
        if row is not None:
            if stats is not None:
                stats["truth_event_matches"] = stats.get("truth_event_matches", 0) + 1
            return row
    if race_id:
        row = lookup.get("by_race", {}).get(race_id)
        if row is not None:
            if stats is not None:
                stats["truth_fallback_matches"] = stats.get("truth_fallback_matches", 0) + 1
            return row
    if stats is not None:
        stats["truth_unmatched"] = stats.get("truth_unmatched", 0) + 1
    return {}


def rpdc_by_selection(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    deduped = dedupe_latest_rpdc_rows(rows)
    return {
        (row["race_id"], row["horse_id"]): row
        for row in deduped
        if row.get("race_id") and row.get("horse_id")
    }


def rpdc_selection_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[Any, dict[str, Any]]]:
    deduped = dedupe_latest_rpdc_rows(rows)
    by_event_selection = {
        (row["doctrine_event_id"], row["horse_id"]): row
        for row in deduped
        if row.get("doctrine_event_id") and row.get("horse_id")
    }
    by_race_selection = {
        (row["race_id"], row["horse_id"]): row
        for row in deduped
        if row.get("race_id") and row.get("horse_id")
    }
    return {"by_event_selection": by_event_selection, "by_race_selection": by_race_selection}


def rpdc_for_sigma_row(
    sigma_row: dict[str, Any],
    rpdc_rows: dict[tuple[str, str], dict[str, Any]] | dict[str, dict[Any, dict[str, Any]]],
    *,
    stats: dict[str, int] | None = None,
) -> dict[str, Any]:
    race_id = sigma_row.get("race_id")
    horse_id = sigma_row.get("horse_id")
    doctrine_event_id = sigma_row.get("doctrine_event_id")
    if not race_id or not horse_id:
        return {"has_cash_window": False, "max_rpdc_release_score": 0.0}
    row = None
    if "by_event_selection" in rpdc_rows:
        if doctrine_event_id:
            row = rpdc_rows["by_event_selection"].get((doctrine_event_id, horse_id))
            if row is not None and stats is not None:
                stats["rpdc_event_matches"] = stats.get("rpdc_event_matches", 0) + 1
        if row is None:
            row = rpdc_rows["by_race_selection"].get((race_id, horse_id))
            if row is not None and stats is not None:
                stats["rpdc_fallback_matches"] = stats.get("rpdc_fallback_matches", 0) + 1
    else:
        row = rpdc_rows.get((race_id, horse_id))
    if not row:
        if stats is not None:
            stats["rpdc_unmatched"] = stats.get("rpdc_unmatched", 0) + 1
        return {"has_cash_window": False, "max_rpdc_release_score": 0.0}
    return {
        "has_cash_window": bool(row.get("rpdc_cash_window_flag")),
        "max_rpdc_release_score": float(row.get("rpdc_release_score") or 0.0),
        "rpdc_tag_count": int(row.get("rpdc_tag_count") or 0),
    }


def rpdc_coverage_metrics(
    sigma_rows: list[dict[str, Any]],
    rpdc_rows: list[dict[str, Any]],
) -> dict[str, int]:
    rpdc_lookup = rpdc_selection_lookup(rpdc_rows)
    event_ids = {
        row.get("doctrine_event_id")
        for row in rpdc_rows
        if row.get("doctrine_event_id") not in (None, "")
    }
    race_ids = {
        row.get("race_id")
        for row in rpdc_rows
        if row.get("race_id") not in (None, "")
    }

    reviewed_sigma_rows = len(sigma_rows)
    reviewed_with_horse_id = 0
    reviewed_in_rpdc_events = 0
    reviewed_with_exact_rpdc_match = 0

    for row in sigma_rows:
        race_id = row.get("race_id")
        doctrine_event_id = row.get("doctrine_event_id")
        horse_id = row.get("horse_id")
        if horse_id not in (None, ""):
            reviewed_with_horse_id += 1
        if doctrine_event_id:
            if doctrine_event_id in event_ids:
                reviewed_in_rpdc_events += 1
        elif race_id and race_id in race_ids:
            reviewed_in_rpdc_events += 1
        if doctrine_event_id and horse_id and (doctrine_event_id, horse_id) in rpdc_lookup["by_event_selection"]:
            reviewed_with_exact_rpdc_match += 1

    return {
        "reviewed_sigma_rows": reviewed_sigma_rows,
        "reviewed_sigma_rows_with_horse_id": reviewed_with_horse_id,
        "reviewed_sigma_rows_in_rpdc_covered_events": reviewed_in_rpdc_events,
        "reviewed_sigma_rows_with_exact_rpdc_match": reviewed_with_exact_rpdc_match,
    }


def contradiction_type(sigma: dict[str, Any], truth: dict[str, Any], rpdc: dict[str, Any]) -> str | None:
    verdict_score = float(sigma.get("verdict_score") or 0)
    confidence_level = sigma.get("confidence_level") or ""
    decision_tier = sigma.get("decision_tier")
    outcome = sigma.get("outcome")

    if verdict_score >= 0.70 and truth.get("blocker_fired"):
        return "strong_model_negative_doctrine"
    if verdict_score < 0.40 and rpdc.get("has_cash_window"):
        return "weak_model_strong_doctrine"
    if truth.get("blocker_fired") and outcome == "WIN":
        return "blocker_fired_horse_won"
    if rpdc.get("has_cash_window") and confidence_level == "low":
        return "rpdc_cash_window_low_model_confidence"
    if decision_tier == "A" and is_weak_a(sigma):
        return "a_tier_weak_place_support"
    return None


def is_weak_a(row: dict[str, Any]) -> bool:
    top_pick_position = row.get("top_pick_position")
    return row.get("decision_tier") == "A" and (
        row.get("confidence_level") == "low"
        or top_pick_position is None
        or int(top_pick_position) > 2
    )


def outcome_rate_rows(rows: list[dict[str, Any]]) -> list[object]:
    total = len(rows)
    if total == 0:
        return [0, 0.0, 0.0, 0.0]
    wins = sum(1 for row in rows if row.get("outcome") == "WIN")
    placed = sum(1 for row in rows if row.get("outcome") == "PLACED")
    misses = sum(1 for row in rows if row.get("outcome") == "MISS")
    return [
        total,
        round(100 * wins / total, 1),
        round(100 * placed / total, 1),
        round(100 * misses / total, 1),
    ]


def top_counts(values: list[str | None], limit: int = 3) -> str:
    counts = Counter((value or "unknown") for value in values)
    if not counts:
        return "none"
    return ", ".join(f"{key} ({count})" for key, count in counts.most_common(limit))


def surface_bucket(track: str | None) -> str:
    if not track:
        return "unknown"
    aw_markers = [
        "(AW)",
        "Dundalk",
        "Kempton (AW)",
        "Southwell (AW)",
        "Wolverhampton",
        "Newcastle (AW)",
        "Lingfield (AW)",
        "Chelmsford",
    ]
    if any(marker in track for marker in aw_markers):
        return "AW"
    return "non_AW_or_unknown"


def sp_bucket(price: Any) -> str:
    if price is None:
        return "unknown"
    try:
        value = float(price)
    except (TypeError, ValueError):
        return "unknown"
    if value <= 3.0:
        return "short_<=3.0"
    if value <= 6.0:
        return "mid_3.01_6.0"
    return "outsider_>6.0"


def doctrine_status_for_type(contradiction_type_name: str, doctrine_rows: list[dict[str, Any]]) -> str:
    doctrine_by_key = {row.get("doctrine_key"): row.get("status") for row in doctrine_rows}
    key_map = {
        "a_tier_weak_place_support": "a_tier_weak_place_watch",
    }
    mapped_key = key_map.get(contradiction_type_name)
    if not mapped_key:
        return "review"
    return doctrine_by_key.get(mapped_key) or "review"
