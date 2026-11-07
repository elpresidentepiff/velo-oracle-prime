from __future__ import annotations

import copy
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.velo.rich_context_comment_intelligence import (
    FEATURE_SCHEMA_VERSION,
    PARSER_VERSION,
    attach_comment_shadow_by_horse_id,
    build_race_comment_shadow_packet,
    build_runner_comment_shadow,
    extract_factual_comment_evidence,
    resolve_race_off_time_utc,
)


def test_extracts_only_allowlisted_factual_spans() -> None:
    facts, rejected = extract_factual_comment_evidence(
        "Held up and denied a clear run last time. First-time cheekpieces today."
    )

    assert {fact["family"] for fact in facts} == {
        "pace_and_running_style",
        "interference_and_trip",
        "equipment_and_procedure",
    }
    assert rejected == []


def test_rejects_entire_sentence_when_tip_language_is_mixed_with_fact() -> None:
    facts, rejected = extract_factual_comment_evidence(
        "Held up last time and should win today. Stayed on at Newbury."
    )

    assert [fact["family"] for fact in facts] == ["finish_profile"]
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "OPINION_OR_SELECTION"
    assert "text" not in rejected[0]


@pytest.mark.parametrize(
    "opinion",
    [
        "has strong claims",
        "should go well",
        "belongs on the shortlist",
        "is respected",
        "is feared",
        "is a player",
        "is the likeliest winner",
        "has each-way claims",
        "has a place chance",
        "may win",
        "might win",
        "is interesting",
        "looks well treated",
        "must be considered",
        "is not ruled out",
    ],
)
def test_adversarial_opinion_phrases_reject_mixed_factual_sentence(opinion: str) -> None:
    facts, rejected = extract_factual_comment_evidence(
        f"Held up and stayed on last time but {opinion}."
    )

    assert facts == []
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "OPINION_OR_SELECTION"


def test_pre_off_exact_identity_packet_is_training_eligible() -> None:
    packet = build_runner_comment_shadow(
        raw_text="Prominent and stayed on.",
        race_id="rp_123",
        horse_id="456",
        horse_name="Example",
        captured_at="2026-11-07T10:00:00Z",
        off_time_utc="2026-11-07T10:01:00Z",
    )

    assert packet["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert packet["parser_version"] == PARSER_VERSION
    assert packet["captured_before_off"] is True
    assert packet["identity_eligible"] is True
    assert packet["training_eligible"] is True
    assert packet["production_prime_consumed"] is False
    assert packet["provider_prediction_consumed"] is False
    assert len(packet["raw_text_sha256"]) == 64


def test_hashes_exact_source_separately_from_normalized_text() -> None:
    raw = "  Held up\n\nand stayed on.  "
    packet = build_runner_comment_shadow(
        raw_text=raw,
        race_id="rp_123",
        horse_id="456",
        horse_name="Example",
        captured_at="2026-11-07T10:00:00Z",
        off_time_utc="2026-11-07T10:01:00Z",
    )

    assert packet["raw_text_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert packet["normalized_text_sha256"] == hashlib.sha256(
        b"Held up and stayed on."
    ).hexdigest()
    assert packet["raw_text_sha256"] != packet["normalized_text_sha256"]


def test_equal_to_or_after_off_is_ineligible() -> None:
    packet = build_runner_comment_shadow(
        raw_text="Held up.",
        race_id="rp_123",
        horse_id="456",
        horse_name="Example",
        captured_at="2026-11-07T10:01:00Z",
        off_time_utc="2026-11-07T10:01:00Z",
    )

    assert packet["captured_before_off"] is False
    assert packet["training_eligible"] is False
    assert "NOT_CAPTURED_PRE_OFF" in packet["ineligibility_reasons"]


def test_missing_canonical_identity_is_ineligible() -> None:
    packet = build_runner_comment_shadow(
        raw_text="Travelled strongly.",
        race_id="rp_123",
        horse_id="",
        horse_name="Name Only",
        captured_at="2026-11-07T10:00:00Z",
        off_time_utc="2026-11-07T10:01:00Z",
    )

    assert packet["identity_eligible"] is False
    assert "UNPROVEN_IDENTITY" in packet["ineligibility_reasons"]


def test_race_packet_does_not_mutate_prime_input() -> None:
    race = {
        "race_id": "rp_123",
        "date": "2026-11-07",
        "off_time": "10:30",
        "runners": [
            {"horse_id": "456", "horse_name": "Example", "spotlight": "Led and stayed on."}
        ],
    }
    original = copy.deepcopy(race)

    packet = build_race_comment_shadow_packet(
        race,
        captured_at=datetime(2026, 11, 7, 10, 0, tzinfo=UTC),
    )

    assert race == original
    assert packet["eligible_runner_count"] == 1
    assert packet["production_prime_consumed"] is False


def test_attachment_uses_prediction_horse_id_not_duplicate_or_variant_name() -> None:
    race_packet = {
        "runners": [
            {"horse_id": "101", "horse_name": "O'Brien's Star", "marker": "A"},
            {"horse_id": "202", "horse_name": "Obriens Star", "marker": "B"},
        ]
    }
    predictions = [
        {"horse_id": "202", "horse": "O'Brien's Star"},
        {"horse_id": "101", "horse": "OBRIENS STAR"},
        {"horse_id": "", "horse": "O'Brien's Star"},
        {"horse": "Obriens Star"},
    ]

    attached = attach_comment_shadow_by_horse_id(predictions, race_packet)

    assert attached == 2
    assert predictions[0]["rich_context_comment_shadow"]["marker"] == "B"
    assert predictions[1]["rich_context_comment_shadow"]["marker"] == "A"
    assert predictions[2]["rich_context_comment_shadow"] is None
    assert predictions[3]["rich_context_comment_shadow"] is None


def test_duplicate_packet_horse_id_fails_closed() -> None:
    packet = {"runners": [{"horse_id": "101"}, {"horse_id": "101"}]}
    predictions = [{"horse_id": "101", "horse": "Same Name"}]

    assert attach_comment_shadow_by_horse_id(predictions, packet) == 0
    assert predictions[0]["rich_context_comment_shadow"] is None


def test_london_off_time_is_resolved_to_utc() -> None:
    winter = resolve_race_off_time_utc({"date": "2026-11-07", "off_time": "10:30"})
    summer = resolve_race_off_time_utc({"date": "2026-07-07", "off_time": "10:30"})

    assert winter == datetime(2026, 11, 7, 10, 30, tzinfo=UTC)
    assert summer == datetime(2026, 7, 7, 9, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("card_time", "expected_utc"),
    [
        # Racing Post prints afternoon times in 12-hour form with no am/pm. These are
        # the exact strings that produced no history or Spotlight on 2026-11-07.
        ("1.52", datetime(2026, 11, 7, 13, 52, tzinfo=UTC)),
        ("3.00", datetime(2026, 11, 7, 15, 0, tzinfo=UTC)),
        ("4.30", datetime(2026, 11, 7, 16, 30, tzinfo=UTC)),
        ("8.45", datetime(2026, 11, 7, 20, 45, tzinfo=UTC)),
        # Morning and noon times are already on the 24-hour clock.
        ("10.05", datetime(2026, 11, 7, 10, 5, tzinfo=UTC)),
        ("11.55", datetime(2026, 11, 7, 11, 55, tzinfo=UTC)),
        ("12.45", datetime(2026, 11, 7, 12, 45, tzinfo=UTC)),
        # A 24-hour feed is unchanged.
        ("15:00", datetime(2026, 11, 7, 15, 0, tzinfo=UTC)),
    ],
)
def test_afternoon_card_times_resolve_to_the_pm_clock(card_time: str, expected_utc: datetime) -> None:
    assert resolve_race_off_time_utc({"date": "2026-11-07", "off_time": card_time}) == expected_utc


def test_afternoon_summer_time_is_converted_from_london_to_utc() -> None:
    assert resolve_race_off_time_utc({"date": "2026-07-07", "off_time": "3.00"}) == datetime(
        2026, 7, 7, 14, 0, tzinfo=UTC
    )


@pytest.mark.parametrize("bad", ["", "noon", "25:00", "11.75", "3", "3.5"])
def test_unparseable_card_time_is_unknown_not_guessed(bad: str) -> None:
    assert resolve_race_off_time_utc({"date": "2026-11-07", "off_time": bad}) is None


def test_run_prime_builds_shadow_packet_before_unchanged_prime_call() -> None:
    source = (Path(__file__).parents[1] / "scripts" / "ops" / "run_prime_today.py").read_text(
        encoding="utf-8"
    )
    build_at = source.index("_comment_shadow_packet = build_race_comment_shadow_packet(")
    score_at = source.index("preds = score_race_velo_prime(race, sentient_state=_sentient_state)")
    attach_at = source.index("attach_comment_shadow_by_horse_id(preds, _comment_shadow_packet)")

    assert build_at < score_at
    assert score_at < attach_at
    assert "score_race_velo_prime(race, sentient_state=_sentient_state)" in source
    assert "score_race_velo_prime(race, _comment_shadow_packet" not in source
    assert "_comment_shadow_by_horse_id =" not in source
