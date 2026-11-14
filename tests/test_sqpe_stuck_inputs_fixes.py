"""Regression tests for the stuck-input parser fixes (distance, class, weight, going)."""
from app.services.sqpe_v17_service import _parse_class, _parse_dist, _parse_going, _parse_wgt
from workers.racing_api_normalizer import _st_lb_to_lbs


def test_numeric_furlongs_are_not_defaulted():
    assert _parse_dist(16.0) == 16.0
    assert _parse_dist(10.0) == 10.0
    assert _parse_dist("5.5") == 5.5


def test_text_distance_still_parses():
    assert _parse_dist("1m2f") == 10.0


def test_bare_digit_class_parses():
    assert _parse_class("4") == 4.0
    assert _parse_class("2") == 2.0
    assert _parse_class("Class 3") == 3.0


def test_st_lb_weight_converts_to_pounds():
    assert _st_lb_to_lbs("11-1") == 155
    assert _st_lb_to_lbs("9-0") == 126
    assert _parse_wgt(_st_lb_to_lbs("11-1")) == 155.0


def test_missing_weight_keeps_default():
    assert _parse_wgt(_st_lb_to_lbs("")) == 126.0


def test_going_longest_phrase_wins():
    assert _parse_going("Good to Firm")[0] == 1.5
    assert _parse_going("Good to Soft")[0] == 0.5
    assert _parse_going("Good")[0] == 1.0
    assert _parse_going("Firm")[0] == 2.0
