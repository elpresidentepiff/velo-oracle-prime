from scripts.ops.build_formfav_premium_shadow_ablation import (
    analyse_static_blends,
    first_market_flip,
    normalise_name,
)


def test_normalise_name_handles_punctuation_and_accents():
    assert normalise_name("L'Île d'Or") == "liledor"


def test_static_blend_reports_top_change_without_mutating_prime():
    prime = {"alpha": 0.40, "beta": 0.35, "gamma": 0.25}
    formfav = {"alpha": 0.20, "beta": 0.60, "gamma": 0.20}
    before = dict(prime)

    result = analyse_static_blends(prime, formfav, alphas=(0.10, 0.30))

    assert result["0.10"]["top"] == "alpha"
    assert result["0.10"]["changed"] is False
    assert result["0.30"]["top"] == "beta"
    assert result["0.30"]["changed"] is True
    assert prime == before


def test_first_market_flip_records_first_adequately_covered_minute():
    prime = {"alpha": 0.40, "beta": 0.35}
    observations = [
        {
            "captured_at": "2026-11-04T10:00:10Z",
            "horse_name": "Alpha",
            "market_payload": {"market": {"fairProbability": 0.20}},
        },
        {
            "captured_at": "2026-11-04T10:00:40Z",
            "horse_name": "Beta",
            "market_payload": {"market": {"fairProbability": 0.80}},
        },
    ]

    result = first_market_flip(prime, observations, alpha=0.20)

    assert result == {
        "captured_minute_utc": "2026-11-04T10:00:00Z",
        "from": "alpha",
        "to": "beta",
        "coverage": 1.0,
        "matched_runners": 2,
    }


def test_market_flip_requires_minimum_coverage():
    prime = {"alpha": 0.40, "beta": 0.35, "gamma": 0.25}
    observations = [
        {
            "captured_at": "2026-11-04T10:00:10Z",
            "horse_name": "Beta",
            "market_payload": {"market": {"fairProbability": 0.99}},
        }
    ]

    assert first_market_flip(prime, observations, alpha=0.30) is None
