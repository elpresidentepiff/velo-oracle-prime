"""Tests for scripts/audit/build_training_corpus_v2.py (LEARNING-LOOP-01A
Phase 4, corrected per PR #147 REQUEST CHANGES: P0-1 wiring, P1 metrics)."""

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


def _snapshot_row(
    race_id, run_id, horse_id, horse, course, race_date, off_time, rank=1, created_at="2026-06-01T10:00:00Z", **scores
):
    row = {
        "race_id": race_id,
        "run_id": run_id,
        "created_at": created_at,
        "horse_id": horse_id,
        "horse": horse,
        "course": course,
        "race_date": race_date,
        "off_time": off_time,
        "rank": rank,
    }
    row.update(scores)
    return row


def _selection(
    mod,
    races,
    source="RP_LOCAL_JSON",
    classification="RESULT_SOURCE_RP_LOCAL_PRIMARY",
    source_hash="h1",
    race_completeness=None,
):
    from src.velo.learning.result_source_selector import ResultSourceSelection

    return ResultSourceSelection(
        date="2026-06-01",
        source=source,
        classification=classification,
        path_or_table="data/results/rp_results_2026_06_01.json",
        source_hash=source_hash,
        completeness={"exists": True, "race_completeness_by_id": race_completeness or {}},
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
# process_race_group now takes a RunSelection, not raw pooled rows -- the
# Redcar-style contamination (multiple run_ids pooled into one race) must
# never reach this function; it is filtered out upstream by
# select_canonical_run before process_race_group ever sees the rows.
# ---------------------------------------------------------------------------


def test_process_race_group_produces_events_for_resolved_runners(mod):
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [
        _snapshot_row(
            "rp_LIN_20260601_2.07", "run_1", "rp_LIN_h1", "Horse One", "Lingfield", "2026-06-01", "2.07", rank=1
        ),
        _snapshot_row(
            "rp_LIN_20260601_2.07", "run_1", "rp_LIN_h2", "Horse Two", "Lingfield", "2026-06-01", "2.07", rank=2
        ),
    ]
    rs = select_canonical_run("rp_LIN_20260601_2.07", rows)
    assert rs.resolved is True

    result_race = _result_race(
        "rp_LIN_20260601_2.07",
        "Lingfield",
        "2026-06-01",
        "2.07",
        [_runner("rp_LIN_h1", 1), _runner("rp_LIN_h2", 2)],
    )
    selection = _selection(mod, [result_race], race_completeness={"rp_LIN_20260601_2.07": True})
    events, exclusions = mod.process_race_group("rp_LIN_20260601_2.07", rs, selection)
    assert len(events) == 2
    assert exclusions == []
    winner_event = next(e for e in events if e["prediction"]["subject_horse_id"] == "rp_LIN_h1")
    assert winner_event["outcome"]["winner_horse_id"] == "rp_LIN_h1"
    # field_size must equal the unique selected-run horse count
    assert winner_event["context"]["field_size"] == 2


def test_process_race_group_input_card_hash_is_a_real_hash(mod):
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [_snapshot_row("rp_LIN_20260601_2.07", "run_1", "rp_LIN_h1", "Horse One", "Lingfield", "2026-06-01", "2.07")]
    rs = select_canonical_run("rp_LIN_20260601_2.07", rows)
    result_race = _result_race("rp_LIN_20260601_2.07", "Lingfield", "2026-06-01", "2.07", [_runner("rp_LIN_h1", 1)])
    selection = _selection(mod, [result_race], race_completeness={"rp_LIN_20260601_2.07": True})
    events, _ = mod.process_race_group("rp_LIN_20260601_2.07", rs, selection)
    h = events[0]["prediction"]["input_card_hash"]
    assert h != "rp_LIN_20260601_2.07:rp_LIN_h1"
    assert len(h) == 64
    int(h, 16)


def test_process_race_group_excludes_unresolvable_race(mod):
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [_snapshot_row("missing_race", "run_1", "h1", "Horse One", "Ascot", "2026-06-01", "1.35")]
    rs = select_canonical_run("missing_race", rows)
    selection = _selection(mod, [])  # no candidate races at all
    events, exclusions = mod.process_race_group("missing_race", rs, selection)
    assert events == []
    assert len(exclusions) == 1
    assert exclusions[0]["reason"] == "RACE_UNRESOLVED"


def test_process_race_group_excludes_unresolvable_horse_but_keeps_resolved_ones(mod):
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [
        _snapshot_row(
            "rp_LIN_20260601_2.07", "run_1", "rp_LIN_h1", "Horse One", "Lingfield", "2026-06-01", "2.07", rank=1
        ),
        _snapshot_row(
            "rp_LIN_20260601_2.07", "run_1", "unknown_id", "Nowhere Horse", "Lingfield", "2026-06-01", "2.07", rank=2
        ),
    ]
    rs = select_canonical_run("rp_LIN_20260601_2.07", rows)
    result_race = _result_race("rp_LIN_20260601_2.07", "Lingfield", "2026-06-01", "2.07", [_runner("rp_LIN_h1", 1)])
    selection = _selection(mod, [result_race], race_completeness={"rp_LIN_20260601_2.07": True})
    events, exclusions = mod.process_race_group("rp_LIN_20260601_2.07", rs, selection)
    assert len(events) == 1
    assert len(exclusions) == 1
    assert exclusions[0]["reason"] == "HORSE_UNRESOLVED"
    assert exclusions[0]["horse_id"] == "unknown_id"


def test_process_race_group_incomplete_result_marks_excluded_incomplete(mod):
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [_snapshot_row("rp_LIN_20260601_2.07", "run_1", "rp_LIN_h1", "Horse One", "Lingfield", "2026-06-01", "2.07")]
    rs = select_canonical_run("rp_LIN_20260601_2.07", rows)
    result_race = _result_race("rp_LIN_20260601_2.07", "Lingfield", "2026-06-01", "2.07", [_runner("rp_LIN_h1", 1)])
    # race_completeness_by_id explicitly says this race is NOT fully accounted
    selection = _selection(mod, [result_race], race_completeness={"rp_LIN_20260601_2.07": False})
    events, _ = mod.process_race_group("rp_LIN_20260601_2.07", rs, selection)
    assert events[0]["safety"]["time_safety"] == "EXCLUDED_INCOMPLETE_RESULT"
    assert events[0]["safety"]["shadow_evaluation_allowed"] is False
    assert events[0]["safety"]["state_learning_allowed"] is False


def test_process_race_group_untimed_odds_when_result_complete(mod):
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [_snapshot_row("rp_LIN_20260601_2.07", "run_1", "rp_LIN_h1", "Horse One", "Lingfield", "2026-06-01", "2.07")]
    rs = select_canonical_run("rp_LIN_20260601_2.07", rows)
    result_race = _result_race("rp_LIN_20260601_2.07", "Lingfield", "2026-06-01", "2.07", [_runner("rp_LIN_h1", 1)])
    selection = _selection(mod, [result_race], race_completeness={"rp_LIN_20260601_2.07": True})
    events, _ = mod.process_race_group("rp_LIN_20260601_2.07", rs, selection)
    assert events[0]["safety"]["time_safety"] == "EXCLUDED_UNTIMED_ODDS"
    assert events[0]["safety"]["analysis_allowed"] is True
    assert events[0]["safety"]["shadow_evaluation_allowed"] is True
    assert events[0]["safety"]["promotion_eligible"] is False


def test_process_race_group_event_id_is_repeatable(mod):
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [_snapshot_row("rp_LIN_20260601_2.07", "run_1", "rp_LIN_h1", "Horse One", "Lingfield", "2026-06-01", "2.07")]
    rs = select_canonical_run("rp_LIN_20260601_2.07", rows)
    result_race = _result_race("rp_LIN_20260601_2.07", "Lingfield", "2026-06-01", "2.07", [_runner("rp_LIN_h1", 1)])
    selection = _selection(mod, [result_race], race_completeness={"rp_LIN_20260601_2.07": True})
    events_a, _ = mod.process_race_group("rp_LIN_20260601_2.07", rs, selection)
    events_b, _ = mod.process_race_group("rp_LIN_20260601_2.07", rs, selection)
    assert events_a[0]["event_id"] == events_b[0]["event_id"]


# ---------------------------------------------------------------------------
# regression: the exact Redcar/921866-style contamination must be caught
# before process_race_group ever runs
# ---------------------------------------------------------------------------


def test_contaminated_race_with_multiple_full_field_runs_selects_one(mod):
    from src.velo.learning.prediction_run_selector import select_canonical_run

    horses = [f"h{i}" for i in range(23)]
    rows = []
    for run_idx, ts in enumerate(
        [
            "2026-06-03T10:00:00Z",
            "2026-06-03T11:00:00Z",
            "2026-06-03T12:00:00Z",
            "2026-06-03T12:15:00Z",
        ]
    ):
        for rank, hid in enumerate(horses):
            rows.append(
                _snapshot_row(
                    "921866", f"run_{run_idx}", hid, hid, "Redcar", "2026-06-03", "15.15", rank=rank, created_at=ts
                )
            )
    assert len(rows) == 92  # 4 runs x 23 horses -- this is the pre-fix pooled contamination

    rs = select_canonical_run("921866", rows)
    assert rs.resolved is True
    assert len(rs.selected_rows) == 23
    assert len({r["horse_id"] for r in rs.selected_rows}) == 23

    result_race = _result_race(
        "921866", "Redcar", "2026-06-03", "15.15", [_runner(h, i + 1) for i, h in enumerate(horses)]
    )
    selection = _selection(mod, [result_race], race_completeness={"921866": True})
    events, exclusions = mod.process_race_group("921866", rs, selection)
    assert len(events) == 23
    assert exclusions == []
    rank_orders = {tuple(e["prediction"]["rank_order"]) for e in events}
    assert len(rank_orders) == 1  # every event in the race shares the same, non-duplicated rank order
    assert len(rank_orders.pop()) == 23


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
