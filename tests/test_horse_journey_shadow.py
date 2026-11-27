from src.velo.horse_journey_shadow import build_horse_journey_shadow


def _run(day, *, position=2, official_rating=70, course="York", course_id="york", distance_f=8, jockey_id="j1"):
    return {"run_date": day, "position_int": position, "official_rating": official_rating,
            "course": course, "course_id": course_id, "distance_f": distance_f, "jockey_id": jockey_id}


def _runner(**overrides):
    row = {"current_or": 70, "course": "York", "course_id": "york", "distance_f": 8,
           "jockey_id": "j2", "stable_heat": 16.0}
    row.update(overrides)
    return row


CAPTURED = "2026-11-27T08:00:00+00:00"
OFF_TIME = "2026-11-27T12:00:00+00:00"


def test_emits_factual_handicap_release_pattern_only_with_mark_and_corroboration():
    packet = build_horse_journey_shadow(
        race_id="race-1", horse_id="horse-1", race_date="2026-11-27", source_captured_at=CAPTURED, race_off_time_utc=OFF_TIME,
        runner=_runner(), historical_runs=[_run("2026-11-10"), _run("2026-10-01", position=1, official_rating=70)],
    )

    assert packet["training_eligible"] is True
    assert "JOURNEY_MARK_AT_OR_BELOW_LAST_WIN" in packet["factual_tags"]
    assert "JOURNEY_RETURN_TO_WINNING_COURSE" in packet["factual_tags"]
    assert "JOURNEY_RETURN_TO_WINNING_DISTANCE" in packet["factual_tags"]
    assert "JOURNEY_HANDICAP_RELEASE_PATTERN" in packet["factual_tags"]
    assert packet["ranking_effect"] == "NONE"


def test_does_not_invent_handicap_release_from_mark_alone():
    packet = build_horse_journey_shadow(
        race_id="race-1", horse_id="horse-1", race_date="2026-11-27", source_captured_at=CAPTURED, race_off_time_utc=OFF_TIME,
        runner=_runner(course="Ascot", course_id="ascot", distance_f=12, jockey_id="j1", stable_heat=0),
        historical_runs=[_run("2026-11-26", position=1, official_rating=70, course="York", course_id="york", distance_f=8, jockey_id="j1")],
    )

    assert "JOURNEY_MARK_AT_OR_BELOW_LAST_WIN" in packet["factual_tags"]
    assert "JOURNEY_HANDICAP_RELEASE_PATTERN" not in packet["factual_tags"]
    # The prior win is retained-ability evidence, but without a current-race
    # context match it remains a WATCH rather than a release candidate.
    assert packet["handicap_release_assessment"]["verdict"] == "WATCH"


def test_handicap_release_requires_mark_ability_and_context_and_never_claims_intent():
    packet = build_horse_journey_shadow(
        race_id="race-1", horse_id="horse-1", race_date="2026-11-27", source_captured_at=CAPTURED, race_off_time_utc=OFF_TIME,
        runner=_runner(current_or=70), historical_runs=[
            {**_run("2026-11-20", position=2, official_rating=80), "rpr": 100, "tsr": 90},
            {**_run("2026-11-01", position=1, official_rating=75), "rpr": 102, "tsr": 91},
        ],
    )
    assessment = packet["handicap_release_assessment"]
    assert assessment["verdict"] == "STRONG_CANDIDATE"
    assert "HRI_MARK_DROP_FROM_RECENT_PEAK" in {item["code"] for item in assessment["evidence"]}
    assert assessment["intent_claim"] == "NOT_MADE"
    assert assessment["betting_recommendation"] == "NOT_MADE"


def test_rejects_same_day_or_future_history_to_prevent_outcome_leakage():
    packet = build_horse_journey_shadow(
        race_id="race-1", horse_id="horse-1", race_date="2026-11-27", source_captured_at=CAPTURED, race_off_time_utc=OFF_TIME,
        runner=_runner(), historical_runs=[_run("2026-11-27", position=1), _run("2026-11-28", position=1)],
    )

    assert packet["history_rows_used"] == 0
    assert packet["history_rows_rejected"] == 2
    assert "POST_CUTOFF_OR_INVALID_HISTORY_REJECTED" in packet["ineligibility_reasons"]
    assert "NO_TIME_SAFE_HISTORY" in packet["ineligibility_reasons"]
    assert packet["training_eligible"] is False


def test_requires_identity_and_capture_time_before_any_training_use():
    packet = build_horse_journey_shadow(
        race_id="", horse_id="", race_date="2026-11-27", source_captured_at=None, race_off_time_utc=None,
        runner=_runner(), historical_runs=[_run("2026-11-20")],
    )

    assert packet["training_eligible"] is False
    assert "UNPROVEN_CANONICAL_IDENTITY" in packet["ineligibility_reasons"]
    assert "MISSING_SOURCE_CAPTURE_TIME" in packet["ineligibility_reasons"]


def test_journey_facts_are_captured_in_rich_context_but_not_active_model_input():
    from src.velo.rich_context_challenger import build_runner_shadow_packet

    journey = build_horse_journey_shadow(
        race_id="race-1", horse_id="horse-1", race_date="2026-11-27", source_captured_at=CAPTURED, race_off_time_utc=OFF_TIME,
        runner=_runner(), historical_runs=[_run("2026-11-20", position=1)],
    )
    packet = build_runner_shadow_packet(
        race_id="race-1", horse_id="horse-1", race_date="2026-11-27",
        prime_snapshot={"velo_prime_prob": 0.2}, formfav_manifest=None,
        history_packet={"eligible": True, "source_row_ids": ["1"], "features": {"win_rate": 0.1}},
        comment_packet=None, horse_journey_packet=journey,
    )

    assert packet["families"]["horse_journey_facts"]["factual_tags"] == journey["factual_tags"]
    assert packet["production_influence"] is False
    assert packet["challenger_probability"] is None


def test_capture_at_or_after_off_is_explicitly_ineligible():
    packet = build_horse_journey_shadow(
        race_id="race-1", horse_id="horse-1", race_date="2026-11-27",
        source_captured_at="2026-11-27T12:00:00+00:00", race_off_time_utc=OFF_TIME,
        runner=_runner(), historical_runs=[_run("2026-11-20", position=1)],
    )

    assert packet["captured_before_off"] is False
    assert packet["training_eligible"] is False
    assert "NOT_CAPTURED_PRE_OFF" in packet["ineligibility_reasons"]
