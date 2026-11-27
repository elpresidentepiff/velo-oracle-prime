from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "evaluate_rpdc_tag_matched_controls",
    ROOT / "scripts" / "ops" / "evaluate_rpdc_tag_matched_controls.py",
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _tag(race_id: str, horse_id: str, tag: str = "MARK_READY") -> dict:
    return {"race_id": race_id, "horse_id": horse_id, "horse": horse_id, "tag": tag}


def _candidate(race_id: str, horse_id: str) -> dict:
    return {"race_id": race_id, "horse_id": horse_id, "horse": horse_id}


def _result(race_id: str, horse_id: str, position: int | None, sp: float | None = 3.0) -> dict:
    return {"race_id": race_id, "horse_id": horse_id, "horse": horse_id, "position_int": position, "sp_dec": sp}


def test_compares_a_tag_only_with_settled_non_tagged_runners_in_same_races():
    report = module.evaluate(
        [_tag("r1", "a"), _tag("r2", "d")],
        [_candidate("r1", "a"), _candidate("r1", "b"), _candidate("r1", "c"),
         _candidate("r2", "d"), _candidate("r2", "e")],
        [_result("r1", "a", 1), _result("r1", "b", 2), _result("r1", "c", 4),
         _result("r2", "d", 3), _result("r2", "e", 1)],
    )

    card = report["tag_scorecards"][0]
    assert report["status"] == "OK"
    assert card["tag"] == "MARK_READY"
    assert card["treatment"]["n"] == 2
    assert card["treatment"]["wins"] == 1
    assert card["treatment"]["top_3"] == 2
    assert card["same_race_control"]["n"] == 3
    assert card["same_race_control"]["wins"] == 1
    assert card["same_race_control"]["top_3"] == 2
    assert card["delta_win_rate_pp"] == 16.7


def test_control_excludes_runner_with_same_tag_even_when_other_tags_overlap():
    report = module.evaluate(
        [_tag("r1", "a", "MARK_READY"), _tag("r1", "b", "MARK_READY"), _tag("r1", "b", "CYCLE_RUN_2")],
        [_candidate("r1", "a"), _candidate("r1", "b"), _candidate("r1", "c")],
        [_result("r1", "a", 1), _result("r1", "b", 2), _result("r1", "c", 3)],
    )

    mark_ready = next(card for card in report["tag_scorecards"] if card["tag"] == "MARK_READY")
    cycle = next(card for card in report["tag_scorecards"] if card["tag"] == "CYCLE_RUN_2")
    assert mark_ready["treatment"]["n"] == 2
    assert mark_ready["same_race_control"]["n"] == 1
    assert cycle["treatment"]["n"] == 1
    assert cycle["same_race_control"]["n"] == 2


def test_missing_or_unsettled_identity_is_reported_not_name_matched_or_invented():
    report = module.evaluate(
        [_tag("r1", "a"), _tag("r1", "missing")],
        [_candidate("r1", "a"), _candidate("r1", "b")],
        [_result("r1", "a", 1), _result("r1", "b", None)],
    )

    card = report["tag_scorecards"][0]
    assert card["tagged_missing_candidate"] == 1
    assert card["control_unresolved_result"] == 1
    assert card["same_race_control"]["n"] == 0
    assert report["guardrails"]["identity_fallback"] == "DISALLOWED"


def test_empty_settlement_is_explicit_not_a_silent_success():
    report = module.evaluate([], [], [])
    assert report["status"] == "NO_SETTLED_TAG_EVIDENCE"
    assert report["tag_scorecards"] == []


def test_eod_and_artifact_persistence_are_wired_for_the_report():
    eod_source = (ROOT / "scripts" / "ops" / "run_full_raceday_eod.py").read_text(encoding="utf-8")
    persistence_source = (ROOT / "scripts" / "ops" / "persist_daily_artifacts.py").read_text(encoding="utf-8")
    assert "Step 13B: RPDC tag matched-control shadow" in eod_source
    assert "evaluate_rpdc_tag_matched_controls.py" in eod_source
    assert '"rpdc_tag_matched_control"' in persistence_source
