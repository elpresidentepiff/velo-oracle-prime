import json

import numpy as np
import pytest

from scripts.analysis.prime_market_blind_ranker_challenger import (
    CORE_FEATURES,
    feature_matrix,
    pairwise_training_data,
    run_ranker_challenger,
)


def _race(day: int, winner: int) -> dict:
    base = [0.55, 0.30, 0.15]
    g = [0.52, 0.31, 0.17]
    market = [0.45, 0.35, 0.20]
    feature_rows = [
        [0.60, 0.10, 0.20, 0.55, 0.10, 0.75, 0.02],
        [0.30, 0.30, 0.50, 0.35, 0.30, 0.50, 0.01],
        [0.10, 0.60, 0.30, 0.20, 0.60, 0.25, 0.00],
    ]
    all_features = (
        "sqpe_v17_prob",
        "improvement_score",
        "market_deception_score",
        "place_prob",
        "longshot_prob",
        "spotlight_score",
        "nds_score",
    )
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
        source.append(dict(zip(all_features, feature_rows[index], strict=True)))
    return {
        "race_id": f"race-{day:02d}",
        "race_date": f"2026-03-{day:02d}",
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


def test_pairwise_rows_are_balanced_and_antisymmetric():
    x_train, y_train = pairwise_training_data([_race(1, 0)], CORE_FEATURES)
    assert x_train.shape == (4, 3)
    assert y_train.tolist() == [1, 0, 1, 0]
    assert x_train[0] == pytest.approx(-x_train[1])
    assert x_train[2] == pytest.approx(-x_train[3])


def test_feature_matrix_uses_only_requested_fields():
    matrix = feature_matrix(_race(1, 0), CORE_FEATURES)
    assert matrix.shape == (3, 3)
    assert np.isfinite(matrix).all()
    assert matrix[0].tolist() == pytest.approx([0.60, 0.10, 0.20])


def test_holdout_cannot_change_fitting_or_selection(tmp_path):
    first = run_ranker_challenger(_races(test_winner=1), tmp_path / "first", bootstrap_samples=20)
    second = run_ranker_challenger(_races(test_winner=2), tmp_path / "second", bootstrap_samples=20)
    assert first["fitted_on_train_only"] == second["fitted_on_train_only"]
    assert first["selected_on_calibration_only"]["variant"] == second["selected_on_calibration_only"]["variant"]
    assert first["untouched_test"] != second["untouched_test"]


def test_outputs_are_disposable_and_market_blind(tmp_path):
    sentinel = tmp_path / "sentient_state.json"
    sentinel.write_text('{"untouched": true}', encoding="utf-8")
    output = tmp_path / "analysis"
    summary = run_ranker_challenger(_races(), output, bootstrap_samples=20)
    assert sentinel.read_text(encoding="utf-8") == '{"untouched": true}'
    assert not any(summary["market_blind_contract"].values())
    assert summary["safety"]["fitted_model_persisted"] is False
    assert {path.name for path in output.iterdir()} == {
        "prime_market_blind_ranker_challenger.json",
        "prime_market_blind_ranker_challenger.md",
        "disposable_ranker_parameters.json",
        "holdout_ranker_metrics.csv",
    }
    payload = json.loads((output / "prime_market_blind_ranker_challenger.json").read_text())
    assert payload["classification"] == "ANALYSIS_ONLY"
