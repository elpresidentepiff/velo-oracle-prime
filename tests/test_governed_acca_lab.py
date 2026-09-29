import copy
import json
from datetime import datetime
from pathlib import Path

import pytest

import scripts.research.governed_acca_lab as lab
from scripts.research.governed_acca_lab import (
    build_forward_acca_packet,
    build_holdout_multiplicity_evidence,
    build_oracle_ceiling,
    promotion_gate,
    settle_forward_packet,
    write_canonical_truth_artifact,
    write_immutable_forward_packet,
    write_immutable_holdout_evidence,
    write_immutable_settlement,
)

DATE = "2026-09-29"
NOW = datetime.fromisoformat("2026-09-29T09:00:00+01:00")
CARD_PATH = None
EVIDENCE_ROOT = None
SETTLEMENT_CASE = 0


@pytest.fixture(autouse=True)
def trusted_clock(monkeypatch, tmp_path):
    global CARD_PATH, EVIDENCE_ROOT, SETTLEMENT_CASE
    monkeypatch.setattr(lab, "_utc_now", lambda: NOW)
    EVIDENCE_ROOT = tmp_path / "anchored"
    SETTLEMENT_CASE = 0
    card_path = tmp_path / "authoritative_card.json"
    schedule = [
        {"race_id": f"r{i}", "off_ts": f"{DATE}T{10 + i:02d}:00:00+01:00"}
        for i in range(1, 10)
    ]
    card_path.write_text(json.dumps({
        "race_date": DATE, "timezone": "Europe/London",
        "provenance": {"source": "TEST_AUTHORITATIVE_CARD_FIXTURE"}, "races": schedule,
    }), encoding="utf-8")
    CARD_PATH = card_path


def candidate(race, horse, *, role="BANKER", probability=0.5, odds=2.0, venue=None, family=None):
    return {
        "race_id": race,
        "horse_id": horse,
        "horse": horse.title(),
        "off_ts": f"{DATE}T{10 + int(race[1:]):02d}:00:00+01:00",
        "selection_ts": f"{DATE}T08:00:00+01:00",
        "role": role,
        "model_name": "CAPTAIN",
        "model_version": "c1",
        "model_family": family or f"family-{race}",
        "probability": probability,
        "score": probability,
        "captured_odds_dec": odds,
        "odds_capture_ts": f"{DATE}T08:30:00+01:00",
        "price_source": "FROZEN_SNAPSHOT",
        "venue": venue or f"venue-{race}",
        "meeting_id": venue or f"meeting-{race}",
        "race_type": "FLAT",
        "trainer_id": f"trainer-{race}",
        "jockey_id": f"jockey-{race}",
        "comparators": {
            "market_favourite": {"horse_id": f"fav-{race}"},
            "production": {"horse_id": f"prod-{race}"},
            "random_market_weighted": {"horse_id": f"rnd-{race}"},
            "top_probability": {"horse_id": horse},
        },
    }


def truth(race, horse, outcome="WIN", *, source="truth-hash", date=DATE):
    values = {
        "WIN": ("FINISHED", "1", "SETTLED", True),
        "LOSS": ("FINISHED", "2", "SETTLED", False),
        "F": ("TERMINAL", "F", "SETTLED", False),
        "PU": ("TERMINAL", "PU", "SETTLED", False),
        "UR": ("TERMINAL", "UR", "SETTLED", False),
        "BD": ("TERMINAL", "BD", "SETTLED", False),
        "RO": ("TERMINAL", "RO", "SETTLED", False),
        "REF": ("TERMINAL", "REF", "SETTLED", False),
        "NR": ("NON_RUNNER", "NR", "VOID", False),
        "WD": ("NON_RUNNER", "WD", "VOID", False),
        "UNKNOWN": ("UNKNOWN", "", "UNSETTLED", False),
    }
    status, code, settlement, win = values[outcome]
    return {
        "date": date,
        "race_id": race,
        "horse_id": horse,
        "subject_outcome_status": status,
        "subject_outcome_code": code,
        "settlement_status": settlement,
        "win": win,
        "subject_is_non_runner": outcome in {"NR", "WD"},
        "stake_void": outcome in {"NR", "WD"},
        "result_source_complete": True,
        "result_source_hash": source,
    }


def packet(candidates=None, cap=12):
    return build_forward_acca_packet(
        race_date=DATE,
        candidates=[candidate("r1", "h1"), candidate("r2", "h2")] if candidates is None else candidates,
        card_artifact_path=CARD_PATH,
        max_tickets=cap,
    )


def anchored_settle(p, rows):
    global SETTLEMENT_CASE
    SETTLEMENT_CASE += 1
    root = EVIDENCE_ROOT / f"case-{SETTLEMENT_CASE}"
    write_immutable_forward_packet(p, root)
    source_path = root / f"result-source-{p['race_date']}.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_rows = [
        {key: value for key, value in row.items() if key not in {"date", "result_source_complete", "result_source_hash"}}
        for row in rows
    ]
    source_path.write_text(json.dumps({
        "race_date": p["race_date"], "result_source": {"name": "TEST_RESULTS"},
        "complete": True, "rows": source_rows,
    }), encoding="utf-8")
    write_canonical_truth_artifact(source_path, root)
    return settle_forward_packet(p, evidence_root=root), root


def anchored_day(root, date, *, win=True):
    card_path = root / f"card-{date}.json"
    card_path.parent.mkdir(parents=True, exist_ok=True)
    schedule = [
        {"race_id": "r1", "off_ts": f"{date}T11:00:00+01:00"},
        {"race_id": "r2", "off_ts": f"{date}T12:00:00+01:00"},
    ]
    card_path.write_text(json.dumps({
        "race_date": date, "timezone": "Europe/London",
        "provenance": {"source": "TEST_DATE_CARD"}, "races": schedule,
    }), encoding="utf-8")
    rows = []
    for index in (1, 2):
        row = candidate(f"r{index}", f"h{index}")
        row.update(
            {
                "off_ts": schedule[index - 1]["off_ts"],
                "selection_ts": f"{date}T08:00:00+01:00",
                "odds_capture_ts": f"{date}T08:30:00+01:00",
            }
        )
        rows.append(row)
    old_clock = lab._utc_now
    lab._utc_now = lambda: datetime.fromisoformat(f"{date}T09:00:00+01:00")
    try:
        p = build_forward_acca_packet(race_date=date, candidates=rows, card_artifact_path=card_path)
    finally:
        lab._utc_now = old_clock
    day_root = root
    canonical = [truth("r1", "h1", "WIN" if win else "LOSS", source=f"truth-{date}", date=date),
                 truth("r2", "h2", "WIN", source=f"truth-{date}", date=date)]
    write_immutable_forward_packet(p, day_root)
    source_path = root / f"result-source-{date}.json"
    source_path.write_text(json.dumps({
        "race_date": date, "result_source": {"name": "TEST_RESULTS"}, "complete": True,
        "rows": [{key: value for key, value in row.items() if key not in {"date", "result_source_complete", "result_source_hash"}} for row in canonical],
    }), encoding="utf-8")
    write_canonical_truth_artifact(source_path, day_root)
    settlement = settle_forward_packet(p, evidence_root=day_root)
    write_immutable_settlement(settlement, day_root)
    return settlement, day_root


def test_oracle_is_complete_search_not_selectability_claim():
    picks = [
        candidate("r1", "h1", odds=3), candidate("r1", "h2", odds=5),
        candidate("r2", "h3", odds=4), candidate("r2", "h4", odds=6),
    ]
    for index, row in enumerate(picks):
        row["model_name"] = f"M{index}"
    rows = [truth("r1", "h1"), truth("r1", "h2", "LOSS"), truth("r2", "h3"), truth("r2", "h4", "LOSS")]
    report = build_oracle_ceiling(race_date=DATE, model_selections=picks, canonical_rows=rows)
    assert report["artifact_type"] == "ORACLE_CEILING_OPPORTUNITY_COVERAGE"
    assert report["selectability_claim"] is False
    assert report["eligible_races"] == 2
    assert report["candidates_per_race"] == {"r1": 2, "r2": 2}
    assert report["total_combinatorial_tickets"] == 4
    assert report["smallest_winning_fold"] == 2
    assert report["winning_tickets"] == 1
    assert report["complete_search_outlay"] == 4
    assert report["genuine_captured_price_return"] == 12
    assert report["net_complete_search_result"] == 8


def test_oracle_deduplicates_same_horse_model_union():
    first = candidate("r1", "h1")
    duplicate = {**first, "model_name": "OTHER"}
    report = build_oracle_ceiling(
        race_date=DATE,
        model_selections=[first, duplicate, candidate("r2", "h2")],
        canonical_rows=[truth("r1", "h1"), truth("r2", "h2")],
    )
    assert report["candidates_per_race"]["r1"] == 1
    assert report["total_combinatorial_tickets"] == 1


def test_oracle_accepts_selection_without_probability_but_never_uses_unproven_price():
    first = candidate("r1", "h1", odds=10)
    second = candidate("r2", "h2", odds=12)
    first.pop("probability")
    second.pop("probability")
    first["odds_capture_ts"] = first["off_ts"]
    report = build_oracle_ceiling(
        race_date=DATE,
        model_selections=[first, second],
        canonical_rows=[truth("r1", "h1"), truth("r2", "h2")],
    )
    assert report["winning_tickets"] == 1
    assert report["genuine_captured_price_return"] == 0
    assert report["net_complete_search_result"] == -1


def test_forward_packet_is_finite_preregistered_and_paper_only():
    p = packet()
    assert p["artifact_type"] == "FORWARD_EXECUTABLE_SHADOW_TICKETS"
    assert p["status"] == "TICKETS_FROZEN"
    assert len(p["tickets"]) <= p["daily_ticket_cap"]
    assert p["safety"] == {
        "paper_sim_only": True, "execution_allowed": False, "bets_placed": False,
        "stakes_generated": False, "production_learning_allowed": False, "promotion_authorized": False,
    }
    assert p["research_declarations"]["operator_decision_required"] is True
    assert p["research_declarations"]["multiple_testing_correction"]
    ticket = p["tickets"][0]
    assert ticket["product_price"] == 4
    assert ticket["independence_product_reference"] == 0.25
    assert ticket["independence_reference_status"] == "UNVALIDATED_INDEPENDENCE_REFERENCE"
    assert ticket["identical_card_baselines"]["production"]["available"] is True


def test_forward_no_acca_is_explicit_and_zero_day_preserved():
    p = packet([], cap=4)
    assert p["status"] == "NO_ACCA"
    assert p["tickets"] == []
    assert p["no_acca_reason"] == "NO_PREDECLARED_TEMPLATE_QUALIFIED"
    settled, _ = anchored_settle(p, [truth("r1", "h1"), truth("r2", "h2")])
    assert settled["status"] == "NO_ACCA" and settled["tickets"] == []


@pytest.mark.parametrize(
    "mutation",
    [
        {"status": "NO_ACCA", "no_acca_reason": "NO_PREDECLARED_TEMPLATE_QUALIFIED"},
        {"status": "TICKETS_FROZEN", "no_acca_reason": "FORGED_REASON"},
        {"status": "UNKNOWN_STATUS", "no_acca_reason": None},
    ],
)
def test_rehashed_nonempty_packet_status_reason_contract_is_bidirectional(mutation):
    p = packet()
    p.update(mutation)
    p["packet_hash"] = lab._hash({key: value for key, value in p.items() if key != "packet_hash"})
    with pytest.raises(ValueError, match="PACKET_STATUS_TICKETS_REASON_CONTRACT_INVALID"):
        lab._validate_packet(p)


@pytest.mark.parametrize(
    "mutation",
    [
        {"status": "TICKETS_FROZEN", "no_acca_reason": None},
        {"status": "NO_ACCA", "no_acca_reason": None},
        {"status": "NO_ACCA", "no_acca_reason": "FORGED_REASON"},
        {"status": "UNKNOWN_STATUS", "no_acca_reason": "NO_PREDECLARED_TEMPLATE_QUALIFIED"},
    ],
)
def test_rehashed_empty_packet_status_reason_contract_is_bidirectional(mutation):
    p = packet([])
    p.update(mutation)
    p["packet_hash"] = lab._hash({key: value for key, value in p.items() if key != "packet_hash"})
    with pytest.raises(ValueError, match="PACKET_STATUS_TICKETS_REASON_CONTRACT_INVALID"):
        lab._validate_packet(p)


def test_packet_rejects_time_and_price_leakage(monkeypatch):
    late = candidate("r1", "h1")
    late["selection_ts"] = late["off_ts"]
    with pytest.raises(ValueError, match="SELECTION_NOT_STRICTLY_PRE_OFF"):
        packet([late])
    late = candidate("r1", "h1")
    late["odds_capture_ts"] = late["off_ts"]
    with pytest.raises(ValueError, match="CAPTURED_PRICE_NOT_STRICTLY_PRE_OFF"):
        packet([late])
    monkeypatch.setattr(lab, "_utc_now", lambda: datetime.fromisoformat(f"{DATE}T11:00:00+01:00"))
    with pytest.raises(ValueError, match="PACKET_NOT_FROZEN_BEFORE_AUTHORITATIVE_FIRST_OFF"):
        build_forward_acca_packet(race_date=DATE, candidates=[candidate("r1", "h1"), candidate("r2", "h2")], card_artifact_path=CARD_PATH)


def test_unique_candidate_and_one_horse_per_race():
    duplicate = candidate("r1", "h1")
    with pytest.raises(ValueError, match="DUPLICATE_CANDIDATE_IDENTITY"):
        packet([duplicate, duplicate])
    p = packet([candidate("r1", "h1"), candidate("r1", "h2"), candidate("r2", "h3")])
    assert all(len({leg["race_id"] for leg in ticket["legs"]}) == len(ticket["legs"]) for ticket in p["tickets"])


def test_correlation_flags_and_effective_legs_are_explicit():
    p = packet([
        candidate("r1", "h1", venue="AYR", family="FAMILY-A"),
        candidate("r2", "h2", venue="AYR", family="FAMILY-B"),
    ])
    ticket = p["tickets"][0]
    assert {"SHARED_VENUE", "SAME_MEETING"} <= set(ticket["correlation_flags"])
    assert ticket["effective_independent_legs"] < ticket["nominal_fold"]
    assert ticket["correlation_adjusted_probability"] is None
    assert ticket["correlation_adjustment_status"] == "UNAVAILABLE_UNCALIBRATED"
    assert ticket["correlation_stress_score"] > 0


@pytest.mark.parametrize("terminal", ["F", "PU", "UR", "BD", "RO", "REF"])
def test_terminal_starter_codes_are_losses_never_voids(terminal):
    p = packet()
    result, _ = anchored_settle(p, [truth("r1", "h1", terminal), truth("r2", "h2")])
    assert result["tickets"][0]["status"] == "LOST"
    assert result["tickets"][0]["settled_fold"] == 2


@pytest.mark.parametrize("void_code", ["NR", "WD"])
def test_true_non_runner_void_reduces_fold(void_code):
    p = packet()
    result, _ = anchored_settle(p, [truth("r1", "h1", void_code), truth("r2", "h2")])
    ticket = result["tickets"][0]
    assert ticket["status"] == "WON"
    assert ticket["nominal_fold"] == 2 and ticket["settled_fold"] == 1
    assert ticket["return"] == 2 and ticket["profit"] == 1


def test_unknown_and_missing_truth_fail_closed():
    p = packet()
    result, _ = anchored_settle(p, [truth("r1", "h1", "UNKNOWN"), truth("r2", "h2")])
    assert result["status"] == "UNRESOLVED"
    assert result["tickets"][0]["profit"] is None
    result, _ = anchored_settle(p, [truth("r1", "h1"), truth("r3", "unused")])
    assert result["status"] == "UNRESOLVED"


def test_result_identity_is_date_race_horse_and_conflicts_rejected():
    p = packet()
    duplicate = truth("r1", "h1")
    conflict = {**duplicate, "win": False}
    with pytest.raises(ValueError, match="CANONICAL_IDENTITY_CONFLICT"):
        anchored_settle(p, [duplicate, conflict, truth("r2", "h2")])


def test_packet_tamper_and_regeneration_conflict_rejected(tmp_path):
    p = packet()
    assert write_immutable_forward_packet(p, tmp_path)[0] == "CREATED"
    assert write_immutable_forward_packet(p, tmp_path)[0] == "VALIDATED_IDENTICAL"
    forged = copy.deepcopy(p)
    forged["tickets"][0]["legs"][0]["horse_id"] = "post-result-switch"
    with pytest.raises(ValueError, match="PACKET_HASH_MISMATCH"):
        write_immutable_forward_packet(forged, tmp_path)
    other = packet([candidate("r1", "other"), candidate("r2", "h2")])
    assert other["packet_identity_hash"] == p["packet_identity_hash"]
    with pytest.raises(FileExistsError, match="IMMUTABLE_CONFLICT"):
        write_immutable_forward_packet(other, tmp_path)


def test_json_roundtrip_remains_valid_and_settlement_immutable(tmp_path):
    p = json.loads(json.dumps(packet()))
    result, root = anchored_settle(p, [truth("r1", "h1"), truth("r2", "h2")])
    assert write_immutable_settlement(result, root)[0] == "CREATED"
    assert write_immutable_settlement(result, root)[0] == "VALIDATED_IDENTICAL"


def test_ticket_cap_and_experimental_folds():
    candidates = [candidate(f"r{i}", f"h{i}") for i in range(1, 10)]
    p = packet(candidates, cap=5)
    assert len(p["tickets"]) == 5
    assert any(ticket["experimental"] and ticket["nominal_fold"] >= 4 for ticket in p["tickets"])


def test_oracle_and_forward_artifacts_cannot_be_confused(tmp_path):
    p = packet()
    report = build_oracle_ceiling(
        race_date=DATE,
        model_selections=[candidate("r1", "h1"), candidate("r2", "h2")],
        canonical_rows=[truth("r1", "h1"), truth("r2", "h2")],
    )
    assert p["artifact_type"] != report["artifact_type"]
    assert "selectability_claim" not in p
    with pytest.raises(ValueError, match="PACKET_HASH_MISMATCH"):
        settle_forward_packet(report, evidence_root=tmp_path)


def holdout_evidence(settlements, evidence_root):
    return build_holdout_multiplicity_evidence(
        development_dates=["2026-08-01", "2026-08-02"],
        holdout_dates=[row["race_date"] for row in settlements],
        predeclared_hypotheses=[
            {"hypothesis_id": "h-banker", "template": "2_BANKER", "predeclared_at": "2026-08-31T12:00:00+00:00"}
        ],
        settlements=settlements, evidence_root=evidence_root, resampling_samples=31,
    )


def test_promotion_is_never_automatic_and_assesses_all_gates(tmp_path):
    settlements = [anchored_day(tmp_path, date)[0] for date in ("2026-09-01", "2026-09-02")]
    evidence = holdout_evidence(settlements, tmp_path)
    gate = promotion_gate(settlements, evidence, evidence_root=tmp_path, minimum_tickets=30, bootstrap_samples=50)
    assert gate["promotion_authorized"] is False
    assert gate["operator_decision_required"] is True
    assert gate["gate_evaluations"]["minimum_30_forward_days"]["status"] == "FAIL"
    assert gate["gate_evaluations"]["roi_lower_confidence_bound"]["status"] == "PASS"
    assert gate["gate_evaluations"]["operator_decision"]["status"] == "REQUIRED"


def test_incomplete_result_source_fails_closed(tmp_path):
    source = tmp_path / "incomplete-results.json"
    source.write_text(json.dumps({
        "race_date": DATE, "result_source": {"name": "TEST_RESULTS"}, "complete": False,
        "rows": [truth("r1", "h1"), truth("r2", "h2")],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="RESULT_SOURCE_NOT_COMPLETE"):
        write_canonical_truth_artifact(source, tmp_path)


def test_truth_cannot_be_supplied_as_arbitrary_rows_or_fake_hash(tmp_path):
    import inspect

    assert "canonical_rows" not in inspect.signature(settle_forward_packet).parameters
    source = tmp_path / "fake-hash-results.json"
    source.write_text(json.dumps({
        "race_date": DATE,
        "result_source": {"name": "TEST_RESULTS", "source_file_sha256": "f" * 64},
        "complete": True,
        "rows": [truth("r1", "h1"), truth("r2", "h2")],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="RESULT_SOURCE_INCLUDED_HASH_MISMATCH"):
        write_canonical_truth_artifact(source, tmp_path)


def test_identical_card_baselines_use_same_races_and_never_borrow_ticket_prices():
    p = packet()
    rows = [truth("r1", "h1"), truth("r2", "h2")]
    for race in ("r1", "r2"):
        rows.extend(
            [
                truth(race, f"fav-{race}", "LOSS"),
                truth(race, f"prod-{race}", "WIN"),
                truth(race, f"rnd-{race}", "LOSS"),
            ]
        )
    settled, _ = anchored_settle(p, rows)
    result = settled["tickets"][0]["identical_card_baselines"]
    assert result["market_favourite"]["status"] == "LOST"
    assert result["production"]["status"] == "WON_UNPRICED"
    assert result["production"]["profit"] is None
    assert result["top_probability"]["status"] == "WON_UNPRICED"


def test_public_builder_has_no_clock_override_and_persists_chronology():
    import inspect

    assert "generated_at" not in inspect.signature(build_forward_acca_packet).parameters
    p = packet()
    assert p["clock_provenance"] == "SYSTEM_UTC_INTERNAL"
    assert p["evidence_class"] == "GENUINELY_FORWARD"
    for ticket in p["tickets"]:
        for leg in ticket["legs"]:
            assert datetime.fromisoformat(leg["selection_ts"]) <= datetime.fromisoformat(p["generated_at"])
            assert datetime.fromisoformat(leg["odds_capture_ts"]) <= datetime.fromisoformat(p["generated_at"])


def test_historical_forward_build_refused_and_future_evidence_rejected(monkeypatch):
    monkeypatch.setattr(lab, "_utc_now", lambda: datetime.fromisoformat("2026-09-30T09:00:00+01:00"))
    with pytest.raises(ValueError, match="HISTORICAL_FORWARD_PACKET_REFUSED_USE_ORACLE"):
        build_forward_acca_packet(
            race_date=DATE, candidates=[candidate("r1", "h1"), candidate("r2", "h2")],
            card_artifact_path=CARD_PATH,
        )
    monkeypatch.setattr(lab, "_utc_now", lambda: NOW)
    future = candidate("r1", "h1")
    future["selection_ts"] = f"{DATE}T09:01:00+01:00"
    with pytest.raises(ValueError, match="SELECTION_TIMESTAMP_AFTER_PACKET"):
        packet([future, candidate("r2", "h2")])
    future = candidate("r1", "h1")
    future["odds_capture_ts"] = f"{DATE}T09:01:00+01:00"
    with pytest.raises(ValueError, match="PRICE_TIMESTAMP_AFTER_PACKET"):
        packet([future, candidate("r2", "h2")])
    monkeypatch.setattr(lab, "_utc_now", lambda: datetime.fromisoformat("2026-09-30T09:00:00+01:00"))
    with pytest.raises(ValueError, match="HISTORICAL_FORWARD_PACKET_REFUSED_USE_ORACLE"):
        build_forward_acca_packet(race_date=DATE, candidates=[], card_artifact_path=CARD_PATH)


def test_bst_operational_date_uses_london_not_utc(monkeypatch):
    monkeypatch.setattr(lab, "_utc_now", lambda: datetime.fromisoformat("2026-09-28T23:30:00+00:00"))
    p = build_forward_acca_packet(race_date=DATE, candidates=[], card_artifact_path=CARD_PATH)
    assert p["generated_at"].startswith("2026-09-28T23:30")
    assert p["operational_race_date"] == DATE
    assert p["racing_timezone"] == "Europe/London"


def test_no_acca_still_requires_verified_card_and_pre_first_off(monkeypatch, tmp_path):
    bad = tmp_path / "empty-card.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="CARD_RACE_DATE_MISMATCH"):
        build_forward_acca_packet(race_date=DATE, candidates=[], card_artifact_path=bad)
    monkeypatch.setattr(lab, "_utc_now", lambda: datetime.fromisoformat(f"{DATE}T11:00:00+01:00"))
    with pytest.raises(ValueError, match="PACKET_NOT_FROZEN_BEFORE_AUTHORITATIVE_FIRST_OFF"):
        build_forward_acca_packet(race_date=DATE, candidates=[], card_artifact_path=CARD_PATH)


def test_card_schedule_is_derived_only_from_artifact(monkeypatch, tmp_path):
    import inspect

    assert "card_evidence" not in inspect.signature(build_forward_acca_packet).parameters
    actual = tmp_path / "actual-card.json"
    actual.write_text(json.dumps({
        "race_date": DATE, "timezone": "Europe/London", "provenance": {"source": "ACTUAL"},
        "races": [{"race_id": "r1", "off_ts": f"{DATE}T10:00:00+01:00"}],
    }), encoding="utf-8")
    monkeypatch.setattr(lab, "_utc_now", lambda: datetime.fromisoformat(f"{DATE}T12:00:00+01:00"))
    with pytest.raises(ValueError, match="PACKET_NOT_FROZEN_BEFORE_AUTHORITATIVE_FIRST_OFF"):
        build_forward_acca_packet(race_date=DATE, candidates=[], card_artifact_path=actual)


@pytest.mark.parametrize(
    "field,value,error",
    [("race_date", "2026-09-30", "RACE_DATE_MISMATCH"), ("timezone", "UTC", "TIMEZONE_MISMATCH")],
)
def test_card_artifact_date_and_timezone_must_match(tmp_path, field, value, error):
    path = tmp_path / f"bad-{field}.json"
    payload = {
        "race_date": DATE, "timezone": "Europe/London", "provenance": {"source": "TEST"},
        "races": [{"race_id": "r1", "off_ts": f"{DATE}T11:00:00+01:00"}],
    }
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        build_forward_acca_packet(race_date=DATE, candidates=[], card_artifact_path=path)


def test_leg_must_match_authoritative_local_card_schedule():
    changed = candidate("r1", "h1")
    changed["off_ts"] = f"{DATE}T11:01:00+01:00"
    with pytest.raises(ValueError, match="LEG_NOT_IN_AUTHORITATIVE_CARD_SCHEDULE"):
        packet([changed, candidate("r2", "h2")])
    wrong_date = candidate("r1", "h1")
    wrong_date["off_ts"] = "2026-09-30T11:00:00+01:00"
    with pytest.raises(ValueError, match="LEG_OFF_NOT_ON_RACING_LOCAL_DATE"):
        packet([wrong_date, candidate("r2", "h2")])


def test_price_source_is_required_and_comparator_none_is_unavailable():
    bad = candidate("r1", "h1")
    bad["price_source"] = ""
    with pytest.raises(ValueError, match="CAPTURED_PRICE_NOT_STRICTLY_PRE_OFF"):
        packet([bad, candidate("r2", "h2")])
    first = candidate("r1", "h1")
    first["comparators"]["production"] = None
    p = packet([first, candidate("r2", "h2")])
    assert p["tickets"][0]["identical_card_baselines"]["production"]["available"] is False


def test_model_family_cap_is_predeclared_and_enforced():
    p = packet([
        candidate("r1", "h1", family="SAME"),
        candidate("r2", "h2", family="SAME"),
        candidate("r3", "h3", family="OTHER"),
    ])
    assert p["max_legs_per_model_family"] == 1
    assert all(len({leg["model_family"] for leg in ticket["legs"]}) == len(ticket["legs"]) for ticket in p["tickets"])
    assert all(not ({leg["horse_id"] for leg in ticket["legs"]} == {"h1", "h2"}) for ticket in p["tickets"])


@pytest.mark.parametrize(
    "outcome,changes",
    [
        ("F", {"subject_outcome_status": "NON_RUNNER", "settlement_status": "VOID", "subject_is_non_runner": True, "stake_void": True}),
        ("NR", {"subject_outcome_status": "TERMINAL", "settlement_status": "SETTLED", "subject_is_non_runner": False, "stake_void": False}),
        ("WIN", {"stake_void": True}),
    ],
)
def test_canonical_cross_field_contradictions_are_unresolved(outcome, changes):
    row = truth("r1", "h1", outcome)
    row.update(changes)
    result, _ = anchored_settle(packet(), [row, truth("r2", "h2")])
    assert result["status"] == "UNRESOLVED"
    assert result["tickets"][0]["leg_outcomes"][0]["outcome"] == "UNRESOLVED_CONFLICT"


def test_one_authoritative_day_lock_blocks_rule_or_cap_bypass(tmp_path):
    first = packet(cap=4)
    assert write_immutable_forward_packet(first, tmp_path)[0] == "CREATED"
    assert write_immutable_forward_packet(first, tmp_path)[0] == "VALIDATED_IDENTICAL"
    changed_cap = packet(cap=5)
    with pytest.raises(FileExistsError, match="IMMUTABLE_CONFLICT"):
        write_immutable_forward_packet(changed_cap, tmp_path)
    assert len(list((tmp_path / "packets" / DATE).glob("day_lock.json"))) == 1
    lock = json.loads((tmp_path / "packets" / DATE / "day_lock.json").read_text())
    assert lock["packet_hash"] == first["packet_hash"]


def test_day_lock_manifest_tamper_is_detected(tmp_path):
    p = packet()
    write_immutable_forward_packet(p, tmp_path)
    lock_path = tmp_path / "packets" / DATE / "day_lock.json"
    lock = json.loads(lock_path.read_text())
    lock["packet_hash"] = "forged"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(FileExistsError, match="IMMUTABLE_CONFLICT"):
        write_immutable_forward_packet(p, tmp_path)


def test_holdout_multiplicity_is_disjoint_predeclared_hashed_and_immutable(tmp_path):
    settlements = [anchored_day(tmp_path, "2026-09-01")[0], anchored_day(tmp_path, "2026-09-02", win=False)[0]]
    evidence = build_holdout_multiplicity_evidence(
        development_dates=["2026-08-01", "2026-08-02"],
        holdout_dates=["2026-09-01", "2026-09-02"],
        predeclared_hypotheses=[
            {"hypothesis_id": "banker", "template": "2_BANKER", "predeclared_at": "2026-08-31T12:00:00+00:00"},
            {"hypothesis_id": "glue", "template": "2_BANKER_GLUE", "predeclared_at": "2026-08-31T12:00:00+00:00"},
        ],
        settlements=settlements, evidence_root=tmp_path, resampling_samples=31, resampling_seed=7,
    )
    assert evidence["hypothesis_count"] == 2
    assert evidence["methodology"]["no_tuning_on_holdout"] is True
    assert all("bh_adjusted_p_value" in row for row in evidence["metrics"])
    assert write_immutable_holdout_evidence(evidence, tmp_path)[0] == "CREATED"
    assert write_immutable_holdout_evidence(evidence, tmp_path)[0] == "VALIDATED_IDENTICAL"


def test_holdout_rejects_overlap_late_hypothesis_and_missing_day(tmp_path):
    settlements = [anchored_day(tmp_path, "2026-09-01")[0]]
    base = {
        "development_dates": ["2026-08-01"], "holdout_dates": ["2026-09-01"],
        "predeclared_hypotheses": [
            {"hypothesis_id": "h", "template": "2_BANKER", "predeclared_at": "2026-08-31T12:00:00+00:00"}
        ],
        "settlements": settlements, "evidence_root": tmp_path, "resampling_samples": 7,
    }
    with pytest.raises(ValueError, match="OVERLAP_OR_ORDER"):
        build_holdout_multiplicity_evidence(**{**base, "development_dates": ["2026-09-01"]})
    late = copy.deepcopy(base)
    late["predeclared_hypotheses"][0]["predeclared_at"] = "2026-09-01T00:00:00+00:00"
    with pytest.raises(ValueError, match="NOT_PREDECLARED"):
        build_holdout_multiplicity_evidence(**late)
    with pytest.raises(ValueError, match="COVERAGE_INCOMPLETE"):
        build_holdout_multiplicity_evidence(**{**base, "holdout_dates": ["2026-09-01", "2026-09-02"]})


def test_packet_and_settlement_rehashed_tamper_still_fail_derived_identity(tmp_path):
    p = packet()
    forged = copy.deepcopy(p)
    forged["tickets"][0]["correlation_stress_score"] = 0.99
    forged["packet_hash"] = lab._hash({key: value for key, value in forged.items() if key != "packet_hash"})
    with pytest.raises(ValueError, match="TICKET_DERIVATION_MISMATCH"):
        settle_forward_packet(forged, evidence_root=tmp_path)
    settled, root = anchored_settle(p, [truth("r1", "h1"), truth("r2", "h2")])
    settled["tickets"][0]["profit"] = 999
    settled["settlement_hash"] = lab._hash({key: value for key, value in settled.items() if key != "settlement_hash"})
    with pytest.raises(ValueError, match="SETTLEMENT_IDENTITY_MISMATCH"):
        write_immutable_settlement(settled, root)


def test_rehashed_derived_ticket_off_forgery_rejected_by_card_schedule():
    p = packet()
    forged = copy.deepcopy(p)
    forged["tickets"][0]["legs"][0]["off_ts"] = f"{DATE}T11:01:00+01:00"
    template = next(row for row in lab.TEMPLATES if row["template"] == forged["tickets"][0]["template"])
    derived = lab._ticket(template, tuple(forged["tickets"][0]["legs"]), forged["rule_version"])
    derived["identical_card_baselines"] = forged["tickets"][0]["identical_card_baselines"]
    forged["tickets"][0] = derived
    forged["packet_hash"] = lab._hash({key: value for key, value in forged.items() if key != "packet_hash"})
    with pytest.raises(ValueError, match="TICKET_LEG_NOT_IN_DERIVED_CARD_SCHEDULE"):
        lab._validate_packet(forged)


def test_fabricated_settlement_rejected_without_day_lock_and_truth(tmp_path):
    fake = {
        "race_date": DATE, "packet_hash": "fake", "result_source_hash": "fake", "tickets": [],
        "safety": {"paper_sim_only": True},
    }
    fake["settlement_hash"] = lab._hash(fake)
    with pytest.raises(ValueError, match="SETTLEMENT_IDENTITY_MISMATCH|AUTHORITATIVE_EVIDENCE_MISSING"):
        write_immutable_settlement(fake, tmp_path)


def test_truth_artifact_and_frozen_packet_tamper_break_settlement_validation(tmp_path):
    p = packet()
    rows = [truth("r1", "h1"), truth("r2", "h2")]
    settled, root = anchored_settle(p, rows)
    write_immutable_settlement(settled, root)
    truth_path = root / "truth" / DATE / "canonical_truth.json"
    truth_artifact = json.loads(truth_path.read_text())
    truth_artifact["canonical_rows"][0]["win"] = False
    truth_path.write_text(json.dumps(truth_artifact), encoding="utf-8")
    with pytest.raises(ValueError, match="CANONICAL_TRUTH_HASH_MISMATCH"):
        write_immutable_settlement(settled, root)


def test_changed_result_source_after_canonical_artifact_is_detected():
    p = packet()
    settled, root = anchored_settle(p, [truth("r1", "h1"), truth("r2", "h2")])
    truth_artifact = json.loads((root / "truth" / DATE / "canonical_truth.json").read_text())
    source_path = Path(truth_artifact["result_source_artifact_path"])
    source = json.loads(source_path.read_text())
    source["rows"][0]["win"] = False
    source_path.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="CANONICAL_TRUTH_BODY_MISMATCH"):
        write_immutable_settlement(settled, root)
