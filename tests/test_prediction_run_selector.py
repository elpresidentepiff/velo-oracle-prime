"""Tests for src/velo/learning/prediction_run_selector.py.

P0-1 correction: group by (race_id, run_id), never race_id alone.
P0-8 correction: race off-times are LOCAL venue time (GB=Europe/London,
IRE=Europe/Dublin), not UTC -- BST/IST add a real one-hour offset in
summer. A post-race snapshot must never become the canonical run.
"""

from src.velo.learning.prediction_run_selector import (
    PROOF_PRE_RACE,
    PROOF_TIMEZONE_UNPROVEN,
    PROOF_UNPROVEN,
    REASON_AMBIGUOUS_RUN_SELECTION,
    REASON_DUPLICATE_HORSE_IN_RUN,
    REASON_DUPLICATE_RANK_IN_RUN,
    REASON_NO_COMPLETE_RUN,
    REASON_NO_PRE_RACE_RUN,
    course_timezone,
    select_canonical_run,
)


def _row(run_id, horse_id, rank, created_at, race_date="2026-06-03", off_time="3.15", course="Ayr"):
    return {
        "run_id": run_id,
        "horse_id": horse_id,
        "rank": rank,
        "created_at": created_at,
        "race_date": race_date,
        "off_time": off_time,
        "course": course,
    }


# ---------------------------------------------------------------------------
# course timezone mapping
# ---------------------------------------------------------------------------


def test_gb_course_maps_to_europe_london():
    assert course_timezone("Ayr") == "Europe/London"
    assert course_timezone("Redcar") == "Europe/London"


def test_ire_course_maps_to_europe_dublin():
    assert course_timezone("Sligo") == "Europe/Dublin"
    assert course_timezone("Dundalk") == "Europe/Dublin"


def test_unmapped_course_is_timezone_unproven():
    assert course_timezone("Deauville") is None
    assert course_timezone("Sha Tin") is None
    assert course_timezone(None) is None


# ---------------------------------------------------------------------------
# P0-1: run pooling / contamination
# ---------------------------------------------------------------------------


def test_reproduces_921866_style_contamination_and_selects_one_run():
    """8 independent full-field runs for one race_id -- must select exactly
    one, not pool all 184 rows into an invented 8x-duplicated field."""
    rows = []
    horses = [f"h{i}" for i in range(23)]
    run_timestamps = [
        "2026-06-03T09:00:00Z",
        "2026-06-03T09:05:00Z",
        "2026-06-03T10:00:00Z",
        "2026-06-03T10:05:00Z",
        "2026-06-03T11:00:00Z",
        "2026-06-03T11:05:00Z",
        "2026-06-03T11:10:00Z",
        "2026-06-03T11:15:00Z",  # latest -- should win (still before 15:15 BST == 14:15 UTC off)
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
        _row("bad_run", "h1", 1, "2026-06-03T09:00:00Z"),
        _row("bad_run", "h1", 2, "2026-06-03T09:00:00Z"),  # same horse twice
        _row("good_run", "h1", 1, "2026-06-03T10:00:00Z"),
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is True
    assert sel.selected_run_id == "good_run"
    assert sel.excluded_runs["bad_run"] == REASON_DUPLICATE_HORSE_IN_RUN


def test_run_with_duplicate_rank_excluded_as_candidate():
    rows = [
        _row("bad_run", "h1", 1, "2026-06-03T09:00:00Z"),
        _row("bad_run", "h2", 1, "2026-06-03T09:00:00Z"),  # tied rank, no tie policy
        _row("good_run", "h1", 1, "2026-06-03T10:00:00Z"),
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


def test_unparseable_timestamps_with_no_signal_are_ambiguous_not_guessed():
    rows = [
        _row("run_a", "h1", 1, None),
        _row("run_b", "h1", 1, None),
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is False
    assert sel.reason == REASON_AMBIGUOUS_RUN_SELECTION


def test_one_timestamped_run_among_untimed_ones_is_selected_deterministically():
    rows = [
        _row("run_a", "h1", 1, None, off_time="15.15"),
        _row("run_b", "h1", 1, "2026-06-03T09:00:00Z", off_time="15.15"),  # 09:00 UTC, well before 14:15 UTC off
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is True
    assert sel.selected_run_id == "run_b"
    assert sel.pre_race_proof == PROOF_PRE_RACE


def test_tied_latest_timestamps_are_ambiguous_not_silently_picked():
    rows = [
        _row("run_a", "h1", 1, "2026-06-03T09:00:00Z"),
        _row("run_b", "h1", 1, "2026-06-03T09:00:00Z"),  # exact tie
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is False
    assert sel.reason == REASON_AMBIGUOUS_RUN_SELECTION


# ---------------------------------------------------------------------------
# P0-8: timezone correctness and hard-block on post-race-only runs
# ---------------------------------------------------------------------------


def test_uk_winter_gmt_no_offset():
    """January: GMT, no offset -- 15:15 local == 15:15 UTC."""
    rows = [
        _row("pre", "h1", 1, "2026-01-15T15:00:00Z", race_date="2026-01-15", off_time="15.15", course="Ayr"),
        _row("post", "h1", 1, "2026-01-15T15:30:00Z", race_date="2026-01-15", off_time="15.15", course="Ayr"),
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is True
    assert sel.selected_run_id == "pre"
    assert sel.pre_race_proof == PROOF_PRE_RACE


def test_uk_summer_bst_one_hour_offset():
    """June: BST, UTC+1 -- 15:15 local == 14:15 UTC. A run at 14:45 UTC is
    AFTER the real off-time even though it's before the naively-assumed
    15:15 UTC off -- this is exactly the bug: it must NOT be selected as
    pre-race."""
    rows = [
        _row("truly_pre_race", "h1", 1, "2026-06-03T13:00:00Z", race_date="2026-06-03", off_time="15.15", course="Ayr"),
        _row(
            "false_pre_race_naive_utc",
            "h1",
            1,
            "2026-06-03T14:45:00Z",
            race_date="2026-06-03",
            off_time="15.15",
            course="Ayr",
        ),
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is True
    assert sel.selected_run_id == "truly_pre_race"
    assert sel.pre_race_proof == PROOF_PRE_RACE


def test_irish_summer_time_one_hour_offset():
    """Irish Standard Time also runs UTC+1 in summer -- Sligo 15:15 local
    on 2026-06-03 == 14:15 UTC, same as the UK BST case."""
    rows = [
        _row("pre", "h1", 1, "2026-06-03T13:00:00Z", race_date="2026-06-03", off_time="15.15", course="Sligo"),
        _row("post", "h1", 1, "2026-06-03T14:45:00Z", race_date="2026-06-03", off_time="15.15", course="Sligo"),
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is True
    assert sel.selected_run_id == "pre"
    assert sel.pre_race_proof == PROOF_PRE_RACE


def test_snapshot_after_real_utc_off_but_before_naive_utc_off_is_excluded():
    """The exact defect scenario in isolation: only ONE candidate run,
    timestamped 14:45 UTC for a 15:15 BST (14:15 UTC) race -- after the
    real off, before the wrongly-assumed-UTC off. Must be excluded as
    NO_PRE_RACE_RUN, not selected."""
    rows = [_row("only_run", "h1", 1, "2026-06-03T14:45:00Z", race_date="2026-06-03", off_time="15.15", course="Ayr")]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is False
    assert sel.reason == REASON_NO_PRE_RACE_RUN


def test_all_runs_post_race_is_hard_blocked_not_selected():
    """A post-race prediction snapshot must never become the canonical
    prediction run -- when every timed candidate is after off-time, the
    race is excluded, full stop. No latest-post-race fallback."""
    rows = [
        _row("run_a", "h1", 1, "2026-06-03T16:00:00Z", race_date="2026-06-03", off_time="15.15", course="Ayr"),
        _row("run_b", "h1", 1, "2026-06-03T17:00:00Z", race_date="2026-06-03", off_time="15.15", course="Ayr"),
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is False
    assert sel.reason == REASON_NO_PRE_RACE_RUN


def test_mixed_pre_and_post_race_runs_selects_only_pre_race_one():
    rows = [
        _row("pre", "h1", 1, "2026-06-03T12:00:00Z", race_date="2026-06-03", off_time="15.15", course="Ayr"),
        _row("post", "h1", 1, "2026-06-03T16:00:00Z", race_date="2026-06-03", off_time="15.15", course="Ayr"),
    ]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is True
    assert sel.selected_run_id == "pre"
    assert sel.pre_race_proof == PROOF_PRE_RACE


def test_unmapped_course_timezone_is_retained_for_analysis_only():
    """An international course with no jurisdiction mapping cannot prove
    pre/post-race timing either way -- the run is still selected (for
    analysis only) but never labelled PROVEN_PRE_RACE, even though its
    timestamp would look 'pre-race' under a naive UTC assumption."""
    rows = [_row("run_a", "h1", 1, "2026-06-03T10:00:00Z", off_time="15.15", course="Deauville")]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is True
    assert sel.selected_run_id == "run_a"
    assert sel.pre_race_proof == PROOF_TIMEZONE_UNPROVEN


def test_unmapped_course_never_hard_blocks_even_if_naively_looks_post_race():
    """Same unmapped-course case, but the single run's timestamp would
    look 'post-race' under a naive same-day-UTC comparison. Since timing
    cannot be proven at all for this jurisdiction, it must NOT be
    hard-excluded as NO_PRE_RACE_RUN -- that hard block only applies when
    timezone IS known and every candidate is proven after off."""
    rows = [_row("run_a", "h1", 1, "2026-06-03T20:00:00Z", off_time="15.15", course="Deauville")]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is True
    assert sel.pre_race_proof == PROOF_TIMEZONE_UNPROVEN


def test_unparseable_date_is_unproven_not_hard_blocked():
    rows = [_row("run_a", "h1", 1, "2026-06-03T10:00:00Z", race_date="not-a-date", off_time="15.15", course="Ayr")]
    sel = select_canonical_run("race_x", rows)
    assert sel.resolved is True
    assert sel.pre_race_proof == PROOF_UNPROVEN
