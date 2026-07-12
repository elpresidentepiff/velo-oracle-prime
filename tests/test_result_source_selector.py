"""Tests for src/velo/learning/result_source_selector.py (LEARNING-LOOP-01A Phase 2)."""

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
    SOURCE_UNAVAILABLE,
    select_result_source,
)


def _write_local_file(tmp_path, date, races):
    tag = date.replace("-", "_")
    path = tmp_path / f"rp_results_{tag}.json"
    path.write_text(json.dumps({"date": date, "results": races}), encoding="utf-8")
    return path


def _race(race_id, runners):
    return {"race_id": race_id, "course": "Ascot", "date": "2026-05-20", "off": "1.35", "runners": runners}


def _runner(horse_id, position):
    return {"horse_id": horse_id, "position": str(position)}


def test_complete_local_file_is_primary(tmp_path):
    _write_local_file(tmp_path, "2026-05-20", [_race("rp_ASC_20260520_1.35", [_runner("h1", 1)])])
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
    # a race with no runners at all counts as incomplete
    _write_local_file(tmp_path, "2026-05-20", [{"race_id": "rp_ASC_20260520_1.35", "runners": []}])
    sel = select_result_source("2026-05-20", results_dir=tmp_path, supabase_fetch=lambda d: [])
    assert sel.source == SOURCE_RP_LOCAL_JSON
    assert sel.classification == CLASS_PARTIAL
    assert sel.completeness["races_with_runners"] == 0
    assert sel.completeness["races_total"] == 1


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


def test_missing_local_file_falls_back_to_supabase_canonical_when_rp_scheme_present(tmp_path):
    supa_rows = [
        {
            "race_id": "rp_ASC_20260520_1.35",
            "course": "Ascot",
            "date": "2026-05-20",
            "off": "1.35",
            "runners": [_runner("h1", 1)],
        }
    ]
    sel = select_result_source("2026-05-20", results_dir=tmp_path, supabase_fetch=lambda d: supa_rows)
    assert sel.source == SOURCE_SUPABASE_CANONICAL
    assert sel.classification == CLASS_FALLBACK_VERIFIED


def test_local_and_supabase_conflicting_winner_is_flagged_not_merged(tmp_path):
    # local file is deliberately partial (one race missing runners), which
    # is what triggers the fallback-comparison branch -- but the race we
    # care about ("shared_id") already has a determinable local winner.
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
    ]  # different winner
    sel = select_result_source("2026-05-21", results_dir=tmp_path, supabase_fetch=lambda d: supa_rows)
    assert sel.classification == CLASS_CONFLICT
    assert sel.conflict_detail is not None
    assert sel.conflict_detail["conflicts"][0]["race_id"] == "shared_id"
    assert sel.races == []  # never silently merged into an apparent result


def test_source_hash_changes_when_file_content_changes(tmp_path):
    _write_local_file(tmp_path, "2026-05-20", [_race("r1", [_runner("h1", 1)])])
    sel_a = select_result_source("2026-05-20", results_dir=tmp_path)
    _write_local_file(tmp_path, "2026-05-20", [_race("r1", [_runner("h1", 1), _runner("h2", 2)])])
    sel_b = select_result_source("2026-05-20", results_dir=tmp_path)
    assert sel_a.source_hash != sel_b.source_hash
