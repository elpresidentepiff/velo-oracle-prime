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


def test_select_verdict_rows_single_candidate(mod):
    rows = [{"race_id": "222", "generated_at": "2026-07-12T09:00:00Z", "engine_version": "v1"}]
    selected, ambiguous = mod.select_verdict_rows(rows)

    assert ambiguous == {}
    assert selected["222"]["_duplicate_row_count"] == 0
    assert selected["222"]["_multiple_candidates"] is False
    assert selected["222"]["_tie_break_reason"] == "SINGLE_CANDIDATE"


def test_select_verdict_rows_unique_latest_generated_at_wins(mod):
    rows = [
        {"race_id": "111", "generated_at": "2026-07-12T09:00:00Z", "engine_version": "v1"},
        {"race_id": "111", "generated_at": "2026-07-12T09:05:00Z", "engine_version": "v1"},  # latest wins
    ]
    selected, ambiguous = mod.select_verdict_rows(rows)

    assert ambiguous == {}
    assert selected["111"]["generated_at"] == "2026-07-12T09:05:00Z"
    assert selected["111"]["_duplicate_row_count"] == 1
    assert selected["111"]["_multiple_candidates"] is True
    assert selected["111"]["_tie_break_reason"] == "LATEST_GENERATED_AT"


def test_select_verdict_rows_identical_duplicate_at_same_timestamp_collapses_safely(mod):
    # Same race_id, same generated_at, IDENTICAL content -- a duplicate
    # write, not a real ambiguity, so it is safe to collapse.
    rows = [
        {"race_id": "333", "generated_at": "2026-07-12T09:00:00Z", "engine_version": "v1", "git_commit_sha": "abc"},
        {"race_id": "333", "generated_at": "2026-07-12T09:00:00Z", "engine_version": "v1", "git_commit_sha": "abc"},
    ]
    selected, ambiguous = mod.select_verdict_rows(rows)

    assert ambiguous == {}
    assert selected["333"]["_duplicate_row_count"] == 1
    assert selected["333"]["_multiple_candidates"] is True
    assert selected["333"]["_tie_break_reason"] == "IDENTICAL_DUPLICATE_COLLAPSED"


def test_select_verdict_rows_conflicting_duplicate_at_same_timestamp_fails_closed(mod):
    # Same race_id, same generated_at, DIFFERENT content -- a genuine
    # ambiguity. Must not be resolved by input order; must fail closed.
    rows = [
        {"race_id": "444", "generated_at": "2026-07-12T09:00:00Z", "engine_version": "v1", "git_commit_sha": "aaa"},
        {"race_id": "444", "generated_at": "2026-07-12T09:00:00Z", "engine_version": "v2", "git_commit_sha": "bbb"},
    ]
    selected, ambiguous = mod.select_verdict_rows(rows)

    assert "444" not in selected
    assert ambiguous["444"]["reason"] == mod.AMBIGUOUS_PREDICTION_RUN
    assert ambiguous["444"]["candidate_count"] == 2
    assert len(ambiguous["444"]["distinct_content_hashes"]) == 2

    # order-independence: reversing input order must not change the outcome
    selected_rev, ambiguous_rev = mod.select_verdict_rows(list(reversed(rows)))
    assert "444" not in selected_rev
    assert ambiguous_rev["444"]["reason"] == mod.AMBIGUOUS_PREDICTION_RUN


# -- P0-12 follow-up: explicit course/date validation + clean-checkout ------


def test_dundalk_mapping_rejects_wrong_course(mod, tmp_path):
    manifest_path = _write_manifest(tmp_path, [_cap("some-other-course", "111", "2.00")])
    verdicts = [{"race_id": "rp_DUN_20260712_2.00"}]
    with pytest.raises(RuntimeError, match="course mismatch"):
        mod.build_dundalk_id_map(verdicts, manifest_path=manifest_path)


def test_dundalk_mapping_rejects_wrong_date(mod, tmp_path):
    manifest = {
        "captures": [
            {
                "source_url": "https://www.racingpost.com/results/1138/dundalk-aw/2026-07-11/111",
                "title": "Full Result 2.00 Dundalk (AW) (IRE) | 11 July 2026 | Racing Post",
            }
        ]
    }
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")
    verdicts = [{"race_id": "rp_DUN_20260712_2.00"}]
    with pytest.raises(RuntimeError, match="date mismatch"):
        mod.build_dundalk_id_map(verdicts, manifest_path=p)


def test_dundalk_mapping_reproduces_from_committed_evidence_on_clean_checkout(mod):
    """Regression for the residual-review finding: a clean checkout of this
    repo (no locally-generated captures) must still be able to derive the
    Dundalk bridge, because the manifest is a committed evidence artifact,
    not a local-only capture byproduct."""
    manifest_path = mod.DUNDALK_RESULTS_MANIFEST_PATH
    assert manifest_path.exists(), (
        f"{manifest_path} must be committed to the repo -- a clean checkout cannot "
        "reproduce the Dundalk mapping without it"
    )

    verdicts = [
        {"race_id": f"rp_DUN_20260712_{off}"}
        for off in ["2.00", "2.35", "3.10", "3.45", "4.20", "4.55", "5.30"]
    ]
    id_map, evidence, manifest_sha = mod.build_dundalk_id_map(verdicts, manifest_path=manifest_path)

    assert id_map == {
        "924518": "rp_DUN_20260712_2.00",
        "924519": "rp_DUN_20260712_2.35",
        "924520": "rp_DUN_20260712_3.10",
        "924521": "rp_DUN_20260712_3.45",
        "924522": "rp_DUN_20260712_4.20",
        "924523": "rp_DUN_20260712_4.55",
        "924524": "rp_DUN_20260712_5.30",
    }
    assert len(evidence) == 7
    for rec in evidence:
        assert rec["course"] == "dundalk-aw"
        assert rec["date"] == "2026-07-12"
        assert rec["source_manifest_sha256"] == manifest_sha
