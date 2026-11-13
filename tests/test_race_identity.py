"""#189 regression: US racing date vs UTC key collision (Remington Park R4, 12 Nov 2026).

The fixtures below are the two production rows exactly as stored on 13 Nov 2026 01:43 UTC
(`formfav_races` + `formfav_runner_form`), plus the corrected card a fixed worker stores.
"""
from __future__ import annotations

from datetime import UTC, datetime

from src.velo.race_identity import (
    BLOCKED_LABEL,
    RACECARD_MISMATCH,
    VERIFIED,
    canonical_race_key,
    local_race_date,
    parse_race_key,
    verify_race_identity,
    verify_selection,
)

CHICAGO = "America/Chicago"
FIELD_12 = [  # actual 12 Nov R4 Maiden Special Weight entries, in saddlecloth order
    "Imatexasbeauty", "Yes Julia", "Brandy Foot", "Wicked One", "It's Time For Zima",
    "Reckless Ride", "Conqueress", "Lady Reyna", "Black Velvet Rose", "Vinalia",
]
FIELD_13 = ["Bendelene", "Forever Safe", "Stone Cold Lover", "Miss Arlington", "Music Mistress", "Woman's Intuition"]


def _runners(key, names, *, updated_at, scratched=()):
    return [
        {"provider_race_key": key, "runner_number": i, "horse_name": n, "scratched": n in scratched,
         "updated_at": updated_at}
        for i, n in enumerate(names, start=1)
    ]


# --- production rows (legacy, UTC-date keyed) -------------------------------------------------
LEGACY_12 = {
    "provider_race_key": "formfav:us:2026-11-12:remington_park:r4", "race_date": "2026-11-12",
    "start_time": "2026-11-12 01:54:00+00", "timezone": CHICAGO, "race_number": 4,
    # meetings entry for the 11 Nov card (off 12 Nov 01:54 UTC), class CLAIMING
    "metadata": {"raceNumber": 4, "startTime": "2026-11-12T01:54:00Z", "raceClass": "3YO+ CLM",
                 "numberOfRunners": 8, "timezone": CHICAGO},
    # racecard for the 12 Nov card (off 13 Nov 01:54 UTC)
    "form_meta": {"raceNumber": 4, "startTime": "2026-11-13T01:54:00Z", "raceClass": "MAIDEN SPECIAL WEIGHT",
                  "numberOfRunners": 10, "timezone": CHICAGO, "date": "2026-11-12"},
}
LEGACY_12_RUNNERS = _runners(LEGACY_12["provider_race_key"], FIELD_12, updated_at="2026-11-12T04:52:44+00:00")

LEGACY_13 = {
    "provider_race_key": "formfav:us:2026-11-13:remington_park:r4", "race_date": "2026-11-13",
    "start_time": "2026-11-13 01:54:00+00", "timezone": CHICAGO, "race_number": 4,
    "metadata": {"raceNumber": 4, "startTime": "2026-11-13T01:54:00Z", "raceClass": "MAIDEN SPECIAL WEIGHT",
                 "numberOfRunners": 10, "timezone": CHICAGO},
    "form_meta": {"raceNumber": 4, "startTime": "2026-11-14T01:54:00Z", "raceClass": "CLAIMING $20,000",
                  "numberOfRunners": 6, "timezone": CHICAGO, "date": "2026-11-13"},
}
LEGACY_13_RUNNERS = _runners(LEGACY_13["provider_race_key"], FIELD_13, updated_at="2026-11-13T01:43:44+00:00")

# --- what a fixed worker stores for the race that actually ran at 01:54 UTC on 13 Nov ----------
FIXED_12 = {
    **LEGACY_12,
    "start_time": "2026-11-13T01:54:00+00:00",
    "metadata": {"raceNumber": 4, "startTime": "2026-11-13T01:54:00Z", "raceClass": "MAIDEN SPECIAL WEIGHT",
                 "numberOfRunners": 10, "timezone": CHICAGO},
}
FIXED_12_RUNNERS = _runners(
    FIXED_12["provider_race_key"], FIELD_12, updated_at="2026-11-13T01:30:00+00:00", scratched=("Reckless Ride",),
)
PRE_OFF = datetime(2026, 11, 13, 1, 40, tzinfo=UTC)


# ---- mandatory regression: Remington Park R4 ------------------------------------------------

def test_remington_r4_local_racing_date_is_12_november() -> None:
    assert local_race_date("2026-11-13T01:54:00Z", CHICAGO) == "2026-11-12"
    assert canonical_race_key("us", "2026-11-12", "Remington Park", 4) == "formfav:us:2026-11-12:remington_park:r4"
    assert parse_race_key("formfav:us:2026-11-12:remington_park:r4") == {
        "country": "us", "race_date": "2026-11-12", "slug": "remington_park", "race_number": 4,
    }


def test_remington_r4_resolves_to_the_verified_maiden_special_weight() -> None:
    ident = verify_race_identity(FIXED_12, FIXED_12_RUNNERS, now=PRE_OFF)
    assert ident["status"] == VERIFIED, ident["reasons"]
    assert ident["provider_race_key"] == "formfav:us:2026-11-12:remington_park:r4"
    assert ident["local_race_date"] == "2026-11-12"
    assert ident["start_time_utc"] == "2026-11-13T01:54:00+00:00"  # R4, 01:54 GMT
    assert ident["race_number"] == 4
    assert ident["field_size"] == 10  # original entries
    assert [r["name"] for r in ident["non_runners"]] == ["Reckless Ride"]
    assert len(ident["active_runners"]) == 9
    assert ident["warnings"] == []  # class and runner count agree once both sources are one race


def test_remington_r4_historical_picks_are_certified_only_on_the_verified_card() -> None:
    ident = verify_race_identity(FIXED_12, FIXED_12_RUNNERS, now=PRE_OFF)
    formfav = verify_selection(ident, "It's Time For Zima", 5)
    world = verify_selection(ident, "Vinalia")
    assert formfav["status"] == VERIFIED and formfav["selection"] == {"number": 5, "name": "It's Time For Zima"}
    assert world["status"] == VERIFIED and world["selection"]["number"] == 10
    # the horses the dashboard showed are not in this race
    for wrong in ("Stone Cold Lover", "Woman's Intuition"):
        out = verify_selection(ident, wrong)
        assert out["status"] == "NOT_IN_FIELD" and out["label"] == BLOCKED_LABEL and out["selection"] is None
    nr = verify_selection(ident, "Reckless Ride", 6)
    assert nr["status"] == "NON_RUNNER" and nr["label"] == BLOCKED_LABEL


def test_remington_r4_runner_number_must_match_too() -> None:
    ident = verify_race_identity(FIXED_12, FIXED_12_RUNNERS, now=PRE_OFF)
    assert verify_selection(ident, "It's Time For Zima", 7)["status"] == "NOT_IN_FIELD"


def test_both_production_rows_are_blocked_as_racecard_mismatch() -> None:
    now = PRE_OFF
    a = verify_race_identity(LEGACY_12, LEGACY_12_RUNNERS, now=now)
    b = verify_race_identity(LEGACY_13, LEGACY_13_RUNNERS, now=now)
    for ident in (a, b):
        assert ident["status"] == RACECARD_MISMATCH
        assert "START_TIME_CONFLICT" in ident["reasons"] and "RACE_DATE_COLLISION" in ident["reasons"]
        assert ident["label"] == BLOCKED_LABEL
    # the picks that were displayed for "13 Nov R4 01:54" are blocked, and so are the right ones,
    # because on these rows nothing proves which race the field belongs to
    for ident, pick in ((b, "Stone Cold Lover"), (b, "Woman's Intuition"), (a, "Vinalia"), (a, "It's Time For Zima")):
        out = verify_selection(ident, pick)
        assert out["status"] == RACECARD_MISMATCH and out["selection"] is None and out["label"] == BLOCKED_LABEL
        assert out["original_pick"]["name"] == pick  # preserved for audit, never shown


def test_production_card_checked_21h_before_the_off_cannot_certify_scratchings() -> None:
    """The stored card is from 12 Nov 04:52 UTC and does not know Reckless Ride was scratched at 20:43."""
    stale = {**FIXED_12}
    ident = verify_race_identity(stale, LEGACY_12_RUNNERS, now=PRE_OFF)
    assert ident["status"] == RACECARD_MISMATCH and ident["reasons"] == ["RACECARD_STALE"]
    # settlement may still identify the race from the same evidence (the result carries the scratching)
    settle = verify_race_identity(stale, LEGACY_12_RUNNERS, now=PRE_OFF, require_fresh_racecard=False)
    assert settle["status"] == VERIFIED


# ---- other overnight / date-boundary cases ----------------------------------------------------

def _race(key, off, tz, *, form_off=None, meta_off=None, form_date=None, race_no=1):
    return {
        "provider_race_key": key, "race_date": parse_race_key(key)["race_date"], "race_number": race_no,
        "start_time": meta_off or off, "timezone": tz,
        "metadata": {"raceNumber": race_no, "startTime": meta_off or off, "timezone": tz},
        "form_meta": {"raceNumber": race_no, "startTime": form_off or off, "timezone": tz,
                      **({"date": form_date} if form_date else {})},
    }


def _fresh(key, n=6):
    return _runners(key, [f"H{i}" for i in range(n)], updated_at="2026-11-13T00:00:00+00:00")


NOW = datetime(2026, 11, 13, 0, 30, tzinfo=UTC)


def test_midnight_crossing_west_coast_race_keeps_its_local_date() -> None:
    # Del Mar-style 21:30 Pacific on 12 Nov = 05:30 UTC on 13 Nov
    off = "2026-11-13T05:30:00Z"
    assert local_race_date(off, "America/Los_Angeles") == "2026-11-12"
    key = "formfav:us:2026-11-12:del_mar:r9"
    assert verify_race_identity(_race(key, off, "America/Los_Angeles", race_no=9), _fresh(key), now=NOW)["status"] == VERIFIED
    utc_keyed = "formfav:us:2026-11-13:del_mar:r9"
    ident = verify_race_identity(_race(utc_keyed, off, "America/Los_Angeles", race_no=9), _fresh(utc_keyed), now=NOW)
    assert ident["reasons"] == ["RACE_DATE_COLLISION"]


def test_13_and_14_november_collision_on_the_same_key_is_rejected() -> None:
    key = "formfav:us:2026-11-13:remington_park:r4"
    race = _race(key, "2026-11-13T01:54:00Z", CHICAGO, meta_off="2026-11-13T01:54:00Z",
                 form_off="2026-11-14T01:54:00Z", form_date="2026-11-13", race_no=4)
    ident = verify_race_identity(race, _fresh(key), now=NOW)
    assert ident["status"] == RACECARD_MISMATCH
    assert {"START_TIME_CONFLICT", "RACE_DATE_COLLISION"} <= set(ident["reasons"])


def test_early_australian_race_belongs_to_the_next_local_date() -> None:
    off = "2026-11-12T23:30:00Z"  # 10:30 Sydney on 13 Nov
    assert local_race_date(off, "Australia/Sydney") == "2026-11-13"
    key = "formfav:au:2026-11-13:randwick:r1"
    assert verify_race_identity(_race(key, off, "Australia/Sydney"), _fresh(key),
                                now=datetime(2026, 11, 12, 22, tzinfo=UTC))["status"] == VERIFIED


def test_a_late_off_time_change_is_a_warning_not_a_block() -> None:
    key = "formfav:us:2026-11-12:aqueduct:r1"
    race = _race(key, "2026-11-12T17:00:00Z", "America/New_York", form_off="2026-11-12T17:12:00Z")
    ident = verify_race_identity(race, _fresh(key), now=datetime(2026, 11, 12, 16, tzinfo=UTC))
    assert ident["status"] == VERIFIED and ident["warnings"] == ["OFF_TIME_MOVED"]


def test_form_date_and_race_number_contradictions_are_hard_errors() -> None:
    key = "formfav:us:2026-11-12:aqueduct:r1"
    race = _race(key, "2026-11-12T17:00:00Z", "America/New_York", form_date="2026-11-13")
    assert "FORM_DATE_CONFLICT" in verify_race_identity(race, _fresh(key), now=datetime(2026, 11, 12, 16, tzinfo=UTC))["reasons"]
    race = _race(key, "2026-11-12T17:00:00Z", "America/New_York")
    race["form_meta"]["raceNumber"] = 2
    assert "RACE_NUMBER_CONFLICT" in verify_race_identity(race, _fresh(key), now=datetime(2026, 11, 12, 16, tzinfo=UTC))["reasons"]


def test_duplicate_runner_ids_missing_runners_and_missing_evidence_block() -> None:
    key = "formfav:us:2026-11-12:aqueduct:r1"
    race = _race(key, "2026-11-12T17:00:00Z", "America/New_York")
    now = datetime(2026, 11, 12, 16, tzinfo=UTC)
    dup = _fresh(key, 3) + [{**_fresh(key, 1)[0]}]
    assert "RUNNER_ID_COLLISION" in verify_race_identity(race, dup, now=now)["reasons"]
    assert "RUNNERS_MISSING" in verify_race_identity(race, [], now=now)["reasons"]
    no_card = {**race, "form_meta": None}
    assert "RACECARD_MISSING" in verify_race_identity(no_card, _fresh(key), now=now)["reasons"]
    no_tz = {**race, "timezone": None, "metadata": {"raceNumber": 1, "startTime": race["start_time"]},
             "form_meta": {"raceNumber": 1, "startTime": race["start_time"]}}
    assert "MISSING_TIMEZONE" in verify_race_identity(no_tz, _fresh(key), now=now)["reasons"]
    assert verify_race_identity({"provider_race_key": "bogus"}, [], now=now)["status"] == RACECARD_MISMATCH


def test_every_scratched_runner_is_removed_from_actionable_selections() -> None:
    key = "formfav:us:2026-11-12:aqueduct:r1"
    race = _race(key, "2026-11-12T17:00:00Z", "America/New_York")
    runners = _runners(key, ["A", "B", "C"], updated_at="2026-11-12T16:00:00+00:00", scratched=("B",))
    ident = verify_race_identity(race, runners, now=datetime(2026, 11, 12, 16, 30, tzinfo=UTC))
    assert [r["name"] for r in ident["active_runners"]] == ["A", "C"]
    assert verify_selection(ident, "B")["status"] == "NON_RUNNER"
    assert verify_selection(ident, "A (USA)")["status"] == VERIFIED  # country tag ignored
