from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_forecasting_shadow_package",
    ROOT / "scripts" / "ops" / "run_forecasting_shadow_package.py",
)
shadow = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = shadow
SPEC.loader.exec_module(shadow)


def _predictions():
    return [
        {"horse": "A", "horse_id": "1", "velo_prime_prob": 0.64, "sqpe_v17_prob": 0.40,
         "improvement_score": 0.90, "market_deception_score": 0.10},
        {"horse": "B", "horse_id": "2", "velo_prime_prob": 0.24, "sqpe_v17_prob": 0.30,
         "improvement_score": 0.10, "market_deception_score": 0.40},
        {"horse": "C", "horse_id": "3", "velo_prime_prob": 0.12, "sqpe_v17_prob": 0.20,
         "improvement_score": 0.20, "market_deception_score": 0.20},
    ]


def test_calibration_preserves_ranking_and_normalises():
    probabilities = shadow.calibrated_g_probabilities(_predictions())
    assert shadow._ranks(probabilities) == [1, 2, 3]
    assert abs(sum(probabilities) - 1.0) < 1e-12
    assert probabilities[0] < 0.64  # beta < 1 flattens the overconfident field


def test_sqpe_mds_excludes_improvement_and_market_blind_uses_frozen_contract():
    predictions = _predictions()
    original = shadow.sqpe_mds_probabilities(predictions)
    predictions[0]["improvement_score"] = -9999
    assert shadow.sqpe_mds_probabilities(predictions) == original
    ranker = shadow.market_blind_core_probabilities(predictions)
    assert abs(sum(ranker) - 1.0) < 1e-12
    assert set(shadow.RANKER_COEFFICIENTS) == {
        "sqpe_v17_prob", "improvement_score", "market_deception_score"
    }


def test_packet_is_explicitly_shadow_only_and_contains_all_lanes():
    verdicts = [{
        "race_id": "R1", "generated_at": "2026-09-26T08:00:00Z",
        "full_analysis": {"predictions": _predictions()},
    }]
    packet = shadow.build_packet("2026-09-26", verdicts, "race_id")
    assert packet["race_count"] == 1
    assert packet["velo_scoring_allowed"] is False
    assert packet["stake_authorised"] is False
    assert packet["supabase_write_authorised"] is False
    assert packet["promotion_authorised"] is False
    assert set(packet["races"][0]["lanes"]) == set(shadow.LANE_MODELS)


def test_main_refuses_historical_window_without_loading_or_writing(tmp_path, capsys):
    with patch.object(sys, "argv", ["x", "--date", "2026-09-24"]), \
         patch.object(shadow, "ROOT", tmp_path), \
         patch.object(shadow, "load_verdicts") as loader:
        assert shadow.main() == 2
    loader.assert_not_called()
    assert "REFUSED" in capsys.readouterr().out
    assert not (tmp_path / "data").exists()


def test_main_refuses_generated_at_fallback(tmp_path, capsys):
    with patch.object(sys, "argv", ["x", "--date", "2026-09-26"]), \
         patch.object(shadow, "ROOT", tmp_path), \
         patch.object(shadow, "load_verdicts", return_value=([], "generated_at")):
        assert shadow.main() == 2
    assert "exact race-date membership" in capsys.readouterr().out
    assert not (tmp_path / "data").exists()


def test_main_writes_only_explicit_report_packet(tmp_path):
    verdicts = [{"race_id": "R1", "generated_at": "2026-09-26T08:00:00Z",
                 "full_analysis": json.dumps({"predictions": _predictions()})}]
    with patch.object(sys, "argv", ["x", "--date", "2026-09-26"]), \
         patch.object(shadow, "ROOT", tmp_path), \
         patch.object(shadow, "load_verdicts", return_value=(verdicts, "race_id")):
        assert shadow.main() == 0
    output = tmp_path / "data" / "reports" / "forecasting_shadow_package_2026_09_26.json"
    assert output.exists()
    assert list((tmp_path / "data").rglob("*.*")) == [output]
