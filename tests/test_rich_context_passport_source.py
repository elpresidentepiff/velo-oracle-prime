from datetime import UTC, datetime

from src.velo.rich_context_passport_source import factual_passport_before_cutoff


def _row(*, persisted_at: str = "2026-11-19T08:00:00+00:00") -> dict:
    return {
        "horse_rp_uid": 123,
        "career_runs": 18,
        "wins": 4,
        "win_rate": 0.222,
        "last_run_date": "2026-10-31",
        "source_sha256": "a" * 64,
        "persisted_at": persisted_at,
        # Must not be copied wholesale: it may contain opaque/derived/text
        # content that has not been individually provenance-checked.
        "passport": {"private_notes": "not packet evidence"},
    }


def test_passport_facts_are_allowlisted_and_pre_off() -> None:
    facts = factual_passport_before_cutoff(
        _row(), as_of_cutoff=datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
    )
    assert facts == {
        "source": "new_build_horse_passports",
        "horse_rp_uid": 123,
        "career_runs": 18,
        "wins": 4,
        "win_rate": 0.222,
        "last_run_date": "2026-10-31",
        "source_sha256": "a" * 64,
        "persisted_at": "2026-11-19T08:00:00+00:00",
    }
    assert "passport" not in facts


def test_passport_after_off_or_without_timestamp_fails_closed() -> None:
    cutoff = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
    assert factual_passport_before_cutoff(
        _row(persisted_at="2026-11-19T12:00:01+00:00"), as_of_cutoff=cutoff
    ) is None
    assert factual_passport_before_cutoff(
        _row(persisted_at="2026-11-19T12:00:00+00:00"), as_of_cutoff=cutoff
    ) is None
    assert factual_passport_before_cutoff(
        {"horse_rp_uid": 123}, as_of_cutoff=cutoff
    ) is None
