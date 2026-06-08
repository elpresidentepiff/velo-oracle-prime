from __future__ import annotations

from new_build_velo.result_fetcher import _date_range


def test_result_fetcher_date_range() -> None:
    assert _date_range("2026-05-25", "2026-05-27") == ["2026-05-25", "2026-05-26", "2026-05-27"]
