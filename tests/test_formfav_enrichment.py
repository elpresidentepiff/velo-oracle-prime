from src.velo.formfav_enrichment import _race_local_minutes


def test_compact_racing_post_time_is_normalized_to_afternoon():
    assert _race_local_minutes({"off_time": "4.12"}, "2026-10-12") == 16 * 60 + 12


def test_explicit_24_hour_time_is_preserved():
    assert _race_local_minutes({"off_time": "16:12"}, "2026-10-12") == 16 * 60 + 12


def test_compact_noon_time_is_not_shifted():
    assert _race_local_minutes({"off_time": "12.30"}, "2026-10-12") == 12 * 60 + 30
