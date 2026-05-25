from __future__ import annotations

from new_build_velo.sources import discover_sources, ingest_racing_api_card, ingest_racing_api_results


def test_source_inventory_sees_industry_scale_inputs() -> None:
    inventory = discover_sources(execute=False)

    assert inventory["racing_api_racecard_files"] >= 30
    assert inventory["racing_api_result_files"] >= 50
    assert inventory["raceform_clean_available"] is True
    assert inventory["rpdc_historical_available"] is True
    assert inventory["velo_scoring_allowed"] is False


def test_racing_api_card_ingest_is_archive_only() -> None:
    payload = ingest_racing_api_card("2026-05-15", execute=False)

    assert payload["status"] == "PASS"
    assert payload["race_count"] == 52
    assert payload["runner_count"] > 300
    assert payload["velo_scoring_allowed"] is False
    assert all(row["velo_scoring_allowed"] is False for row in payload["records"][:10])


def test_racing_api_results_ingest_is_archive_only() -> None:
    payload = ingest_racing_api_results("2026-05-13", execute=False)

    assert payload["status"] == "PASS"
    assert payload["race_count"] == 59
    assert payload["winner_count"] == 59
    assert payload["velo_scoring_allowed"] is False
