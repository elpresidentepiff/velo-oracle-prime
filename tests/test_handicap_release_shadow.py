from datetime import date

import pytest

from src.velo.handicap_release_shadow import HistoricalRun, RaceContext, review_handicap_release


def context(**changes):
    base = dict(race_id="r1", runner_id="h1", race_date=date(2026, 11, 26), is_handicap=True,
                official_rating=70, course="York", distance_furlongs=8.0, going_bucket="GOOD")
    base.update(changes)
    return RaceContext(**base)


def history():
    return [
        HistoricalRun(date(2026, 8, 1), 75, 4, "York", 8.0, "GOOD"),
        HistoricalRun(date(2026, 9, 1), 74, 1, "York", 8.0, "GOOD"),
        HistoricalRun(date(2026, 10, 1), 72, 7, "Ascot", 10.0, "SOFT"),
        HistoricalRun(date(2026, 11, 1), 71, 6, "Ascot", 10.0, "SOFT"),
    ]


def test_candidate_requires_mark_and_two_independent_corroborators():
    review = review_handicap_release(context(), history())
    assert review.status == "CANDIDATE_FOR_REVIEW"
    assert "AT_OR_BELOW_LAST_WINNING_MARK" in review.evidence
    assert "RETURN_TO_WINNING_COURSE" in review.evidence
    assert review.corroborator_count == 3
    assert review.classification == "SHADOW_ONLY_NO_LIVE_SCORING_CHANGE"


def test_above_winning_mark_is_not_a_candidate_even_when_other_context_fits():
    review = review_handicap_release(context(official_rating=76), history())
    assert review.status == "NOT_SUPPORTED"
    assert "ABOVE_LAST_WINNING_MARK" in review.contradictions


def test_missing_mark_or_short_history_fails_closed_with_explicit_reason():
    assert "CURRENT_OFFICIAL_RATING_MISSING" in review_handicap_release(context(official_rating=None), history()).missing
    assert "INSUFFICIENT_PRIOR_RUNS" in review_handicap_release(context(), history()[:2]).missing


def test_no_winning_mark_is_insufficient_not_a_negative_inference():
    no_wins = [HistoricalRun(r.run_date, r.official_rating, 2, r.course, r.distance_furlongs, r.going_bucket) for r in history()]
    review = review_handicap_release(context(), no_wins)
    assert review.status == "INSUFFICIENT_EVIDENCE"
    assert "PRIOR_WINNING_MARK_MISSING" in review.missing


def test_non_handicap_is_out_of_scope():
    review = review_handicap_release(context(is_handicap=False), history())
    assert review.status == "NOT_SUPPORTED"
    assert review.contradictions == ("NOT_A_HANDICAP",)


def test_same_day_or_future_history_is_rejected_as_leakage():
    with pytest.raises(ValueError, match="same-day or future"):
        review_handicap_release(context(), history() + [HistoricalRun(date(2026, 11, 26), 70, 1)])


def test_generator_history_is_not_consumed_during_as_of_validation():
    review = review_handicap_release(context(), (row for row in history()))
    assert review.status == "CANDIDATE_FOR_REVIEW"
