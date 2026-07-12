"""Tests for scripts/audit/build_training_corpus_v2.py (LEARNING-LOOP-01A Phase 4)."""

import hashlib
import importlib.util
import os

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(REPO_ROOT, "scripts", "audit", "build_training_corpus_v2.py")


def _import_module():
    spec = importlib.util.spec_from_file_location("build_training_corpus_v2", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _import_module()


def _snapshot_row(race_id, horse_id, horse, course, race_date, off_time, rank=1, **scores):
    row = {
        "race_id": race_id,
        "horse_id": horse_id,
        "horse": horse,
        "course": course,
        "race_date": race_date,
        "off_time": off_time,
        "rank": rank,
    }
    row.update(scores)
    return row


def _selection(mod, races, source="RP_LOCAL_JSON", classification="RESULT_SOURCE_RP_LOCAL_PRIMARY", source_hash="h1"):
    from src.velo.learning.result_source_selector import ResultSourceSelection

    return ResultSourceSelection(
        date="2026-06-01",
        source=source,
        classification=classification,
        path_or_table="data/results/rp_results_2026_06_01.json",
        source_hash=source_hash,
        completeness={"exists": True},
        races=races,
    )


def _result_race(race_id, course, date, off, runners):
    return {"race_id": race_id, "course": course, "date": date, "off": off, "runners": runners}


def _runner(horse_id, position):
    return {"horse_id": horse_id, "position": str(position)}


# ---------------------------------------------------------------------------
# build_supabase_result_index
# ---------------------------------------------------------------------------


def test_build_supabase_result_index_groups_by_date_and_embeds_runners(mod):
    races = [{"race_id": "rac_1", "course": "Ascot", "date": "2026-05-20", "time": "13:35:00"}]
    runner_results = [{"race_id": "rac_1", "horse_id": "hrs_1", "position": "1"}]
    idx = mod.build_supabase_result_index(races, runner_results)
    assert "2026-05-20" in idx
    assert idx["2026-05-20"][0]["race_id"] == "rac_1"
    assert idx["2026-05-20"][0]["runners"] == runner_results


def test_build_supabase_result_index_ignores_rows_with_no_race_id_or_date(mod):
    races = [{"race_id": None, "course": "X", "date": "2026-05-20"}, {"race_id": "rac_2", "course": "X", "date": None}]
    idx = mod.build_supabase_result_index(races, [])
    assert idx == {}


# ---------------------------------------------------------------------------
# process_race_group: resolved race, resolved and unresolved horses
# ---------------------------------------------------------------------------


def test_process_race_group_produces_events_for_resolved_runners(mod):
    rows = [
        _snapshot_row("rp_LIN_20260601_2.07", "rp_LIN_h1", "Horse One", "Lingfield", "2026-06-01", "2.07", rank=1),
        _snapshot_row("rp_LIN_20260601_2.07", "rp_LIN_h2", "Horse Two", "Lingfield", "2026-06-01", "2.07", rank=2),
    ]
    result_race = _result_race(
        "rp_LIN_20260601_2.07",
        "Lingfield",
        "2026-06-01",
        "2.07",
        [_runner("rp_LIN_h1", 1), _runner("rp_LIN_h2", 2)],
    )
    selection = _selection(mod, [result_race])
    events, exclusions = mod.process_race_group("rp_LIN_20260601_2.07", rows, selection)
    assert len(events) == 2
    assert exclusions == []
    winner_event = next(e for e in events if e["prediction"]["runner_universe"][0]["horse_id"] == "rp_LIN_h1")
    assert winner_event["outcome"]["winner_horse_id"] == "rp_LIN_h1"


def test_process_race_group_excludes_unresolvable_race(mod):
    rows = [_snapshot_row("missing_race", "h1", "Horse One", "Ascot", "2026-06-01", "1.35")]
    selection = _selection(mod, [])  # no candidate races at all
    events, exclusions = mod.process_race_group("missing_race", rows, selection)
    assert events == []
    assert len(exclusions) == 1
    assert exclusions[0]["reason"] == "RACE_UNRESOLVED"


def test_process_race_group_excludes_unresolvable_horse_but_keeps_resolved_ones(mod):
    rows = [
        _snapshot_row("rp_LIN_20260601_2.07", "rp_LIN_h1", "Horse One", "Lingfield", "2026-06-01", "2.07"),
        _snapshot_row("rp_LIN_20260601_2.07", "unknown_id", "Nowhere Horse", "Lingfield", "2026-06-01", "2.07"),
    ]
    result_race = _result_race(
        "rp_LIN_20260601_2.07",
        "Lingfield",
        "2026-06-01",
        "2.07",
        [_runner("rp_LIN_h1", 1)],  # only one runner in the actual result
    )
    selection = _selection(mod, [result_race])
    events, exclusions = mod.process_race_group("rp_LIN_20260601_2.07", rows, selection)
    assert len(events) == 1
    assert len(exclusions) == 1
    assert exclusions[0]["reason"] == "HORSE_UNRESOLVED"
    assert exclusions[0]["horse_id"] == "unknown_id"


def test_process_race_group_flags_non_runners(mod):
    rows = [_snapshot_row("rp_LIN_20260601_2.07", "rp_LIN_h1", "Horse One", "Lingfield", "2026-06-01", "2.07")]
    result_race = _result_race(
        "rp_LIN_20260601_2.07",
        "Lingfield",
        "2026-06-01",
        "2.07",
        [{"horse_id": "rp_LIN_h1", "position": ""}],  # withdrawn / non-runner
    )
    selection = _selection(mod, [result_race])
    events, _ = mod.process_race_group("rp_LIN_20260601_2.07", rows, selection)
    assert events[0]["outcome"]["non_runners"] == ("rp_LIN_h1",)
    assert events[0]["outcome"]["runner_positions"]["rp_LIN_h1"] == "NR"


def test_process_race_group_marks_untimed_odds_when_capture_ts_missing(mod):
    """runner_prediction_snapshots never carries an odds-capture timestamp,
    so every event built from it must be EXCLUDED_UNTIMED_ODDS, never a
    fabricated SAFE_* classification."""
    rows = [_snapshot_row("rp_LIN_20260601_2.07", "rp_LIN_h1", "Horse One", "Lingfield", "2026-06-01", "2.07")]
    result_race = _result_race("rp_LIN_20260601_2.07", "Lingfield", "2026-06-01", "2.07", [_runner("rp_LIN_h1", 1)])
    selection = _selection(mod, [result_race])
    events, _ = mod.process_race_group("rp_LIN_20260601_2.07", rows, selection)
    assert events[0]["safety"]["time_safety"] == "EXCLUDED_UNTIMED_ODDS"
    assert events[0]["safety"]["learning_allowed"] is False


def test_process_race_group_marks_incomplete_result_source(mod):
    rows = [_snapshot_row("rp_LIN_20260601_2.07", "rp_LIN_h1", "Horse One", "Lingfield", "2026-06-01", "2.07")]
    result_race = _result_race("rp_LIN_20260601_2.07", "Lingfield", "2026-06-01", "2.07", [_runner("rp_LIN_h1", 1)])
    selection = _selection(mod, [result_race], classification="RESULT_SOURCE_PARTIAL")
    events, _ = mod.process_race_group("rp_LIN_20260601_2.07", rows, selection)
    assert events[0]["safety"]["time_safety"] == "EXCLUDED_INCOMPLETE_RESULT"


def test_process_race_group_event_id_is_repeatable(mod):
    """Rerunning the exact same race group must yield the same event_id --
    idempotent corpus rebuilds, not duplicate rows."""
    rows = [_snapshot_row("rp_LIN_20260601_2.07", "rp_LIN_h1", "Horse One", "Lingfield", "2026-06-01", "2.07")]
    result_race = _result_race("rp_LIN_20260601_2.07", "Lingfield", "2026-06-01", "2.07", [_runner("rp_LIN_h1", 1)])
    selection = _selection(mod, [result_race])
    events_a, _ = mod.process_race_group("rp_LIN_20260601_2.07", rows, selection)
    events_b, _ = mod.process_race_group("rp_LIN_20260601_2.07", rows, selection)
    assert events_a[0]["event_id"] == events_b[0]["event_id"]


# ---------------------------------------------------------------------------
# local result files are never mutated by the corpus builder
# ---------------------------------------------------------------------------


def test_select_result_source_never_writes_to_local_file(tmp_path):
    from src.velo.learning.result_source_selector import select_result_source

    path = tmp_path / "rp_results_2026_06_01.json"
    path.write_text(
        '{"date": "2026-06-01", "results": [{"race_id": "r1", "runners": [{"horse_id": "h1", "position": "1"}]}]}',
        encoding="utf-8",
    )
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    select_result_source("2026-06-01", results_dir=tmp_path)
    select_result_source("2026-06-01", results_dir=tmp_path)  # rerun
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before == after
