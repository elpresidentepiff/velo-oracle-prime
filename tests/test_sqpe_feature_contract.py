from pathlib import Path

import joblib
import pytest

from app.services.sqpe_v17_service import (
    _feature_names_for_model,
    _resolve_decimal_odds,
    build_v17_feature_vector,
    predict_sqpe_no_rpr_shadow,
)


def test_resolve_decimal_odds_probability_and_decimal_contract():
    assert _resolve_decimal_odds({"best_odds_decimal": 0.5}) == 2.0
    assert _resolve_decimal_odds({"best_odds_decimal": 4.0}) == 4.0
    assert _resolve_decimal_odds({"sp": "5/2"}) == 3.5
    assert _resolve_decimal_odds({}) == 10.0


def test_build_v17_feature_vector_uses_preinjected_field_features():
    race = {"distance": "1m", "going": "Good", "race_class": "Class 4", "runners": [{}, {}, {}]}
    runner = {
        "horse_name": "Law Horse",
        "official_rating": 82,
        "rpr": 91,
        "or_vs_field": 7.5,
        "rpr_vs_field": 4.5,
        "sp_rank": 1.0,
        "is_fav": 1.0,
        "_resolved_sp_dec": 3.25,
    }

    feats = build_v17_feature_vector(runner, race)

    assert feats["or_vs_field"] == 7.5
    assert feats["rpr_vs_field"] == 4.5
    assert feats["sp_rank"] == 1.0
    assert feats["is_fav"] == 1.0
    assert feats["sp_dec"] == 3.25


def test_no_rpr_staging_model_feature_contract_is_25_if_artifact_exists():
    model_path = Path("models/sqpe_v17_no_rpr_staging/sqpe_v17_no_rpr.pkl")
    if not model_path.exists():
        pytest.skip("no-RPR staging artifact not present")

    model = joblib.load(model_path)
    feature_names = _feature_names_for_model(model)

    assert len(feature_names) == 25
    assert "or_vs_field" in feature_names
    assert "rpr_vs_field" not in feature_names
    assert "sp_dec" not in feature_names



def test_no_rpr_shadow_predicts_without_live_feature_contract_mismatch():
    model_path = Path("models/sqpe_v17_no_rpr_staging/sqpe_v17_no_rpr.pkl")
    if not model_path.exists():
        pytest.skip("no-RPR staging artifact not present")

    race = {"distance": "1m", "going": "Good", "race_class": "Class 4", "runners": [{}, {}, {}]}
    runner = {
        "official_rating": 82,
        "or_vs_field": 7.5,
        "weight_lbs": 126,
        "draw": 2,
        "age": 4,
        "runs_since_win": 3,
        "runs_since_place": 1,
        "distance_fit_score": 0.7,
        "going_fit_score": 0.4,
        "trainer_timing_score": 0.3,
    }
    feats = build_v17_feature_vector(runner, race)

    prob, feature_names = predict_sqpe_no_rpr_shadow(feats)

    assert prob is not None
    assert 0.0 <= prob <= 1.0
    assert len(feature_names) == 25
    assert "rpr_vs_field" not in feature_names
