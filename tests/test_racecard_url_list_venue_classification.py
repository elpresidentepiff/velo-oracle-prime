"""Regression test for UK/IRE venue slug classification in the RP racecard URL list builder.

southwell-aw (Southwell's all-weather fixture slug) was missing from UK_IRE_VENUES,
causing today's Southwell meeting to be misclassified as international and dropped
from the UK/IRE racecard URL list on 2026-07-05.
"""
from scripts.ops.build_racing_post_racecard_url_list import UK_IRE_VENUES, _venue_slug_from_url


def test_southwell_aw_is_classified_uk_ire():
    assert "southwell-aw" in UK_IRE_VENUES


def test_southwell_aw_url_extracts_matching_slug():
    url = "https://www.racingpost.com/racecards/394/southwell-aw/2026-07-05/921916"
    slug = _venue_slug_from_url(url)
    assert slug is not None
    assert slug.lower() in UK_IRE_VENUES
