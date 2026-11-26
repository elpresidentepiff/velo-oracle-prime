from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from src.velo.acca_detector import Leg, build_tickets, validate_leg

NOW = datetime(2026, 11, 26, 10, tzinfo=timezone.utc)


def leg(race="1", horse="101", market="WIN"):
    return Leg(race, horse, "Horse", "Prime", NOW + timedelta(hours=1),
               NOW - timedelta(minutes=5), "rp", NOW - timedelta(minutes=2),
               "rp", True, market, 2.0, NOW - timedelta(minutes=1), "market")


def test_build_is_paper_only_and_clock_injection_is_never_forward_evidence():
    tickets = build_tickets([leg("2", "102"), leg()], leg_count=2, now=NOW)
    assert len(tickets) == 1
    assert tickets[0].combined_decimal_odds == 4.0
    assert tickets[0].label == "OFFLINE_SIMULATION_NOT_FORWARD_EVIDENCE"
    assert [x.race_id for x in tickets[0].legs] == ["1", "2"]


@pytest.mark.parametrize("changes,reason", [
    ({"in_field": False}, "NOT_VERIFIED_IN_FIELD"),
    ({"horse_id": ""}, "IDENTITY_MISSING"),
    ({"evidence_at": NOW + timedelta(seconds=1)}, "LATE_OR_FUTURE_EVIDENCE"),
    ({"odds_at": NOW + timedelta(seconds=1)}, "LATE_OR_FUTURE_EVIDENCE"),
    ({"roster_checked_at": NOW - timedelta(hours=1)}, "STALE_ROSTER"),
    ({"decimal_odds": 1.0}, "INVALID_ODDS"),
    ({"decimal_odds": float("nan")}, "INVALID_ODDS"),
    ({"off_at": NOW}, "RACE_ALREADY_OFF"),
    ({"odds_source": ""}, "PROVENANCE_MISSING"),
    ({"market": "EACH_WAY"}, "UNSUPPORTED_MARKET"),
    ({"model": "FormFav predictions"}, "PROVIDER_MODEL_FORBIDDEN"),
    ({"market": "PLACE"}, "PLACE_TERMS_MISSING"),
    ({"odds_at": datetime(2026, 11, 26, 9)}, "INVALID_TIMESTAMP"),
])
def test_validation_fails_closed(changes, reason):
    assert reason in validate_leg(replace(leg(), **changes), cutoff=NOW)


def test_place_requires_time_safe_terms():
    p = replace(leg(market="PLACE"), place_count=3, place_terms_source="bookmaker", place_terms_at=NOW - timedelta(minutes=1))
    assert validate_leg(p, cutoff=NOW) == ()
    assert "LATE_OR_FUTURE_PLACE_TERMS" in validate_leg(replace(p, place_terms_at=NOW + timedelta(seconds=1)), cutoff=NOW)


def test_no_same_race_combinations_no_duplicate_candidates():
    assert build_tickets([leg("1", "1"), leg("1", "2")], leg_count=2, now=NOW) == ()
    with pytest.raises(ValueError, match="duplicate candidate"):
        build_tickets([leg(), leg()], leg_count=2, now=NOW)


def test_limit_does_not_silently_cherry_pick():
    with pytest.raises(ValueError, match="ticket limit"):
        build_tickets([leg(str(i), str(i)) for i in range(4)], leg_count=2, max_tickets=2, now=NOW)


def test_invalid_candidates_block_all_tickets():
    with pytest.raises(ValueError, match="NOT_VERIFIED_IN_FIELD"):
        build_tickets([leg(), replace(leg("2", "2"), in_field=False)], leg_count=2, now=NOW)
