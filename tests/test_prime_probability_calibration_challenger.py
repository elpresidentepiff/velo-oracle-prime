import json
from copy import deepcopy

import pytest

from scripts.analysis.prime_probability_calibration_challenger import (
    power_transform,
    run_challenger,
    split_chronologically,
)


def _race(day: int, winner: int) -> dict:
    base = [0.70, 0.20, 0.10]
    g = [0.60, 0.25, 0.15]
    market = [0.45, 0.35, 0.20]
    runners = []
    for index, name in enumerate(("Alpha", "Bravo", "Charlie")):
        runners.append(
            {
                "horse": name,
                "base_prob": base[index],
                "g_prob": g[index],
                "market_prob": market[index],
                "is_winner": index == winner,
            }
        )
    return {
        "race_id": f"race-{day:02d}",
        "race_date": f"2026-01-{day:02d}",
        "course": "Test",
        "off_time": "14:00",
        "winner_index": winner,
        "winner_name": runners[winner]["horse"],
        "winner_sp": 4.0,
        "runners": runners,
    }


def _sample_races(test_winner: int = 1) -> list[dict]:
    winners = [0, 1, 2, 0, 1, 2, 0, 1, 2, test_winner, test_winner, test_winner]
    return [_race(day, winner) for day, winner in enumerate(winners, start=1)]


def test_power_transform_is_normalised_and_preserves_ranking():
    transformed = power_transform([0.7, 0.2, 0.1], 0.5)
    assert sum(transformed) == pytest.approx(1.0)
    assert transformed[0] > transformed[1] > transformed[2]
    assert transformed[0] < 0.7


def test_split_keeps_complete_days_in_strict_chronological_order():
    races = _sample_races()
    races.append({**deepcopy(races[0]), "race_id": "race-01-b"})
    blocks = split_chronologically(races)
    dates = {name: {race["race_date"] for race in block} for name, block in blocks.items()}
    assert not (dates["train"] & dates["calibration"])
    assert not (dates["train"] & dates["test"])
    assert not (dates["calibration"] & dates["test"])
    assert max(dates["train"]) < min(dates["calibration"]) < min(dates["test"])
    assert sum(race["race_date"] == "2026-01-01" for race in blocks["train"]) == 2


def test_holdout_outcomes_cannot_change_fitted_or_selected_challenger(tmp_path):
    first = run_challenger(_sample_races(test_winner=1), tmp_path / "first", bootstrap_samples=20)
    second = run_challenger(_sample_races(test_winner=2), tmp_path / "second", bootstrap_samples=20)

    assert first["fitted_on_train_only"] == second["fitted_on_train_only"]
    assert first["selected_on_calibration_only"]["model_track"] == second["selected_on_calibration_only"]["model_track"]
    assert (
        first["selected_on_calibration_only"]["late_market_track"]
        == second["selected_on_calibration_only"]["late_market_track"]
    )
    assert first["untouched_test"] != second["untouched_test"]


def test_outputs_are_isolated_and_explicit(tmp_path):
    sentinel = tmp_path / "sentient_state.json"
    sentinel.write_text('{"do_not_touch": true}', encoding="utf-8")
    output = tmp_path / "analysis"

    summary = run_challenger(_sample_races(), output, bootstrap_samples=20)

    assert sentinel.read_text(encoding="utf-8") == '{"do_not_touch": true}'
    assert summary["safety"] == {
        "live_state_written": False,
        "canonical_shadow_state_written": False,
        "supabase_writes": False,
        "model_weights_changed": False,
        "production_scoring_changed": False,
        "promotion_authorized": False,
    }
    assert {path.name for path in output.iterdir()} == {
        "prime_probability_calibration_challenger.json",
        "prime_probability_calibration_challenger.md",
        "disposable_calibration_parameters.json",
        "holdout_race_scores.csv",
    }
    payload = json.loads((output / "prime_probability_calibration_challenger.json").read_text())
    assert payload["time_contract"].startswith("whole-day chronological")
    assert payload["market_contract"].endswith("not morning")
