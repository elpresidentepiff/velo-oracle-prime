from __future__ import annotations

import json

import pytest

from scripts.ops import build_canonical_learning_events as learning
from scripts.ops import build_canonical_model_scorecard as scorecard
from scripts.ops import run_results_sigma as sigma
from src.velo.learning import result_source_selector as selector


def _void(race_id: str) -> dict:
    return {
        "race_id": race_id,
        "race_status": "ABANDONED",
        "race_status_evidence": {
            "source_name": "official result authority",
            "source_url": "https://example.test/results",
            "observed_at": "2026-09-30T09:00:00Z",
        },
    }


def test_35_run_plus_4_authoritatively_abandoned_is_complete(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    run_races = []
    expected_runners = {}
    for index in range(35):
        race_id = f"RUN{index}"
        horse_id = f"H{index}"
        run_races.append({
            "race_id": race_id,
            "runners": [{"horse_id": horse_id, "horse": horse_id, "position": "1"}],
        })
        expected_runners[race_id] = {horse_id}
    void_races = [_void(race_id) for race_id in ("929767", "929766", "929768", "929769")]
    (results_dir / "rp_results_2026_09_29.json").write_text(
        json.dumps({"results": run_races}), encoding="utf-8"
    )
    (results_dir / "race_status_2026_09_29.json").write_text(
        json.dumps({
            "date": "2026-09-29", "contract": "GOVERNED_RACE_STATUS_V1",
            "races": void_races,
        }), encoding="utf-8"
    )
    expected_ids = {race["race_id"] for race in run_races + void_races}
    selected = selector.select_result_source(
        "2026-09-29",
        results_dir=results_dir,
        expected_race_ids=expected_ids,
        expected_runners_by_race=expected_runners,
    )
    assert selected.completeness["expected_races"] == 39
    assert selected.completeness["races_fully_accounted"] == 39
    assert selected.completeness["missing_races"] == []
    assert selected.completeness["full_universe_complete"] is True


def test_bare_abandoned_string_is_not_authoritative():
    assert selector.authoritative_race_void({"race_id": "R1", "status": "ABANDONED"}) is False


def test_sigma_excludes_abandoned_races_from_coverage_denominator():
    expected_to_run, coverage = sigma._coverage_after_race_voids(35, 39, 4)
    assert expected_to_run == 35
    assert coverage == 1.0


@pytest.mark.parametrize("counts", [(-1, 39, 4), (35, -1, 4), (35, 39, -1), (36, 39, 4), (0, 3, 4)])
def test_sigma_rejects_impossible_coverage_counts(counts):
    with pytest.raises(ValueError):
        sigma._coverage_after_race_voids(*counts)


def test_sigma_rejects_result_status_identity_collision():
    with pytest.raises(ValueError, match="collision"):
        sigma._merge_sigma_results_with_status(
            [{"race_id": "R1", "runners": [{"horse": "Alpha", "position": "1"}]}],
            [_void("R1")],
        )


def test_abandoned_race_is_void_not_non_runner_or_model_outcome(monkeypatch):
    outcome = scorecard._runner_lookup(_void("R1"), "Never Started")
    assert outcome == {
        "position": None,
        "outcome_code": "ABANDONED",
        "outcome_status": "UNKNOWN",
        "subject_is_non_runner": False,
        "settlement_status": "VOID",
        "stake_void": True,
        "win": None,
        "frame": None,
    }
    row = {
        "id": 7, "run_date": "2026-09-29", "race_id": "R1", "model_name": "TEST",
        "horse": "Never Started", "subject_outcome_code": "ABANDONED",
        "subject_outcome_status": "UNKNOWN", "subject_is_non_runner": False,
        "settlement_status": "VOID", "stake_void": True,
        "result_source_complete": True, "official_evaluation_eligible": False,
        "dashboard_metrics_eligible": False,
        "evaluation_ineligible_reason": "RACE_ABANDONED_VOID_NO_SUBJECT_OUTCOME",
        "learning_class": "RACE_ABANDONED_VOID",
    }
    monkeypatch.setattr(learning, "_preflight", lambda _date: [row])
    event = learning.build_events("2026-09-29")[0][0]
    assert event["event_type"] == "RACE_ABANDONED_VOID"
    assert event["promotion_eligible"] is False
    assert event["official_evaluation_eligible"] is False
    assert event["dashboard_metrics_eligible"] is False
    assert "ineligible for model learning" in event["lesson"]


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.update(date="2026-09-28"),
        lambda payload: payload.update(contract="UNKNOWN"),
        lambda payload: payload.update(races={}),
        lambda payload: payload["races"][0].update(race_status="abandoned"),
        lambda payload: payload["races"][0]["race_status_evidence"].update(source_url="/relative"),
        lambda payload: payload["races"][0]["race_status_evidence"].update(observed_at="2026-09-30T09:00:00"),
        lambda payload: payload["races"][0]["race_status_evidence"].update(extra="not-in-contract"),
    ],
)
def test_malformed_governed_status_document_fails_closed(tmp_path, mutator):
    payload = {
        "date": "2026-09-29",
        "contract": "GOVERNED_RACE_STATUS_V1",
        "races": [_void("R1")],
    }
    mutator(payload)
    path = tmp_path / "race_status_2026_09_29.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        selector.load_race_status_evidence("2026-09-29", tmp_path)


def test_duplicate_and_blank_race_ids_fail_closed(tmp_path):
    for rows in ([_void("R1"), _void("R1")], [_void(" ")]):
        (tmp_path / "race_status_2026_09_29.json").write_text(
            json.dumps({"date": "2026-09-29", "contract": "GOVERNED_RACE_STATUS_V1", "races": rows}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            selector.load_race_status_evidence("2026-09-29", tmp_path)


def test_result_status_collision_and_impossible_parse_count_fail_closed(tmp_path):
    status = {"date": "2026-09-29", "contract": "GOVERNED_RACE_STATUS_V1", "races": [_void("R1")]}
    (tmp_path / "race_status_2026_09_29.json").write_text(json.dumps(status), encoding="utf-8")
    (tmp_path / "rp_results_2026_09_29.json").write_text(
        json.dumps({"races_parsed": 1, "results": [{"race_id": "R1", "runners": []}]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="collision"):
        selector.select_result_source("2026-09-29", results_dir=tmp_path)
    (tmp_path / "rp_results_2026_09_29.json").write_text(
        json.dumps({"races_parsed": 2, "results": [{"race_id": "RUN1", "runners": []}]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="impossible"):
        selector.select_result_source("2026-09-29", results_dir=tmp_path)


def test_actual_scorecard_builder_voids_every_model_row(monkeypatch, tmp_path):
    root = tmp_path
    results_dir = root / "data" / "results"
    results_dir.mkdir(parents=True)
    (results_dir / "rp_results_2026_09_29.json").write_text(
        json.dumps({"races_parsed": 0, "results": []}), encoding="utf-8"
    )
    (results_dir / "race_status_2026_09_29.json").write_text(
        json.dumps({
            "date": "2026-09-29", "contract": "GOVERNED_RACE_STATUS_V1",
            "races": [_void("R1")],
        }), encoding="utf-8"
    )
    predictions = [
        {"horse": "Alpha", "horse_id": "H1", "velo_prime_prob": 0.7, "sqpe_no_rpr_shadow_prob": 0.6},
        {"horse": "Beta", "horse_id": "H2", "velo_prime_prob": 0.3, "sqpe_no_rpr_shadow_prob": 0.4},
    ]
    monkeypatch.setattr(scorecard, "ROOT", root)
    monkeypatch.setattr(scorecard, "_ensure_env", lambda: None)
    monkeypatch.setattr(
        scorecard, "load_verdicts",
        lambda *_args, **_kwargs: ([{"race_id": "R1", "full_analysis": {"predictions": predictions}}], "test"),
    )
    rows, _audit = scorecard.build_scorecard("2026-09-29")
    assert len(rows) == 2
    for row in rows:
        assert row["settlement_status"] == "VOID"
        assert row["stake_void"] is True
        assert row["subject_outcome_status"] == "UNKNOWN"
        assert row["subject_outcome_code"] == "ABANDONED"
        assert row["win"] is None and row["frame"] is None
        assert row["official_evaluation_eligible"] is False
        assert row["dashboard_metrics_eligible"] is False
        assert row["learning_class"] == "RACE_ABANDONED_VOID"
