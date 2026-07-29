"""
Tests for ENSEMBLE-TRUTH-01 — race_id-joined ensemble shadow comparison
(scripts/audit/run_ensemble_shadow_comparison.py).

Covers: reordered race arrays, one missing race, duplicate race IDs, tied
probabilities, one changed selection, idempotent monitor ledger on repeated
execution for the same date, and frozen-output byte-separation across
sequential profile scoring runs.
"""

import csv
import hashlib
import importlib.util
import os

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(REPO_ROOT, "scripts", "audit", "run_ensemble_shadow_comparison.py")


def _import_module():
    spec = importlib.util.spec_from_file_location("run_ensemble_shadow_comparison", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _import_module()


def _race(rid, course, off_time, horse, vp, tier="A", exec_allowed=False):
    return {
        "race_id": rid,
        "course": course,
        "off_time": off_time,
        "tier": tier,
        "top": {
            "horse": horse,
            "velo_prime_prob": vp,
            "candidate_execution_allowed": exec_allowed,
        },
    }


# ---------------------------------------------------------------------------
# Race_id join replaces positional zip() comparison
# ---------------------------------------------------------------------------


def test_reordered_race_arrays_still_join_correctly(mod):
    new_data = [
        _race("1", "Ascot", "1.35", "A Horse", 0.30),
        _race("2", "Chester", "2.10", "B Horse", 0.25),
    ]
    # Legacy list is reversed -- a positional zip() would compare race "1"
    # against race "2"'s pick and vice versa.
    leg_data = [
        _race("2", "Chester", "2.10", "B Horse", 0.24),
        _race("1", "Ascot", "1.35", "A Horse", 0.29),
    ]
    join = mod.join_by_race_id(new_data, leg_data)
    diffs = mod.compute_race_diffs(join)
    summary = mod.summarize_diffs(diffs)
    # Both races actually agree on horse -- a correct join must show 100%
    # agreement despite the reordering.
    assert summary["agreement_count"] == 2
    assert summary["disagreement_count"] == 0


def test_one_missing_race_hard_fails(mod):
    new_data = [
        _race("1", "Ascot", "1.35", "A Horse", 0.30),
        _race("2", "Chester", "2.10", "B Horse", 0.25),
    ]
    leg_data = [
        _race("1", "Ascot", "1.35", "A Horse", 0.29),
        # race "2" missing entirely from the legacy profile's output
    ]
    with pytest.raises(mod.EnsembleComparisonError, match="RACE_UNIVERSE_MISMATCH"):
        mod.join_by_race_id(new_data, leg_data)


def test_duplicate_race_ids_hard_fail(mod):
    new_data = [
        _race("1", "Ascot", "1.35", "A Horse", 0.30),
        _race("1", "Ascot", "1.35", "A Horse Again", 0.28),
    ]
    leg_data = [_race("1", "Ascot", "1.35", "A Horse", 0.29)]
    with pytest.raises(mod.EnsembleComparisonError, match="DUPLICATE_RACE_IDS"):
        mod.join_by_race_id(new_data, leg_data)


def test_missing_top_selection_hard_fails(mod):
    new_data = [{"race_id": "1", "course": "Ascot", "off_time": "1.35", "tier": "A", "top": None}]
    leg_data = [_race("1", "Ascot", "1.35", "A Horse", 0.29)]
    with pytest.raises(mod.EnsembleComparisonError, match="MISSING_TOP_SELECTION"):
        mod.join_by_race_id(new_data, leg_data)


# ---------------------------------------------------------------------------
# Tied probabilities and single changed selection
# ---------------------------------------------------------------------------


def test_tied_probabilities_no_division_error(mod):
    new_data = [_race("1", "Ascot", "1.35", "Same Horse", 0.25)]
    leg_data = [_race("1", "Ascot", "1.35", "Same Horse", 0.25)]
    join = mod.join_by_race_id(new_data, leg_data)
    diffs = mod.compute_race_diffs(join)
    summary = mod.summarize_diffs(diffs)
    assert diffs[0]["vp_delta"] == 0.0
    assert diffs[0]["agree"] is True
    assert summary["max_abs_vp_delta"] == 0.0


def test_one_changed_selection_detected(mod):
    new_data = [
        _race("1", "Ascot", "1.35", "Winner A", 0.30),
        _race("2", "Chester", "2.10", "Same Pick", 0.20),
    ]
    leg_data = [
        _race("1", "Ascot", "1.35", "Winner B", 0.29),
        _race("2", "Chester", "2.10", "Same Pick", 0.19),
    ]
    join = mod.join_by_race_id(new_data, leg_data)
    diffs = mod.compute_race_diffs(join)
    summary = mod.summarize_diffs(diffs)
    assert summary["agreement_count"] == 1
    assert summary["disagreement_count"] == 1
    disagreements = [d for d in diffs if not d["agree"]]
    assert disagreements[0]["race_id"] == "1"
    assert disagreements[0]["live_horse"] == "Winner A"
    assert disagreements[0]["legacy_horse"] == "Winner B"


def test_tier_and_execution_migration_matrices(mod):
    new_data = [_race("1", "Ascot", "1.35", "H", 0.30, tier="A", exec_allowed=True)]
    leg_data = [_race("1", "Ascot", "1.35", "H", 0.29, tier="B", exec_allowed=False)]
    join = mod.join_by_race_id(new_data, leg_data)
    diffs = mod.compute_race_diffs(join)
    summary = mod.summarize_diffs(diffs)
    assert diffs[0]["tier_migrated"] is True
    assert diffs[0]["exec_migrated"] is True
    assert summary["tier_migration_matrix"] == {"A->B": 1}
    assert summary["execution_migration_matrix"] == {"True->False": 1}


# ---------------------------------------------------------------------------
# Idempotent monitor ledger
# ---------------------------------------------------------------------------


def test_upsert_monitor_row_replaces_not_appends(mod, tmp_path):
    csv_path = tmp_path / "monitor.csv"
    row_v1 = dict.fromkeys(mod._MONITOR_HEADER, "")
    row_v1.update({"date": "2026-05-09", "live_profile": "LIVE", "shadow_profile": "SHADOW", "races": "10"})
    mod.upsert_monitor_row(csv_path, row_v1)

    row_v2 = dict(row_v1)
    row_v2["races"] = "20"  # simulate rerun with different content
    mod.upsert_monitor_row(csv_path, row_v2)

    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1, "rerunning the same (date, live_profile, shadow_profile) key must replace, not append"
    assert rows[0]["races"] == "20"


def test_upsert_monitor_row_distinct_keys_both_kept(mod, tmp_path):
    csv_path = tmp_path / "monitor.csv"
    base = dict.fromkeys(mod._MONITOR_HEADER, "")
    row_a = dict(base)
    row_a.update({"date": "2026-05-09", "live_profile": "LIVE", "shadow_profile": "SHADOW"})
    row_b = dict(base)
    row_b.update({"date": "2026-05-10", "live_profile": "LIVE", "shadow_profile": "SHADOW"})
    mod.upsert_monitor_row(csv_path, row_a)
    mod.upsert_monitor_row(csv_path, row_b)

    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Frozen output stays byte-separated across sequential profile scoring runs
# ---------------------------------------------------------------------------


def test_sha256_of_file_matches_manual_hash(mod, tmp_path):
    p = tmp_path / "sample.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    expected = hashlib.sha256(p.read_bytes()).hexdigest()
    assert mod._sha256_of_file(p) == expected


def test_assert_untouched_detects_mutation(mod, tmp_path):
    p = tmp_path / "frozen.json"
    p.write_text('{"profile": "live"}', encoding="utf-8")
    original_hash = mod._sha256_of_file(p)

    mod._assert_untouched(p, original_hash, label="live")  # no-op, unchanged

    p.write_text('{"profile": "legacy-overwrote-this"}', encoding="utf-8")
    with pytest.raises(mod.EnsembleComparisonError, match="FROZEN_OUTPUT_MUTATED"):
        mod._assert_untouched(p, original_hash, label="live")


def test_run_comparison_frozen_live_output_survives_legacy_scoring(mod, tmp_path, monkeypatch):
    """End-to-end (mocked subprocess): the live profile's saved copy must be
    byte-identical before and after the legacy profile's scoring run."""
    calls = {"n": 0}

    def fake_score(date_str, profile, out_path):
        calls["n"] += 1
        vp = 0.30 if profile == mod.LIVE_PROFILE else 0.29
        data = [_race("1", "Ascot", "1.35", "Same Horse", vp)]
        out_path.write_text(__import__("json").dumps(data))
        return data

    monkeypatch.setattr(mod, "_score_with_profile", fake_score)
    result = mod.run_comparison("2026-05-09", tmp_dir=tmp_path)

    assert calls["n"] == 2
    assert result["diff_summary"]["agreement_count"] == 1
    assert result["join"]["live_count"] == 1
    assert result["join"]["legacy_count"] == 1
    assert result["join"]["shared_count"] == 1


def test_run_comparison_raises_on_frozen_mutation(mod, tmp_path, monkeypatch):
    """If a bug reintroduces cross-profile mutation of the frozen output,
    run_comparison must hard-fail rather than silently report wrong stats."""

    def fake_score_that_corrupts(date_str, profile, out_path):
        data = [_race("1", "Ascot", "1.35", "Same Horse", 0.30)]
        out_path.write_text(__import__("json").dumps(data))
        if profile == mod.SHADOW_PROFILE:
            # Simulate the legacy run corrupting the live profile's saved file.
            live_path = tmp_path / "_shadow_cmp_new_2026_05_09.json"
            live_path.write_text('{"corrupted": true}')
        return data

    monkeypatch.setattr(mod, "_score_with_profile", fake_score_that_corrupts)
    with pytest.raises(mod.EnsembleComparisonError, match="FROZEN_OUTPUT_MUTATED"):
        mod.run_comparison("2026-05-09", tmp_dir=tmp_path)
