"""Tests for scripts/audit/build_race_day_12_eod_truth.py (RACE-DAY-12-EOD-TRUTH-01,
corrected per PR #149 REQUEST CHANGES: P0-11 time-safety priority chain,
P0-12 evidence-derived Dundalk bridge, P0-14 immutable prediction-run identity)."""

import importlib.util
import json
import os

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(REPO_ROOT, "scripts", "audit", "build_race_day_12_eod_truth.py")


def _import_module():
    spec = importlib.util.spec_from_file_location("build_race_day_12_eod_truth", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _import_module()


# -- P0-11: time-safety priority chain --------------------------------------


def test_unresolved_identity_cannot_be_safe(mod):
    ts, leakage = mod.classify_time_safety(
        ambiguous=True,
        result_universe_complete=True,
        prediction_before_off=True,
        odds_timing_proven=True,
    )
    assert ts == mod.TIME_SAFETY_EXCLUDED_IDENTITY_AMBIGUOUS
    assert not ts.startswith("SAFE_")
    assert leakage == "UNKNOWN"


def test_incomplete_result_cannot_be_safe(mod):
    ts, leakage = mod.classify_time_safety(
        ambiguous=False,
        result_universe_complete=False,
        prediction_before_off=True,
        odds_timing_proven=True,
    )
    assert ts == mod.TIME_SAFETY_EXCLUDED_INCOMPLETE_RESULT
    assert not ts.startswith("SAFE_")
    assert leakage == "UNKNOWN"


def test_unproven_prediction_timing_cannot_be_safe(mod):
    ts, leakage = mod.classify_time_safety(
        ambiguous=False,
        result_universe_complete=True,
        prediction_before_off=None,
        odds_timing_proven=True,
    )
    assert ts == mod.TIME_SAFETY_EXCLUDED_PREDICTION_TIME_UNPROVEN
    assert not ts.startswith("SAFE_")
    assert leakage == "UNKNOWN"

    ts2, _ = mod.classify_time_safety(
        ambiguous=False,
        result_universe_complete=True,
        prediction_before_off=False,
        odds_timing_proven=True,
    )
    assert ts2 == mod.TIME_SAFETY_EXCLUDED_PREDICTION_TIME_UNPROVEN


def test_unproven_odds_capture_becomes_excluded_untimed_odds(mod):
    ts, leakage = mod.classify_time_safety(
        ambiguous=False,
        result_universe_complete=True,
        prediction_before_off=True,
        odds_timing_proven=False,
    )
    assert ts == mod.TIME_SAFETY_EXCLUDED_UNTIMED_ODDS
    assert not ts.startswith("SAFE_")
    # leakage is about result-derived contamination in frozen features, which is
    # independently proven by the pre-race generation timestamp regardless of
    # whether odds capture timing is separately proven.
    assert leakage == "CLEAN"


def test_all_conditions_proven_yields_safe_frozen_replay(mod):
    ts, leakage = mod.classify_time_safety(
        ambiguous=False,
        result_universe_complete=True,
        prediction_before_off=True,
        odds_timing_proven=True,
    )
    assert ts == mod.TIME_SAFETY_SAFE_FROZEN_REPLAY
    assert leakage == "CLEAN"


def test_current_generator_never_emits_safe_because_odds_timing_unproven(mod):
    assert mod.ODDS_TIMING_PROVEN is False


# -- P0-12: Dundalk mapping derived from evidence, not positional order ------


def _write_manifest(tmp_path, captures):
    manifest = {"captures": captures}
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")
    return p


def _cap(course_slug, race_id, off_time):
    return {
        "source_url": f"https://www.racingpost.com/results/1138/{course_slug}/2026-07-12/{race_id}",
        "title": f"Full Result {off_time} Dundalk (AW) (IRE) | 12 July 2026 | Racing Post",
    }


def test_dundalk_mapping_is_derived_from_source_evidence_not_position(mod, tmp_path):
    # Deliberately shuffled / non-chronological order on both sides -- a
    # positional zip would mis-map these; off-time matching must not.
    manifest_path = _write_manifest(
        tmp_path,
        [
            _cap("dundalk-aw", "999", "5.30"),
            _cap("dundalk-aw", "111", "2.00"),
            _cap("dundalk-aw", "555", "3.10"),
        ],
    )
    verdicts = [
        {"race_id": "rp_DUN_20260712_3.10"},
        {"race_id": "rp_DUN_20260712_5.30"},
        {"race_id": "rp_DUN_20260712_2.00"},
    ]
    id_map, evidence, manifest_sha = mod.build_dundalk_id_map(verdicts, manifest_path=manifest_path)
    assert id_map == {
        "999": "rp_DUN_20260712_5.30",
        "111": "rp_DUN_20260712_2.00",
        "555": "rp_DUN_20260712_3.10",
    }
    assert len(evidence) == 3
    for rec in evidence:
        assert rec["resolution_method"] == "COURSE_DATE_EXACT_OFFTIME_MATCH"
        assert rec["source_manifest_sha256"] == manifest_sha


def test_dundalk_mapping_blocks_on_duplicate_numeric_offtime(mod, tmp_path):
    manifest_path = _write_manifest(
        tmp_path,
        [
            _cap("dundalk-aw", "111", "2.00"),
            _cap("dundalk-aw", "222", "2.00"),  # duplicate off-time
        ],
    )
    verdicts = [
        {"race_id": "rp_DUN_20260712_2.00"},
    ]
    with pytest.raises(RuntimeError):
        mod.build_dundalk_id_map(verdicts, manifest_path=manifest_path)


def test_dundalk_mapping_blocks_on_missing_bijection(mod, tmp_path):
    manifest_path = _write_manifest(
        tmp_path,
        [
            _cap("dundalk-aw", "111", "2.00"),
            _cap("dundalk-aw", "222", "2.35"),
        ],
    )
    # Only one composite id -- not a clean 1:1 bijection.
    verdicts = [
        {"race_id": "rp_DUN_20260712_2.00"},
    ]
    with pytest.raises(RuntimeError):
        mod.build_dundalk_id_map(verdicts, manifest_path=manifest_path)


# -- P0-14: real immutable prediction-run identity ---------------------------


def test_corrected_verdict_row_changes_prediction_run_id(mod):
    row_a = {"race_id": "922149", "generated_at": "2026-07-12T09:43:45Z", "engine_version": "v1"}
    row_b = {"race_id": "922149", "generated_at": "2026-07-12T09:43:45Z", "engine_version": "v2"}  # corrected

    ident_a = mod.compute_prediction_run_identity(row_a)
    ident_b = mod.compute_prediction_run_identity(row_b)

    assert ident_a["prediction_run_id"] != ident_b["prediction_run_id"]
    assert ident_a["source_row_hash"] != ident_b["source_row_hash"]

    # deterministic: same content -> same identity every time
    ident_a2 = mod.compute_prediction_run_identity(dict(row_a))
    assert ident_a2["prediction_run_id"] == ident_a["prediction_run_id"]

    # a bare race identity is not a sufficient run identity
    assert ident_a["prediction_run_id"] != row_a["race_id"]


def test_select_verdict_rows_deterministic_tie_break_on_duplicates(mod):
    rows = [
        {"race_id": "111", "generated_at": "2026-07-12T09:00:00Z"},
        {"race_id": "111", "generated_at": "2026-07-12T09:05:00Z"},  # latest wins
        {"race_id": "222", "generated_at": "2026-07-12T09:00:00Z"},
    ]
    selected = mod.select_verdict_rows(rows)

    assert selected["111"]["generated_at"] == "2026-07-12T09:05:00Z"
    assert selected["111"]["_duplicate_row_count"] == 1
    assert selected["111"]["_multiple_candidates"] is True
    assert selected["111"]["_tie_break_reason"] == "LATEST_GENERATED_AT"

    assert selected["222"]["_duplicate_row_count"] == 0
    assert selected["222"]["_multiple_candidates"] is False
    assert selected["222"]["_tie_break_reason"] == "SINGLE_CANDIDATE"
