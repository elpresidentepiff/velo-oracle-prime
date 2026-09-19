import json

import pytest

from scripts.analysis.prime_component_mechanism_ablation import (
    component_provider,
    run_ablation,
)


def _race(day: int, winner: int) -> dict:
    base = [0.60, 0.25, 0.15]
    g = [0.55, 0.28, 0.17]
    market = [0.45, 0.35, 0.20]
    sqpe = [0.60, 0.30, 0.10]
    improvement = [0.10, 0.30, 0.60]
    mds = [0.20, 0.50, 0.30]
    runners, source = [], []
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
        source.append(
            {
                "horse": name,
                "sqpe_v17_prob": sqpe[index],
                "improvement_score": improvement[index],
                "market_deception_score": mds[index],
            }
        )
    return {
        "race_id": f"race-{day:02d}",
        "race_date": f"2026-02-{day:02d}",
        "course": "Test",
        "off_time": "14:00",
        "winner_index": winner,
        "winner_name": runners[winner]["horse"],
        "winner_sp": 4.0,
        "runners": runners,
        "source_field": source,
    }


def _races(test_winner: int = 1) -> list[dict]:
    winners = [0, 1, 2, 0, 1, 2, 0, 1, 2, test_winner, test_winner, test_winner]
    return [_race(day, winner) for day, winner in enumerate(winners, start=1)]


def test_sqpe_component_provider_race_normalises():
    probabilities = component_provider(("sqpe_v17_prob",))(_race(1, 0))
    assert probabilities == pytest.approx([0.6, 0.3, 0.1])
    assert sum(probabilities) == pytest.approx(1.0)


def test_component_mix_uses_production_weight_pattern():
    probabilities = component_provider(("sqpe_v17_prob", "improvement_score"))(_race(1, 0))
    assert sum(probabilities) == pytest.approx(1.0)
    assert probabilities[0] > probabilities[1] > probabilities[2]
    assert probabilities[0] < 0.6


def test_holdout_outcomes_do_not_change_fit_or_selection(tmp_path):
    first = run_ablation(_races(test_winner=1), tmp_path / "first", bootstrap_samples=20)
    second = run_ablation(_races(test_winner=2), tmp_path / "second", bootstrap_samples=20)
    assert first["fitted_on_train_only"] == second["fitted_on_train_only"]
    assert first["selected_on_calibration_only"]["variant"] == second["selected_on_calibration_only"]["variant"]
    assert first["untouched_test"] != second["untouched_test"]


def test_outputs_are_explicit_and_live_state_is_untouched(tmp_path):
    sentinel = tmp_path / "sentient_state.json"
    sentinel.write_text('{"untouched": true}', encoding="utf-8")
    output = tmp_path / "analysis"
    summary = run_ablation(_races(), output, bootstrap_samples=20)
    assert sentinel.read_text(encoding="utf-8") == '{"untouched": true}'
    assert summary["safety"]["production_scoring_changed"] is False
    assert {path.name for path in output.iterdir()} == {
        "prime_component_mechanism_ablation.json",
        "prime_component_mechanism_ablation.md",
        "disposable_component_parameters.json",
        "holdout_variant_metrics.csv",
    }
    payload = json.loads((output / "prime_component_mechanism_ablation.json").read_text())
    assert payload["classification"] == "ANALYSIS_ONLY"
