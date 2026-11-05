"""The no-RPR shadow lane died silently because its model file was git-ignored and never shipped.

``predict_sqpe_no_rpr_shadow`` returns ``(None, [])`` when the file is missing, so the canonical
scorecard filled the lane with tied, NULL scores. These tests make that failure loud.
"""
from __future__ import annotations

from app.services import sqpe_v17_service as service

RACE = {
    "race_id": "t", "course": "Kempton", "distance": "1m", "going": "good",
    "type": "flat", "field_size": 10, "date": "2026-11-05",
}


def _features(rating: float, odds: float) -> dict:
    runner = {
        "horse_name": "X", "age": 5, "official_rating": rating, "rpr": rating + 5, "ts": rating,
        "odds": odds, "best_odds_decimal": odds,
    }
    return service.build_v17_feature_vector(runner, RACE)


def test_the_model_file_ships_with_the_repo() -> None:
    assert service.NO_RPR_SHADOW_MODEL_PATH.exists(), (
        f"{service.NO_RPR_SHADOW_MODEL_PATH} is missing: the no-RPR lane would silently output nothing. "
        "models/**/*.pkl is git-ignored, so the file must be added with `git add -f`."
    )


def test_it_produces_a_probability_not_none() -> None:
    prob, names = service.predict_sqpe_no_rpr_shadow(_features(80, 5.0))
    assert prob is not None and 0.0 < prob < 1.0
    assert len(names) == 25


def test_every_input_the_model_expects_is_actually_built() -> None:
    _, names = service.predict_sqpe_no_rpr_shadow(_features(80, 5.0))
    absent = [n for n in names if n not in _features(80, 5.0)]
    assert absent == [], f"inputs silently defaulting to 0.0: {absent}"


def test_the_model_does_not_use_rpr_or_ts() -> None:
    _, names = service.predict_sqpe_no_rpr_shadow(_features(80, 5.0))
    assert not [n for n in names if "rpr" in n.lower() or n.lower() in {"ts", "topspeed"}]


def test_the_model_responds_to_its_own_inputs() -> None:
    """Not a constant stub. (Runner rating/odds are not among its inputs: it is the no-RPR model.
    Its inputs come from each horse's form history, which the extractor fetches from the database,
    so a real field can only be checked after a scoring run.)"""
    _, names = service.predict_sqpe_no_rpr_shadow(_features(80, 5.0))
    flat, _ = service.predict_sqpe_no_rpr_shadow({})
    moved, _ = service.predict_sqpe_no_rpr_shadow({n: 3.0 for n in names})
    assert flat is not None and moved is not None and flat != moved


def test_the_ensemble_never_reads_it() -> None:
    """Shadow only: the live ensemble must not consume the no-RPR probability."""
    from pathlib import Path

    ensemble = Path(service.__file__).resolve().parents[2] / "src" / "intelligence" / "velo_prime_ensemble.py"
    assert "no_rpr" not in ensemble.read_text(encoding="utf-8")
