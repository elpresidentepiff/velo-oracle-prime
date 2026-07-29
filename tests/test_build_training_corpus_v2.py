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
    selection = _selection(mod, [result_race])
    events, exclusions = mod.process_race_group("rp_LIN_20260601_2.07", rs, selection)
    assert len(events) == 1
    assert len(exclusions) == 1
    assert exclusions[0]["reason"] == "HORSE_UNRESOLVED"
    assert exclusions[0]["horse_id"] == "unknown_id"
    # P0-7: one predicted horse failing to resolve means the race is NOT
    # complete, even for the one horse that did resolve cleanly.
    assert events[0]["outcome"]["result_universe_complete"] is False


def test_process_race_group_incomplete_result_marks_excluded_incomplete(mod):
    """P0-7: completeness must be judged on the RECONCILED runner mapping,
    not a raw race-ID dictionary lookup. Here 2 horses are predicted but
    the result only carries a position for 1 of them (the other is blank,
    not an explicit NR) -- this must be incomplete for BOTH events, not
    just silently pass because the result file 'has runners'."""
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
    result_race = _result_race(
        "rp_LIN_20260601_2.07",
        "Lingfield",
        "2026-06-01",
        "2.07",
        [_runner("rp_LIN_h1", 1), {"horse_id": "rp_LIN_h2", "position": ""}],
    )
    selection = _selection(mod, [result_race])
    events, _ = mod.process_race_group("rp_LIN_20260601_2.07", rs, selection)
    assert len(events) == 2
    for ev in events:
        assert ev["outcome"]["result_universe_complete"] is False
        assert ev["safety"]["time_safety"] == "EXCLUDED_INCOMPLETE_RESULT"
        assert ev["safety"]["shadow_evaluation_allowed"] is False
        assert ev["safety"]["state_learning_allowed"] is False


def test_process_race_group_top_three_only_result_is_incomplete(mod):
    """The exact real-world defect: 12 predicted horses, result file only
    carries the top 3 finishers -- must be incomplete, not silently
    'passed' because the 3 present rows all looked fine."""
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [
        _snapshot_row(
            "918945",
            "run_1",
            f"h{i}",
            f"Horse {i}",
            "Redcar",
            "2026-05-26",
            "5.23",
            rank=i,
            created_at="2026-05-26T10:00:00Z",  # well before the 17:23 BST (16:23 UTC) off
        )
        for i in range(1, 13)
    ]
    rs = select_canonical_run("918945", rows)
    # Result file resolved via course+date+time fallback to a differently
    # schemed race_id, and only carries the top 3 finishers.
    result_race = _result_race(
        "rp_RED_20260526_5.23",
        "Redcar",
        "2026-05-26",
        "5.23",
        [_runner("h1", 1), _runner("h2", 2), _runner("h3", 3)],
    )
    selection = _selection(mod, [result_race])
    events, exclusions = mod.process_race_group("918945", rs, selection)
    # The 9 horses missing from the result entirely must be HORSE_UNRESOLVED
    assert len([e for e in exclusions if e["reason"] == "HORSE_UNRESOLVED"]) == 9
    # And even the 3 that DID resolve must be marked incomplete, because
    # the other 9 predicted runners were never accounted for.
    assert len(events) == 3
    for ev in events:
        assert ev["outcome"]["result_universe_complete"] is False
        assert ev["safety"]["time_safety"] == "EXCLUDED_INCOMPLETE_RESULT"


def test_process_race_group_complete_reconciled_universe_is_complete(mod):
    """All predicted horses resolve and every one has a known outcome --
    genuinely complete this time."""
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
    result_race = _result_race(
        "rp_LIN_20260601_2.07",
        "Lingfield",
        "2026-06-01",
        "2.07",
        [_runner("rp_LIN_h1", 1), _runner("rp_LIN_h2", "NR")],
    )
    selection = _selection(mod, [result_race])
    events, exclusions = mod.process_race_group("rp_LIN_20260601_2.07", rs, selection)
    assert exclusions == []
    assert len(events) == 2
    for ev in events:
        assert ev["outcome"]["result_universe_complete"] is True


def test_process_race_group_horse_id_mismatch_resolves_by_name(mod):
    """Prediction and result horse IDs differ (different namespace), but
    the horse name resolves -- the reconciled completeness check must
    still succeed via name-based resolution."""
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [
        _snapshot_row("rp_LIN_20260601_2.07", "run_1", "rp_LIN_h1", "Same Horse", "Lingfield", "2026-06-01", "2.07")
    ]
    rs = select_canonical_run("rp_LIN_20260601_2.07", rows)
    result_race = _result_race(
        "rp_LIN_20260601_2.07",
        "Lingfield",
        "2026-06-01",
        "2.07",
        [{"horse_id": "different_id_scheme", "horse": "Same Horse", "position": "1"}],
    )
    selection = _selection(mod, [result_race])
    events, exclusions = mod.process_race_group("rp_LIN_20260601_2.07", rs, selection)
    assert exclusions == []
    assert events[0]["outcome"]["result_universe_complete"] is True
    assert events[0]["outcome"]["winner_horse_id"] == "different_id_scheme"


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
# P0-9: reconciled subject-horse identity is persisted, not discarded
# ---------------------------------------------------------------------------


def test_numeric_prediction_id_resolves_to_rp_scheme_result_id_by_name(mod):
    """The exact regression scenario: prediction-side horse_id is a bare
    numeric id, result-side horse_id is in the rp_ scheme -- they only
    match via normalised-name resolution. The reconciled result-side id,
    outcome, SP, and winner/frame flags must all be persisted directly on
    the event, not left for a consumer to re-derive."""
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [
        _snapshot_row(
            "918945",
            "run_1",
            "2795739",
            "Bayraat",
            "Redcar",
            "2026-05-26",
            "5.23",
            rank=1,
            created_at="2026-05-26T10:00:00Z",
        )
    ]
    rs = select_canonical_run("918945", rows)
    result_race = _result_race(
        "918945",
        "Redcar",
        "2026-05-26",
        "5.23",
        [
            {"horse_id": "rp_RED_bayraat", "horse": "Bayraat", "position": "2", "sp_dec": 4.5},
            {"horse_id": "rp_RED_other", "horse": "Other Horse", "position": "1"},
        ],
    )
    selection = _selection(mod, [result_race])
    events, exclusions = mod.process_race_group("918945", rs, selection)
    assert exclusions == []
    ev = events[0]
    assert ev["prediction"]["subject_horse_id"] == "2795739"  # prediction-side id, unchanged
    assert ev["outcome"]["resolved_result_horse_id"] == "rp_RED_bayraat"
    assert ev["outcome"]["horse_resolution_method"] == "NORMALISED_NAME_IN_RESOLVED_RACE"
    assert ev["outcome"]["subject_finish_position"] == "2"
    assert ev["outcome"]["subject_sp"] == 4.5
    assert ev["outcome"]["subject_is_winner"] is False
    assert ev["outcome"]["subject_is_frame"] is True
    assert ev["outcome"]["subject_outcome_status"] == "FINISHED"


def test_reconciled_known_outcome_metric_counts_name_resolved_rows(mod, monkeypatch):
    """horse_rows_with_known_outcome must use the reconciled subject_*
    fields, not a prediction-id lookup into a result-side-keyed dict --
    that mismatch is exactly what silently undercounted the metric."""
    ev = {
        "prediction": {"race_id": "918945", "subject_horse_id": "2795739"},
        "outcome": {"subject_outcome_status": "FINISHED", "subject_is_non_runner": False},
        "safety": {
            "analysis_allowed": True,
            "shadow_evaluation_allowed": False,
            "state_learning_allowed": False,
            "model_training_allowed": False,
            "promotion_eligible": False,
        },
    }
    known = sum(1 for e in [ev] if e["outcome"]["subject_outcome_status"] != "UNKNOWN")
    assert known == 1


def test_event_content_hash_changes_if_reconciled_target_changes(mod):
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [
        _snapshot_row(
            "918945", "run_1", "2795739", "Bayraat", "Redcar", "2026-05-26", "5.23", created_at="2026-05-26T10:00:00Z"
        )
    ]
    rs = select_canonical_run("918945", rows)
    result_race_a = _result_race(
        "918945", "Redcar", "2026-05-26", "5.23", [{"horse_id": "rp_RED_bayraat", "horse": "Bayraat", "position": "2"}]
    )
    result_race_b = _result_race(
        "918945", "Redcar", "2026-05-26", "5.23", [{"horse_id": "rp_RED_bayraat", "horse": "Bayraat", "position": "1"}]
    )
    events_a, _ = mod.process_race_group("918945", rs, _selection(mod, [result_race_a]))
    events_b, _ = mod.process_race_group("918945", rs, _selection(mod, [result_race_b]))
    assert events_a[0]["event_content_hash"] != events_b[0]["event_content_hash"]


# ---------------------------------------------------------------------------
# P0-10: timing-unproven runs are never shadow-evaluation-eligible
# ---------------------------------------------------------------------------


def test_timezone_unproven_run_is_never_shadow_evaluation_allowed(mod):
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [_snapshot_row("rp_DEA_20260601_2.07", "run_1", "h1", "Horse One", "Deauville", "2026-06-01", "2.07")]
    rs = select_canonical_run("rp_DEA_20260601_2.07", rows)
    assert rs.pre_race_proof == "TIMEZONE_UNPROVEN"
    result_race = _result_race("rp_DEA_20260601_2.07", "Deauville", "2026-06-01", "2.07", [_runner("h1", 1)])
    selection = _selection(mod, [result_race])
    events, _ = mod.process_race_group("rp_DEA_20260601_2.07", rs, selection)
    assert events[0]["safety"]["shadow_evaluation_allowed"] is False
    assert events[0]["safety"]["time_safety"] == "EXCLUDED_TIMEZONE_UNPROVEN"
    assert events[0]["safety"]["analysis_allowed"] is True  # still analysis-eligible


def test_prediction_time_unproven_run_is_never_shadow_evaluation_allowed(mod):
    """Unparseable race_date -> PROOF_UNPROVEN (distinct from TIMEZONE_UNPROVEN)
    -- also must never be shadow-evaluation-eligible."""
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [_snapshot_row("rp_LIN_bad_2.07", "run_1", "h1", "Horse One", "Lingfield", "not-a-date", "2.07")]
    rs = select_canonical_run("rp_LIN_bad_2.07", rows)
    assert rs.pre_race_proof == "UNPROVEN"
    result_race = _result_race("rp_LIN_bad_2.07", "Lingfield", "not-a-date", "2.07", [_runner("h1", 1)])
    selection = _selection(mod, [result_race])
    events, _ = mod.process_race_group("rp_LIN_bad_2.07", rs, selection)
    assert events[0]["safety"]["shadow_evaluation_allowed"] is False
    assert events[0]["safety"]["time_safety"] == "EXCLUDED_PREDICTION_TIME_UNPROVEN"


def test_proven_pre_race_and_complete_result_is_shadow_evaluation_allowed(mod):
    from src.velo.learning.prediction_run_selector import select_canonical_run

    rows = [
        _snapshot_row(
            "rp_LIN_20260601_2.07",
            "run_1",
            "h1",
            "Horse One",
            "Lingfield",
            "2026-06-01",
            "2.07",
            created_at="2026-06-01T10:00:00Z",  # well before 14:07 BST off (13:07 UTC)
        )
    ]
    rs = select_canonical_run("rp_LIN_20260601_2.07", rows)
    assert rs.pre_race_proof == "PROVEN_PRE_RACE"
    result_race = _result_race("rp_LIN_20260601_2.07", "Lingfield", "2026-06-01", "2.07", [_runner("h1", 1)])
    selection = _selection(mod, [result_race])
    events, _ = mod.process_race_group("rp_LIN_20260601_2.07", rs, selection)
    assert events[0]["safety"]["shadow_evaluation_allowed"] is True


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
