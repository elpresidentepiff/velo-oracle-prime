from __future__ import annotations

import json

from app.core.canonical_dashboard_metrics import build_canonical_dashboard_payload
from scripts.ops import build_canonical_model_scorecard as scorecard
from src.velo.side_shadow import SIDE_SHADOW_MODELS, is_side_shadow

DAY = "2026-09-28"


def _row(model: str, race: int, *, win: bool, lane: str = "main", captured: float | None = None) -> dict:
    return {
        "run_date": DAY, "race_id": str(race), "off_time": f"1{race}:00",
        "model_name": model, "lane_name": lane, "rank": 1,
        "truth_contract_version": "CANONICAL_TRUTH_V2",
        "horse": f"Horse {race}", "horse_id": f"h{race}",
        "dashboard_metrics_eligible": True, "settlement_status": "SETTLED",
        "subject_outcome_code": "1" if win else "5", "win": win, "frame": win,
        "captured_odds_dec": captured, "settled_sp_dec": 3.0,
        "odds_timestamp_before_off": captured is not None,
        "odds_capture_ts": f"{DAY}T08:00:00+00:00" if captured else None,
        "source_path": f"data/reports/captain_velo_shadow_{DAY.replace('-', '_')}.json" if captured else None,
        "price_source": "CAPTAIN_FORWARD_PACKET_DECIMAL_ODDS" if captured else None,
    }


def test_captain_is_a_side_shadow_and_the_main_model_is_not() -> None:
    assert "CAPTAIN_VELO_VALUE_V1" in SIDE_SHADOW_MODELS
    assert is_side_shadow("captain_velo_value_v1") and is_side_shadow(" CAPTAIN_VELO_VALUE_V1 ")
    for main in ("MAIN_VELO_PRIME", "OLD_VELO_WIN_ROLE", "MDS_HEAVY_SHADOW_V1", None, ""):
        assert is_side_shadow(main) is False


def test_adding_captain_rows_changes_none_of_the_main_models_numbers() -> None:
    main_rows = [_row("MAIN_VELO_PRIME", race, win=race % 3 == 0) for race in range(1, 8)]
    captain_rows = [
        _row("CAPTAIN_VELO_VALUE_V1", race, win=race % 2 == 0, lane="selective_value_forward_shadow_only", captured=9.0)
        for race in range(1, 8)
    ]
    alone = build_canonical_dashboard_payload(main_rows, DAY)
    both = build_canonical_dashboard_payload(main_rows + captain_rows, DAY)

    def main_summary(payload):
        return next(m for m in payload["models"] if m["model_name"] == "MAIN_VELO_PRIME")

    assert main_summary(both) == main_summary(alone)
    assert main_summary(both)["side_shadow"] is False
    assert alone["side_shadow_models"] == []
    assert both["side_shadow_models"] == ["CAPTAIN_VELO_VALUE_V1"]
    assert next(m for m in both["models"] if m["model_name"].startswith("CAPTAIN"))["side_shadow"] is True


def _packet_fixture(tmp_path, monkeypatch, *, with_packet: bool):
    reports = tmp_path / "data" / "reports"
    results = tmp_path / "data" / "results"
    reports.mkdir(parents=True)
    results.mkdir(parents=True)
    if with_packet:
        packet = {
            "generated_at": f"{DAY}T09:00:00+00:00", "model_version": "CAPTAIN_VELO_VALUE_V1",
            "races": [{"race_id": "R1", "course": "TEST", "off_time": "14:00", "action": "SHADOW_SELECTION",
                       "selection": {"horse": "Value", "horse_id": "H1", "decimal_odds": 11.0,
                                     "quoted_expected_edge": 0.12}}],
        }
        (reports / f"captain_velo_shadow_{DAY.replace('-', '_')}.json").write_text(json.dumps(packet), encoding="utf-8")
    (results / f"rp_results_{DAY.replace('-', '_')}.json").write_text(json.dumps({"results": [{
        "race_id": "R1", "course": "TEST", "off": "14:00",
        "runners": [{"horse": "Value", "horse_id": "H1", "position": "1", "sp_dec": 4.33}],
    }]}), encoding="utf-8")
    monkeypatch.setattr(scorecard, "ROOT", tmp_path)
    monkeypatch.setattr(scorecard, "load_verdicts", lambda *_a, **_k: ([], "race_id"))


def test_captain_rows_are_never_stake_authorised_or_on_the_main_board(tmp_path, monkeypatch) -> None:
    _packet_fixture(tmp_path, monkeypatch, with_packet=True)
    rows, _audit = scorecard.build_scorecard(DAY)
    captain = [r for r in rows if r["model_name"] == "CAPTAIN_VELO_VALUE_V1"]
    assert len(captain) == 1
    assert captain[0]["stake_authorised"] is False
    assert captain[0]["dashboard_visible"] is False
    # its price evidence is kept: that is the one thing a side shadow is for
    assert captain[0]["captured_odds_dec"] == 11.0 and captain[0]["price_source"] == "CAPTAIN_FORWARD_PACKET_DECIMAL_ODDS"


def test_without_a_packet_there_are_no_captain_rows(tmp_path, monkeypatch) -> None:
    _packet_fixture(tmp_path, monkeypatch, with_packet=False)
    rows, audit = scorecard.build_scorecard(DAY)
    assert not [r for r in rows if r["model_name"] == "CAPTAIN_VELO_VALUE_V1"]
    assert "captain_velo_shadow" in audit["sources_missing"]
