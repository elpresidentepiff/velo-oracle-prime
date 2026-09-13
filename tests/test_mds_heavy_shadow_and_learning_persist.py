"""
Tests for the 2026-09-13 additions:
  - scripts/ops/run_mds_heavy_shadow_today.py  (blend must follow the live engine's rules,
    and must refuse to score from the generated_at fallback)
  - scripts/ops/persist_nightly_learning_events.py (jsonl -> velo_learning_events mapping)
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "ops" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mds = _load("run_mds_heavy_shadow_today")
nle = _load("persist_nightly_learning_events")


def test_blend_uses_shadow_weights_and_ignores_improvement():
    preds = [
        {"sqpe_v17_prob": 0.50, "market_deception_score": 0.10, "improvement_score": 0.90},
        {"sqpe_v17_prob": 0.10, "market_deception_score": 0.40, "improvement_score": 0.00},
    ]
    s = mds.blend(preds, mds.WEIGHTS)
    assert abs(s[0] - (0.1 * 0.50 + 0.9 * 0.10)) < 1e-12
    assert abs(s[1] - (0.1 * 0.10 + 0.9 * 0.40)) < 1e-12
    assert mds._rank(s) == [2, 1]


def test_blend_drops_field_constant_component_but_never_sqpe():
    preds = [
        {"sqpe_v17_prob": 0.30, "market_deception_score": 0.05},
        {"sqpe_v17_prob": 0.20, "market_deception_score": 0.05},
    ]
    s = mds.blend(preds, mds.WEIGHTS)
    # MDS constant across the field -> excluded for the race, ranking falls back to sqpe
    assert abs(s[0] - 0.30) < 1e-12 and abs(s[1] - 0.20) < 1e-12
    const_sqpe = [{"sqpe_v17_prob": 0.2, "market_deception_score": 0.3},
                  {"sqpe_v17_prob": 0.2, "market_deception_score": 0.1}]
    s2 = mds.blend(const_sqpe, mds.WEIGHTS)
    assert abs(s2[0] - (0.1 * 0.2 + 0.9 * 0.3)) < 1e-12   # sqpe kept even when constant


def test_blend_missing_components_reweight_over_what_is_present():
    s = mds.blend([{"sqpe_v17_prob": 0.4}, {"sqpe_v17_prob": 0.2, "market_deception_score": 0.5}], mds.WEIGHTS)
    assert abs(s[0] - 0.4) < 1e-12
    assert mds._rank([None, 0.3, 0.7]) == [None, 2, 1]


def test_shadow_refuses_generated_at_fallback(tmp_path, capsys):
    with patch.object(mds, "load_verdicts", return_value=([{"race_id": "1", "full_analysis": {}}], "generated_at")), \
         patch.object(sys, "argv", ["x", "--date", "2026-09-14"]), \
         patch.object(mds, "ROOT", tmp_path):
        assert mds.main() == 2
    assert "REFUSED" in capsys.readouterr().out
    assert not (tmp_path / "data" / "reports").exists()


def test_learning_event_mapping(tmp_path):
    (tmp_path / "data").mkdir()
    events = [
        {"event_type": "result_confirmed", "event_date": "2026-06-10", "race_id": "919917",
         "idempotency_key": "919917:2026-06-10", "sentient_state_target": "data\\sentient_state_shadow_daily.json",
         "learning_allowed": True, "hfs_features_used": False, "prediction_snapshot": {"horse": "X", "horse_id": "123"},
         "result_snapshot": {"winner_id": "123"}, "prediction_result": "WIN", "loss_type": None},
        {"race_id": "999", "prediction_snapshot": {}, "prediction_result": None},   # partial write
    ]
    (tmp_path / "data" / "nightly_eod_learning_events_2026_06_10.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events), encoding="utf-8")
    (tmp_path / "data" / "nightly_eod_learning_status_2026_06_10.json").write_text(
        json.dumps({"engine_updates_applied_first_run": 37}), encoding="utf-8")
    with patch.object(nle, "ROOT", tmp_path):
        rows, audit = nle.build_rows("2026-06-10")
    assert audit["skipped_partial"] == 1 and len(rows) == 1
    r = rows[0]
    assert r["target_state_name"] == "sentient_state_shadow_daily"     # windows path + extension stripped
    assert r["consumption_id"] == "919917:2026-06-10:sentient_state_shadow_daily"
    assert r["horse_id"] == "123" and r["missing_hfs_context"] is True
    assert r["consumed_shadow"] is True and r["consumed_live"] is False
    assert r["result"]["prediction_result"] == "WIN"
