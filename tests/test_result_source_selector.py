"""Tests for src/velo/learning/result_source_selector.py (LEARNING-LOOP-01A
Phase 2, corrected per PR #147 REQUEST CHANGES: P0-2, P1 strengthening)."""

import json

from src.velo.learning.result_source_selector import (
    CLASS_CONFLICT,
    CLASS_FALLBACK_VERIFIED,
    CLASS_MISSING,
    CLASS_PARTIAL,
    CLASS_RP_LOCAL_PRIMARY,
    CLASS_SUPABASE_LEGACY,
    SOURCE_RP_LOCAL_JSON,
    SOURCE_SUPABASE_CANONICAL,
    SOURCE_SUPABASE_LEGACY,
    SOURCE_SUPABASE_MIXED,
    SOURCE_UNAVAILABLE,
    select_result_source,
)


def _write_local_file(tmp_path, date, races):
    tag = date.replace("-", "_")
    path = tmp_path / f"rp_results_{tag}.json"
    path.write_text(json.dumps({"date": date, "results": races}), encoding="utf-8")
    return path


def _race(race_id, runners, non_runners=None, course="Ascot", date="2026-05-20", off="1.35"):
    return {
        "race_id": race_id,
        "course": course,
        "date": date,
        "off": off,
        "runners": runners,
        "non_runners": non_runners or [],
    }


def _runner(horse_id, position, horse_name=""):
    return {"horse_id": horse_id, "horse": horse_name, "position": str(position)}


# ---------------------------------------------------------------------------
# baseline: complete/missing/partial local file (no expected-universe check)
# ---------------------------------------------------------------------------


def test_complete_local_file_is_primary(tmp_path):
    _write_local_file(
        tmp_path,
        "2026-05-20",
        [_race("rp_ASC_20260520_1.35", [_runner("h1", 1), _runner("h2", 2), _runner("h3", 3), _runner("h4", 4)])],
    )
    sel = select_result_source("2026-05-20", results_dir=tmp_path)
    assert sel.source == SOURCE_RP_LOCAL_JSON
    assert sel.classification == CLASS_RP_LOCAL_PRIMARY
    assert sel.source_hash is not None
    assert len(sel.races) == 1


def test_missing_local_file_and_no_supabase_fallback_is_unavailable(tmp_path):
    sel = select_result_source("2026-05-20", results_dir=tmp_path, supabase_fetch=lambda d: [])
    assert sel.source == SOURCE_UNAVAILABLE
    assert sel.classification == CLASS_MISSING
    assert sel.races == []


def test_partial_local_file_with_no_fallback_is_classified_partial_not_hidden(tmp_path):
    _write_local_file(tmp_path, "2026-05-20", [{"race_id": "rp_ASC_20260520_1.35", "runners": []}])
    sel = select_result_source("2026-05-20", results_dir=tmp_path, supabase_fetch=lambda d: [])
    assert sel.source == SOURCE_RP_LOCAL_JSON
    assert sel.classification == CLASS_PARTIAL


# ---------------------------------------------------------------------------
# P0-2: presence of >=1 runner is NOT completeness proof
# ---------------------------------------------------------------------------


def test_winner_only_file_is_partial_not_primary_complete(tmp_path):
    """A file containing only winner/top-three data for a much larger
    predicted field must never be classified as primary-complete."""
    _write_local_file(
        tmp_path,
        "2026-05-20",
        [_race("rp_ASC_20260520_1.35", [_runner("h1", 1), _runner("h2", 2), _runner("h3", 3)])],
    )
    expected_runners = {"rp_ASC_20260520_1.35": {f"h{i}" for i in range(1, 13)}}  # predicted field of 12
    sel = select_result_source(
        "2026-05-20",
        results_dir=tmp_path,
        expected_runners_by_race=expected_runners,
        expected_race_ids={"rp_ASC_20260520_1.35"},
    )
    assert sel.classification != CLASS_RP_LOCAL_PRIMARY


def test_blank_position_is_not_automatically_non_runner(tmp_path):
    """A blank position must be UNKNOWN, not silently treated as NR --
    that would fabricate completeness for missing data."""
    _write_local_file(
        tmp_path,
        "2026-05-20",
        [_race("rp_ASC_20260520_1.35", [_runner("h1", 1), {"horse_id": "h2", "horse": "H2", "position": ""}])],
    )
    expected_runners = {"rp_ASC_20260520_1.35": {"h1", "h2"}}
    sel = select_result_source(
        "2026-05-20",
        results_dir=tmp_path,
        expected_runners_by_race=expected_runners,
        expected_race_ids={"rp_ASC_20260520_1.35"},
    )
    assert sel.classification != CLASS_RP_LOCAL_PRIMARY


def test_explicit_nr_marker_counts_toward_completeness(tmp_path):
    _write_local_file(
        tmp_path,
        "2026-05-20",
        [
            _race(
                "rp_ASC_20260520_1.35",
                [_runner("h1", 1), {"horse_id": "h2", "horse": "H2", "position": "NR"}],
            )
        ],
    )
    expected_runners = {"rp_ASC_20260520_1.35": {"h1", "h2"}}
    sel = select_result_source(
        "2026-05-20",
        results_dir=tmp_path,
        expected_runners_by_race=expected_runners,
        expected_race_ids={"rp_ASC_20260520_1.35"},
    )
    assert sel.classification == CLASS_RP_LOCAL_PRIMARY


def test_terminal_starter_outcome_counts_toward_completeness(tmp_path):
    _write_local_file(
        tmp_path,
        "2026-05-20",
        [_race("rp_ASC_20260520_1.35", [_runner("h1", 1), _runner("h2", "PU")])],
    )
    expected_runners = {"rp_ASC_20260520_1.35": {"h1", "h2"}}
    sel = select_result_source(
        "2026-05-20",
        results_dir=tmp_path,
        expected_runners_by_race=expected_runners,
        expected_race_ids={"rp_ASC_20260520_1.35"},
    )
    assert sel.classification == CLASS_RP_LOCAL_PRIMARY


def test_truncated_file_missing_expected_races_is_not_primary_complete(tmp_path):
    """A local file with 5 internally-populated races when 30 races were
    expected that day must not be labelled primary-complete."""
    races = [_race(f"rp_ASC_20260520_{i}.00", [_runner("h1", 1), _runner("h2", 2)]) for i in range(5)]
    _write_local_file(tmp_path, "2026-05-20", races)
    expected_race_ids = {f"rp_ASC_20260520_{i}.00" for i in range(30)}
    expected_runners = {f"rp_ASC_20260520_{i}.00": {"h1", "h2"} for i in range(30)}
    sel = select_result_source(
        "2026-05-20",
        results_dir=tmp_path,
        expected_race_ids=expected_race_ids,
        expected_runners_by_race=expected_runners,
    )
    assert sel.classification != CLASS_RP_LOCAL_PRIMARY
    assert len(sel.completeness["missing_races"]) == 25


def test_without_expected_universe_completeness_is_flagged_unproven(tmp_path):
    _write_local_file(tmp_path, "2026-05-20", [_race("rp_ASC_20260520_1.35", [_runner("h1", 1), _runner("h2", 2)])])
    sel = select_result_source("2026-05-20", results_dir=tmp_path)
    assert sel.completeness["expectation_provided"] is False


# ---------------------------------------------------------------------------
# Supabase fallback: mixed scheme, duplicate ids, deterministic hash
# ---------------------------------------------------------------------------


def test_missing_local_file_falls_back_to_supabase_legacy_scheme(tmp_path):
    supa_rows = [
        {
            "race_id": "rac_12345",
            "course": "Ascot",
            "date": "2026-05-20",
            "off": "1.35",
            "runners": [_runner("hrs_1", 1)],
        }
    ]
    sel = select_result_source("2026-05-20", results_dir=tmp_path, supabase_fetch=lambda d: supa_rows)
    assert sel.source == SOURCE_SUPABASE_LEGACY
    assert sel.classification == CLASS_SUPABASE_LEGACY
    assert sel.races == supa_rows


def test_mixed_scheme_supabase_rows_are_not_called_canonical(tmp_path):
    """A single rp_ row among mostly legacy rows must not make the whole
    source canonical."""
    supa_rows = [
        {
            "race_id": "rp_ASC_20260520_1.35",
            "course": "Ascot",
            "date": "2026-05-20",
            "off": "1.35",
            "runners": [_runner("h1", 1)],
        },
        {"race_id": "rac_99999", "course": "Ascot", "date": "2026-05-20", "off": "2.00", "runners": [_runner("h2", 1)]},
    ]
    sel = select_result_source("2026-05-20", results_dir=tmp_path, supabase_fetch=lambda d: supa_rows)
    assert sel.source == SOURCE_SUPABASE_MIXED


def test_duplicate_supabase_race_ids_detected_and_downgraded(tmp_path):
    supa_rows = [
        {
            "race_id": "rp_ASC_20260520_1.35",
            "course": "Ascot",
            "date": "2026-05-20",
            "off": "1.35",
            "runners": [_runner("h1", 1)],
        },
        {
            "race_id": "rp_ASC_20260520_1.35",
            "course": "Ascot",
            "date": "2026-05-20",
            "off": "1.35",
            "runners": [_runner("h2", 1)],
        },
    ]
    sel = select_result_source("2026-05-20", results_dir=tmp_path, supabase_fetch=lambda d: supa_rows)
    assert sel.completeness["duplicate_race_ids"] == ["rp_ASC_20260520_1.35"]
    assert sel.classification == CLASS_PARTIAL


def test_supabase_result_hash_is_deterministic_and_order_independent(tmp_path):
    rows_a = [
        {"race_id": "r1", "runners": [_runner("h1", 1)]},
        {"race_id": "r2", "runners": [_runner("h2", 1)]},
    ]
    rows_b = list(reversed(rows_a))
    sel_a = select_result_source("2026-05-20", results_dir=tmp_path, supabase_fetch=lambda d: rows_a)
    sel_b = select_result_source("2026-05-20", results_dir=tmp_path, supabase_fetch=lambda d: rows_b)
    assert sel_a.source_hash == sel_b.source_hash


def test_supabase_canonical_full_universe_gets_fallback_verified(tmp_path):
    supa_rows = [
        {
            "race_id": "rp_ASC_20260520_1.35",
            "course": "Ascot",
            "date": "2026-05-20",
            "off": "1.35",
            "runners": [_runner("h1", 1), _runner("h2", 2)],
        }
    ]
    expected_runners = {"rp_ASC_20260520_1.35": {"h1", "h2"}}
    sel = select_result_source(
        "2026-05-20",
        results_dir=tmp_path,
        supabase_fetch=lambda d: supa_rows,
        expected_race_ids={"rp_ASC_20260520_1.35"},
        expected_runners_by_race=expected_runners,
    )
    assert sel.source == SOURCE_SUPABASE_CANONICAL
    assert sel.classification == CLASS_FALLBACK_VERIFIED


# ---------------------------------------------------------------------------
# conflict detection preserved
# ---------------------------------------------------------------------------


def test_local_and_supabase_conflicting_winner_is_flagged_not_merged(tmp_path):
    _write_local_file(
        tmp_path,
        "2026-05-21",
        [
            _race("shared_id", [_runner("h1", 1), _runner("h2", 2)]),
            {"race_id": "other_id", "runners": []},
        ],
    )
    supa_rows = [
        {
            "race_id": "shared_id",
            "course": "Ascot",
            "date": "2026-05-21",
            "off": "1.35",
            "runners": [_runner("h2", 1), _runner("h1", 2)],
        }
    ]
    sel = select_result_source("2026-05-21", results_dir=tmp_path, supabase_fetch=lambda d: supa_rows)
    assert sel.classification == CLASS_CONFLICT
    assert sel.conflict_detail is not None
    assert sel.conflict_detail["conflicts"][0]["race_id"] == "shared_id"
    assert sel.races == []


def test_source_hash_changes_when_file_content_changes(tmp_path):
    _write_local_file(tmp_path, "2026-05-20", [_race("r1", [_runner("h1", 1)])])
    sel_a = select_result_source("2026-05-20", results_dir=tmp_path)
    _write_local_file(tmp_path, "2026-05-20", [_race("r1", [_runner("h1", 1), _runner("h2", 2)])])
    sel_b = select_result_source("2026-05-20", results_dir=tmp_path)
    assert sel_a.source_hash != sel_b.source_hash
