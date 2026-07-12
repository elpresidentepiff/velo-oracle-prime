"""Tests for src/velo/learning/identity_resolver.py (LEARNING-LOOP-01A Phase 2)."""

from src.velo.learning.identity_resolver import (
    HORSE_METHOD_AMBIGUOUS,
    HORSE_METHOD_EXACT_ID,
    HORSE_METHOD_NAME_IN_RACE,
    HORSE_METHOD_UNRESOLVED,
    RACE_METHOD_AMBIGUOUS,
    RACE_METHOD_COURSE_DATE_EXACT_TIME,
    RACE_METHOD_COURSE_DATE_TIME_FALLBACK,
    RACE_METHOD_EXACT_ID,
    RACE_METHOD_UNRESOLVED,
    normalise_name,
    parse_time_to_minutes,
    resolve_horse,
    resolve_race,
)


def _cand(race_id, course, date, off, runners):
    return {"race_id": race_id, "course": course, "date": date, "off": off, "runners": runners}


def _runner(horse_id, horse_name):
    return {"horse_id": horse_id, "horse_name": horse_name}


# ---------------------------------------------------------------------------
# time parsing: 12h/24h/dot-time
# ---------------------------------------------------------------------------


def test_parse_time_24h_with_seconds():
    assert parse_time_to_minutes("14:35:00") == 14 * 60 + 35


def test_parse_time_24h_no_seconds():
    assert parse_time_to_minutes("14:35") == 14 * 60 + 35


def test_parse_time_racing_dot_time_afternoon():
    assert parse_time_to_minutes("1.35") == 13 * 60 + 35


def test_parse_time_racing_dot_time_already_24h():
    assert parse_time_to_minutes("14.35") == 14 * 60 + 35


def test_parse_time_unparseable_returns_none():
    assert parse_time_to_minutes("not-a-time") is None
    assert parse_time_to_minutes(None) is None


# ---------------------------------------------------------------------------
# country-suffix name normalisation
# ---------------------------------------------------------------------------


def test_normalise_name_strips_country_suffix():
    assert normalise_name("Fines Ailes (FR)") == normalise_name("Fines Ailes")


def test_normalise_name_case_and_punctuation_insensitive():
    assert normalise_name("Ruler'S Pride") == normalise_name("ruler's pride")


# ---------------------------------------------------------------------------
# race resolution priority chain
# ---------------------------------------------------------------------------


def test_race_resolves_by_exact_id_first_even_if_time_mismatches():
    pred = {"race_id": "rp_AYR_20260520_1.42", "course": "AYR", "race_date": "2026-05-20", "off_time": "1.42"}
    candidates = [_cand("rp_AYR_20260520_1.42", "AYR", "2026-05-20", "9.99", [])]
    res = resolve_race(pred, candidates)
    assert res.method == RACE_METHOD_EXACT_ID
    assert res.resolved_race_id == "rp_AYR_20260520_1.42"
    assert res.confidence == "exact"


def test_race_resolves_by_course_date_exact_time_fallback():
    pred = {"race_id": "not_present_anywhere", "course": "Ascot", "race_date": "2026-05-20", "off_time": "1.35"}
    candidates = [_cand("rac_999", "Ascot", "2026-05-20", "1.35", [])]
    res = resolve_race(pred, candidates)
    assert res.method == RACE_METHOD_COURSE_DATE_EXACT_TIME
    assert res.resolved_race_id == "rac_999"
    assert res.confidence == "high"


def test_race_resolves_via_3min_fallback_when_off_time_drifts():
    pred = {"race_id": "missing", "course": "Chester", "race_date": "2026-05-20", "off_time": "2.10"}
    candidates = [_cand("rac_1", "Chester", "2026-05-20", "2.12", [])]  # 2 min drift
    res = resolve_race(pred, candidates)
    assert res.method == RACE_METHOD_COURSE_DATE_TIME_FALLBACK
    assert res.resolved_race_id == "rac_1"
    assert res.confidence == "low"


def test_race_fallback_beyond_3min_is_unresolved_not_guessed():
    pred = {"race_id": "missing", "course": "Chester", "race_date": "2026-05-20", "off_time": "2.10"}
    candidates = [_cand("rac_1", "Chester", "2026-05-20", "2.20", [])]  # 10 min drift
    res = resolve_race(pred, candidates)
    assert res.method == RACE_METHOD_UNRESOLVED
    assert res.resolved_race_id is None


def test_race_ambiguous_multiple_exact_time_candidates_blocked():
    pred = {"race_id": "missing", "course": "Chester", "race_date": "2026-05-20", "off_time": "2.10"}
    candidates = [
        _cand("rac_1", "Chester", "2026-05-20", "2.10", []),
        _cand("rac_2", "Chester", "2026-05-20", "2.10", []),
    ]
    res = resolve_race(pred, candidates)
    assert res.method == RACE_METHOD_AMBIGUOUS
    assert res.resolved_race_id is None
    assert res.ambiguity_reason == "MULTIPLE_EXACT_TIME_CANDIDATES"
    assert res.candidate_count == 2


def test_race_ambiguous_multiple_fallback_candidates_blocked():
    pred = {"race_id": "missing", "course": "Chester", "race_date": "2026-05-20", "off_time": "2.10"}
    candidates = [
        _cand("rac_1", "Chester", "2026-05-20", "2.11", []),
        _cand("rac_2", "Chester", "2026-05-20", "2.12", []),
    ]
    res = resolve_race(pred, candidates)
    assert res.method == RACE_METHOD_AMBIGUOUS
    assert res.ambiguity_reason == "MULTIPLE_FALLBACK_TIME_CANDIDATES"


def test_race_no_candidate_unresolved():
    pred = {"race_id": "missing", "course": "Ascot", "race_date": "2026-05-20", "off_time": "1.35"}
    res = resolve_race(pred, [])
    assert res.method == RACE_METHOD_UNRESOLVED
    assert res.candidate_count == 0


def test_race_id_alias_used_when_registered():
    pred = {"race_id": "old_id", "course": "Ascot", "race_date": "2026-05-20", "off_time": "1.35"}
    candidates = [_cand("new_id", "Ascot", "2026-05-20", "1.35", [])]
    res = resolve_race(pred, candidates, race_id_aliases={"old_id": "new_id"})
    assert res.method.endswith("ALIAS")
    assert res.resolved_race_id == "new_id"


def test_race_numeric_vs_rp_scheme_ids_join_correctly_by_race_id():
    """Different result-source namespaces (numeric RP id vs rp_ scheme vs
    rac_ scheme) all resolve fine as long as the exact string matches --
    the resolver does not care about the scheme itself."""
    pred = {"race_id": "922402", "course": "Chester", "race_date": "2026-07-11", "off_time": "1.35"}
    candidates = [_cand("922402", "Chester", "2026-07-11", "1.35", [])]
    res = resolve_race(pred, candidates)
    assert res.method == RACE_METHOD_EXACT_ID


def test_duplicate_candidate_race_ids_block_as_ambiguous():
    """Two candidates sharing the same race_id string must never resolve
    silently by insertion order (setdefault-first-wins) -- a duplicate
    exact race_id is a data-quality defect and must block the race as
    AMBIGUOUS rather than fabricate a result from an arbitrary match."""
    pred = {"race_id": "dup_1", "course": "Ascot", "race_date": "2026-05-20", "off_time": "1.35"}
    candidates = [
        _cand("dup_1", "Ascot", "2026-05-20", "1.35", []),
        _cand("dup_1", "Ascot", "2026-05-20", "1.35", []),
    ]
    res = resolve_race(pred, candidates)
    assert res.method == RACE_METHOD_AMBIGUOUS
    assert res.resolved_race_id is None
    assert res.ambiguity_reason == "DUPLICATE_EXACT_RACE_ID"
    assert res.candidate_count == 2


def test_duplicate_aliased_race_id_blocks_as_ambiguous():
    pred = {"race_id": "old_id", "course": "Ascot", "race_date": "2026-05-20", "off_time": "1.35"}
    candidates = [
        _cand("new_id", "Ascot", "2026-05-20", "1.35", []),
        _cand("new_id", "Ascot", "2026-05-20", "1.35", []),
    ]
    res = resolve_race(pred, candidates, race_id_aliases={"old_id": "new_id"})
    assert res.method == RACE_METHOD_AMBIGUOUS
    assert res.ambiguity_reason == "DUPLICATE_ALIASED_RACE_ID"


def test_duplicate_exact_horse_id_blocks_as_ambiguous():
    race = {"runners": [_runner("hrs_1", "Same Horse"), _runner("hrs_1", "Same Horse Dup")]}
    res = resolve_horse("hrs_1", "Same Horse", race)
    assert res.method == HORSE_METHOD_AMBIGUOUS
    assert res.resolved_horse_id is None
    assert res.ambiguity_reason == "DUPLICATE_EXACT_HORSE_ID"


def test_duplicate_aliased_horse_id_blocks_as_ambiguous():
    race = {"runners": [_runner("hrs_new", "A"), _runner("hrs_new", "B")]}
    res = resolve_horse("hrs_old", "A", race, horse_id_aliases={"hrs_old": "hrs_new"})
    assert res.method == HORSE_METHOD_AMBIGUOUS
    assert res.ambiguity_reason == "DUPLICATE_ALIASED_HORSE_ID"


# ---------------------------------------------------------------------------
# horse resolution
# ---------------------------------------------------------------------------


def test_horse_resolves_by_exact_id():
    race = {"runners": [_runner("hrs_1", "Same Horse"), _runner("hrs_2", "Other Horse")]}
    res = resolve_horse("hrs_1", "Same Horse", race)
    assert res.method == HORSE_METHOD_EXACT_ID
    assert res.resolved_horse_id == "hrs_1"


def test_horse_resolves_by_alias_when_registered():
    race = {"runners": [_runner("hrs_new", "Renamed Horse")]}
    res = resolve_horse("hrs_old", "Renamed Horse", race, horse_id_aliases={"hrs_old": "hrs_new"})
    assert res.method.endswith("ALIAS")
    assert res.resolved_horse_id == "hrs_new"


def test_horse_falls_back_to_normalised_name_with_country_suffix():
    race = {"runners": [_runner("hrs_9", "Fines Ailes")]}
    res = resolve_horse("unknown_id", "Fines Ailes (FR)", race)
    assert res.method == HORSE_METHOD_NAME_IN_RACE
    assert res.resolved_horse_id == "hrs_9"


def test_horse_no_match_unresolved():
    race = {"runners": [_runner("hrs_9", "Some Other Horse")]}
    res = resolve_horse("unknown_id", "Nowhere Horse", race)
    assert res.method == HORSE_METHOD_UNRESOLVED
    assert res.resolved_horse_id is None


def test_horse_ambiguous_duplicate_names_blocked():
    race = {"runners": [_runner("hrs_1", "Twin"), _runner("hrs_2", "Twin")]}
    res = resolve_horse("unknown_id", "Twin", race)
    assert res.method == HORSE_METHOD_AMBIGUOUS
    assert res.resolved_horse_id is None
    assert res.candidate_count == 2
