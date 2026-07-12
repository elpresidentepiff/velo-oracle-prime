"""Tests for src/velo/learning/prediction_run_selector.py (P0-1 correction)."""

from src.velo.learning.prediction_run_selector import (
    PROOF_POST_RACE,
    PROOF_PRE_RACE,
    PROOF_UNPROVEN,
    REASON_AMBIGUOUS_RUN_SELECTION,
    REASON_DUPLICATE_HORSE_IN_RUN,
    REASON_DUPLICATE_RANK_IN_RUN,
    REASON_NO_COMPLETE_RUN,
    select_canonical_run,
)


def _row(run_id, horse_id, rank, created_at, race_date="2026-06-03", off_time="3.15"):
    return {
        "run_id": run_id,
        "horse_id": horse_id,
        "rank": rank,
        "created_at": created_at,
        "race_date": race_date,
        "off_time": off_time,
    }


def test_reproduces_921866_style_contamination_and_selects_one_run():
    """8 independent full-field runs for one race_id -- must select exactly
    one, not pool all 184 rows into an invented 8x-duplicated field."""
    rows = []
    horses = [f"h{i}" for i in range(23)]
    run_timestamps = [
        "2026-06-03T10:00:00Z",
        "2026-06-03T10:05:00Z",
        "2026-06-03T11:00:00Z",
        "2026-06-03T11:05:00Z",
        "2026-06-03T12:00:00Z",
        "2026-06-03T12:05:00Z",
        "2026-06-03T12:10:00Z",
        "2026-06-03T12:15:00Z",  # latest -- should win (still before 15:15 off)
    ]
    for run_idx, ts in enumerate(run_timestamps):
        for rank, hid in enumerate(horses):
            rows.append(_row(f"run_{run_idx}", hid, rank, ts, off_time="15.15"))

    sel = select_canonical_run("921866", rows)
    assert sel.resolved is True
    assert sel.selected_run_id == "run_7"
    assert len(sel.selected_rows) == 23
    assert len({r["horse_id"] for r in sel.selected_rows}) == 23


def test_single_run_no_duplication_resolves_trivially():
    rows = [_row("run_a", "h1", 1, "2026-06-03T10:00:00Z"), _row("run_a", "h2", 2, "2026-06-03T10:00:00Z")]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is True
    assert sel.selected_run_id == "run_a"
    assert len(sel.selected_rows) == 2


def test_run_with_duplicate_horse_id_excluded_as_candidate():
    rows = [
        _row("bad_run", "h1", 1, "2026-06-03T10:00:00Z"),
        _row("bad_run", "h1", 2, "2026-06-03T10:00:00Z"),  # same horse twice
        _row("good_run", "h1", 1, "2026-06-03T11:00:00Z"),
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is True
    assert sel.selected_run_id == "good_run"
    assert sel.excluded_runs["bad_run"] == REASON_DUPLICATE_HORSE_IN_RUN


def test_run_with_duplicate_rank_excluded_as_candidate():
    rows = [
        _row("bad_run", "h1", 1, "2026-06-03T10:00:00Z"),
        _row("bad_run", "h2", 1, "2026-06-03T10:00:00Z"),  # tied rank, no tie policy
        _row("good_run", "h1", 1, "2026-06-03T11:00:00Z"),
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.selected_run_id == "good_run"
    assert sel.excluded_runs["bad_run"] == REASON_DUPLICATE_RANK_IN_RUN


def test_no_complete_run_at_all_is_unresolved():
    rows = [
        _row("bad_run_1", "h1", 1, "2026-06-03T10:00:00Z"),
        _row("bad_run_1", "h1", 2, "2026-06-03T10:00:00Z"),
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is False
    assert sel.reason == REASON_NO_COMPLETE_RUN


def test_prefers_latest_run_provably_before_off_time():
    rows = [
        _row("early", "h1", 1, "2026-06-03T10:00:00Z", off_time="15.15"),
        _row("later_still_pre_race", "h1", 1, "2026-06-03T14:00:00Z", off_time="15.15"),
        _row("post_race", "h1", 1, "2026-06-03T16:00:00Z", off_time="15.15"),  # after 15:15 off
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.selected_run_id == "later_still_pre_race"
    assert sel.pre_race_proof == PROOF_PRE_RACE


def test_all_runs_after_off_time_falls_back_to_latest_with_post_race_proof():
    rows = [
        _row("run_a", "h1", 1, "2026-06-03T16:00:00Z", off_time="15.15"),
        _row("run_b", "h1", 1, "2026-06-03T17:00:00Z", off_time="15.15"),
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is True
    assert sel.selected_run_id == "run_b"
    assert sel.pre_race_proof == PROOF_POST_RACE


def test_unparseable_timestamps_with_no_signal_are_ambiguous_not_guessed():
    """With zero timestamp signal on either candidate, there is no basis
    to prefer one run over the other -- must block, not silently pick
    insertion order."""
    rows = [
        _row("run_a", "h1", 1, None),
        _row("run_b", "h1", 1, None),
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is False
    assert sel.reason == REASON_AMBIGUOUS_RUN_SELECTION


def test_one_timestamped_run_among_untimed_ones_is_selected_deterministically():
    rows = [
        _row("run_a", "h1", 1, None),
        _row("run_b", "h1", 1, "2026-06-03T10:00:00Z"),
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is True
    assert sel.selected_run_id == "run_b"
    assert sel.pre_race_proof == PROOF_PRE_RACE


def test_tied_latest_timestamps_are_ambiguous_not_silently_picked():
    rows = [
        _row("run_a", "h1", 1, "2026-06-03T10:00:00Z"),
        _row("run_b", "h1", 1, "2026-06-03T10:00:00Z"),  # exact tie
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is False
    assert sel.reason == REASON_AMBIGUOUS_RUN_SELECTION
