"""
Canonical identity resolver — LEARNING-LOOP-01A Phase 2.

Pure resolution logic. Given a prediction-side race stub and a list of
candidate result-side races (already handed to it by
`result_source_selector` — this module is agnostic to *where* those rows
came from), resolves race and horse identity through a strict priority
chain. Never guesses: ambiguous or unresolved cases are returned as such,
not silently defaulted to a "best effort" match.

Race resolution priority:
    1. exact canonical race_id
    2. registered race_id alias
    3. canonical course + date + exact off-time
    4. canonical course + date + unique +/-3-minute off-time fallback
    5. otherwise UNRESOLVED / AMBIGUOUS

Horse resolution priority (within an already-resolved race):
    1. exact canonical horse_id
    2. registered horse_id alias
    3. exact normalised name within the resolved race
    4. otherwise UNRESOLVED / AMBIGUOUS

No alias tables are written by this module (LEARNING-LOOP-01A Phase 2
scope: read-only resolution only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

RACE_METHOD_EXACT_ID = "EXACT_RACE_ID"
RACE_METHOD_ALIAS = "REGISTERED_RACE_ID_ALIAS"
RACE_METHOD_COURSE_DATE_EXACT_TIME = "COURSE_DATE_EXACT_TIME"
RACE_METHOD_COURSE_DATE_TIME_FALLBACK = "COURSE_DATE_TIME_FALLBACK_3MIN"
RACE_METHOD_UNRESOLVED = "UNRESOLVED"
RACE_METHOD_AMBIGUOUS = "AMBIGUOUS"

HORSE_METHOD_EXACT_ID = "EXACT_HORSE_ID"
HORSE_METHOD_ALIAS = "REGISTERED_HORSE_ID_ALIAS"
HORSE_METHOD_NAME_IN_RACE = "NORMALISED_NAME_IN_RESOLVED_RACE"
HORSE_METHOD_UNRESOLVED = "UNRESOLVED"
HORSE_METHOD_AMBIGUOUS = "AMBIGUOUS"


def normalise_name(name: str | None) -> str:
    """Lowercase, strip a trailing country-suffix e.g. '(IRE)', strip non-alnum."""
    if not name:
        return ""
    name = re.sub(r"\s*\([A-Za-z]{2,4}\)\s*$", "", name.strip())
    return re.sub(r"[^a-z0-9]", "", name.lower())


def parse_time_to_minutes(value: Any) -> int | None:
    """Parse ISO 24h ("14:35:00" / "14:35"), or racing dot-time ("1.35"
    meaning 13:35 for an afternoon race) into minutes-since-midnight.
    Returns None if unparseable — callers must never guess a time."""
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    m = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})$", value)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.match(r"^(\d{1,2}):(\d{2})$", value)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.match(r"^(\d{1,2})\.(\d{2})$", value)
    if m:
        hh = int(m.group(1))
        if hh < 10:  # racing dot-time convention: 1.xx-9.xx are afternoon/evening
            hh += 12
        return hh * 60 + int(m.group(2))
    return None


@dataclass
class RaceResolution:
    resolved_race_id: str | None
    method: str
    confidence: str  # "exact" | "high" | "low" | "none"
    candidate_count: int
    source_race_ids: list[str] = field(default_factory=list)
    ambiguity_reason: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def is_resolved(self) -> bool:
        return self.resolved_race_id is not None


@dataclass
class HorseResolution:
    resolved_horse_id: str | None
    method: str
    confidence: str
    candidate_count: int
    source_horse_ids: list[str] = field(default_factory=list)
    ambiguity_reason: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def is_resolved(self) -> bool:
        return self.resolved_horse_id is not None


def _candidate_time_minutes(r: dict) -> int | None:
    return parse_time_to_minutes(r.get("off") or r.get("off_time") or r.get("time"))


def _candidate_date(r: dict) -> Any:
    return r.get("date") or r.get("race_date")


def resolve_race(
    pred_race: dict,
    candidate_races: list[dict],
    race_id_aliases: dict[str, str] | None = None,
) -> RaceResolution:
    """
    pred_race: {"race_id", "course", "race_date", "off_time"}
    candidate_races: result-side race dicts, each with "race_id", "course",
        a date field ("date" or "race_date") and a time field
        ("off" / "off_time" / "time").
    """
    race_id_aliases = race_id_aliases or {}
    pred_id = pred_race.get("race_id")
    by_id: dict[str, dict] = {}
    for r in candidate_races:
        rid = r.get("race_id")
        if rid:
            by_id.setdefault(rid, r)

    if pred_id in by_id:
        return RaceResolution(
            pred_id, RACE_METHOD_EXACT_ID, "exact", 1, [pred_id], provenance={"matched_on": "race_id"}
        )

    aliased = race_id_aliases.get(pred_id) if pred_id else None
    if aliased and aliased in by_id:
        return RaceResolution(
            aliased,
            RACE_METHOD_ALIAS,
            "exact",
            1,
            [aliased],
            provenance={"matched_on": "race_id_alias", "alias_of": pred_id},
        )

    course = normalise_name(pred_race.get("course"))
    date = pred_race.get("race_date")
    off_minutes = parse_time_to_minutes(pred_race.get("off_time"))

    if off_minutes is not None:
        exact_time_matches = [
            r
            for r in candidate_races
            if normalise_name(r.get("course")) == course
            and _candidate_date(r) == date
            and _candidate_time_minutes(r) == off_minutes
        ]
        if len(exact_time_matches) == 1:
            rid = exact_time_matches[0].get("race_id")
            return RaceResolution(
                rid,
                RACE_METHOD_COURSE_DATE_EXACT_TIME,
                "high",
                1,
                [rid],
                provenance={"matched_on": "course_date_exact_time"},
            )
        if len(exact_time_matches) > 1:
            return RaceResolution(
                None,
                RACE_METHOD_AMBIGUOUS,
                "none",
                len(exact_time_matches),
                [r.get("race_id") for r in exact_time_matches],
                ambiguity_reason="MULTIPLE_EXACT_TIME_CANDIDATES",
            )

        near_matches = [
            r
            for r in candidate_races
            if normalise_name(r.get("course")) == course
            and _candidate_date(r) == date
            and _candidate_time_minutes(r) is not None
            and abs(_candidate_time_minutes(r) - off_minutes) <= 3
        ]
        if len(near_matches) == 1:
            rid = near_matches[0].get("race_id")
            return RaceResolution(
                rid,
                RACE_METHOD_COURSE_DATE_TIME_FALLBACK,
                "low",
                1,
                [rid],
                provenance={"matched_on": "course_date_time_fallback_3min"},
            )
        if len(near_matches) > 1:
            return RaceResolution(
                None,
                RACE_METHOD_AMBIGUOUS,
                "none",
                len(near_matches),
                [r.get("race_id") for r in near_matches],
                ambiguity_reason="MULTIPLE_FALLBACK_TIME_CANDIDATES",
            )

    return RaceResolution(None, RACE_METHOD_UNRESOLVED, "none", 0, [], ambiguity_reason="NO_CANDIDATE_FOUND")


def resolve_horse(
    pred_horse_id: str | None,
    pred_horse_name: str | None,
    resolved_race: dict,
    horse_id_aliases: dict[str, str] | None = None,
) -> HorseResolution:
    horse_id_aliases = horse_id_aliases or {}
    runners = resolved_race.get("runners", [])
    by_id: dict[str, dict] = {}
    for r in runners:
        hid = r.get("horse_id")
        if hid:
            by_id.setdefault(hid, r)

    if pred_horse_id and pred_horse_id in by_id:
        return HorseResolution(pred_horse_id, HORSE_METHOD_EXACT_ID, "exact", 1, [pred_horse_id])

    aliased = horse_id_aliases.get(pred_horse_id) if pred_horse_id else None
    if aliased and aliased in by_id:
        return HorseResolution(
            aliased,
            HORSE_METHOD_ALIAS,
            "exact",
            1,
            [aliased],
            provenance={"alias_of": pred_horse_id},
        )

    norm_target = normalise_name(pred_horse_name)
    name_matches = (
        [r for r in runners if normalise_name(r.get("horse_name") or r.get("horse")) == norm_target]
        if norm_target
        else []
    )
    if len(name_matches) == 1:
        hid = name_matches[0].get("horse_id")
        return HorseResolution(
            hid,
            HORSE_METHOD_NAME_IN_RACE,
            "high",
            1,
            [hid],
            provenance={"matched_on": "normalised_name"},
        )
    if len(name_matches) > 1:
        return HorseResolution(
            None,
            HORSE_METHOD_AMBIGUOUS,
            "none",
            len(name_matches),
            [r.get("horse_id") for r in name_matches],
            ambiguity_reason="MULTIPLE_NAME_CANDIDATES",
        )

    return HorseResolution(None, HORSE_METHOD_UNRESOLVED, "none", 0, [], ambiguity_reason="NO_CANDIDATE_FOUND")
