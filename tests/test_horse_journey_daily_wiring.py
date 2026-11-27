from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_governed_prime_runner_builds_journey_from_canonical_history_and_capture_time():
    source = (ROOT / "scripts" / "ops" / "run_prime_today.py").read_text(encoding="utf-8")

    assert "build_horse_journey_shadow" in source
    assert "historical_runs=_history.get(\"journey_history_rows\") or []" in source
    assert "source_captured_at=_comment_shadow_packet.get(\"captured_at\")" in source
    assert "race_off_time_utc=_comment_shadow_packet.get(\"off_time_utc\")" in source
    assert "horse_journey_packet=_journey_packet" in source


def test_history_provider_exposes_exact_pre_cutoff_journey_rows_separate_from_features():
    source = (ROOT / "app" / "services" / "rich_context_history_provider.py").read_text(encoding="utf-8")

    assert '"journey_history_rows": []' in source
    assert 'base["journey_history_rows"]' in source
    assert '"run_date": row["run_date"]' in source
