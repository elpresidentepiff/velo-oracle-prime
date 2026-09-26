from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import captain_velo_challenger as captain
from scripts.ops import build_canonical_model_scorecard as scorecard
from scripts.ops import run_captain_velo_shadow as shadow


def _field():
    return [
        {"horse": "Market", "horse_id": "1", "sp_dec": 2.5, "sqpe_v17_prob": 0.20, "market_deception_score": 0.01},
        {"horse": "Value", "horse_id": "2", "sp_dec": 8.0, "sqpe_v17_prob": 0.55, "market_deception_score": 0.20},
        {"horse": "Other", "horse_id": "3", "sp_dec": 5.0, "sqpe_v17_prob": 0.25, "market_deception_score": 0.02},
    ]


def test_probability_surfaces_normalise_and_exclude_improvement():
    field = _field()
    first = captain.structural_probabilities(field)
    field[1]["improvement_score"] = 999.0
    second = captain.structural_probabilities(field)
    assert first == second
    assert sum(first or []) == pytest.approx(1.0)
    assert sum(captain.market_probabilities(field) or []) == pytest.approx(1.0)
    assert sum(captain.consensus_probabilities(field) or []) == pytest.approx(1.0)


def test_policy_abstains_without_complete_quotes_and_selects_only_clear_value():
    field = _field()
    pick = captain.select_value_pick(field)
    assert pick is not None
    assert pick["horse"] == "Value"
    assert pick["structural_market_ratio"] >= captain.MIN_STRUCTURAL_MARKET_RATIO
    assert pick["quoted_expected_edge"] >= captain.MIN_QUOTED_EXPECTED_EDGE
    field[0]["sp_dec"] = None
    assert captain.select_value_pick(field) is None


def test_forward_packet_is_explicitly_non_executing():
    field = _field()
    for row in field:
        row.update({"race_date": "2026-09-26", "race_id": "R1", "course": "TEST", "off_time": "12:00", "created_at": "2026-09-26T08:00:00+00:00"})
    packet = shadow.build_forward_packet("2026-09-26", {"R1": field})
    assert packet["classification"] == "FORWARD_ONLY_SHADOW_DECISION_PACKET"
    assert packet["shadow_selection_count"] == 1
    assert packet["safety"] == {
        "paper_sim_only": True,
        "bets_placed": False,
        "stakes_generated": False,
        "execution_allowed": False,
        "verdicts_written": False,
        "supabase_writes": False,
        "production_weights_changed": False,
        "production_scoring_changed": False,
        "promotion_authorized": False,
    }


def test_forward_main_refuses_reused_evidence_dates(tmp_path, capsys):
    output = tmp_path / "packet.json"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            "sys.argv",
            ["run_captain_velo_shadow.py", "--date", captain.EVIDENCE_END_DATE, "--output", str(output)],
        )
        assert shadow.main() == 2
    assert "[REFUSED]" in capsys.readouterr().out
    assert not output.exists()


def test_forward_packet_round_trips_strict_json(tmp_path):
    field = _field()
    packet = shadow.build_forward_packet("2026-09-26", {"R1": field})
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(packet, allow_nan=False), encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8"))["model_version"] == captain.MODEL_VERSION


def test_canonical_scorecard_ingests_only_captain_shadow_selections(tmp_path, monkeypatch):
    report_dir = tmp_path / "data" / "reports"
    report_dir.mkdir(parents=True)
    packet = shadow.build_forward_packet("2026-09-26", {"R1": _field()})
    (report_dir / "captain_velo_shadow_2026_09_26.json").write_text(
        json.dumps(packet, allow_nan=False), encoding="utf-8"
    )
    monkeypatch.setattr(scorecard, "ROOT", tmp_path)
    monkeypatch.setattr(scorecard, "load_verdicts", lambda *_args, **_kwargs: ([], "race_id"))
    rows, audit = scorecard.build_scorecard("2026-09-26")
    captain_rows = [row for row in rows if row["model_name"] == captain.MODEL_VERSION]
    assert len(captain_rows) == 1
    assert captain_rows[0]["horse"] == "Value"
    assert captain_rows[0]["policy_decision"] == "SHADOW_SELECTION"
    assert captain_rows[0]["stake_authorised"] is False
    assert audit["sources_found"]["captain_velo_shadow"] == "captain_velo_shadow_2026_09_26.json"
