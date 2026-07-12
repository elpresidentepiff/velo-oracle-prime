"""Tests for scripts/audit/build_race_day_12_sigma_and_report.py (RACE-DAY-12-EOD-TRUTH-01,
corrected per PR #149 REQUEST CHANGES: P0-13 exclusions populated from the
canonical ledger, not left empty)."""

import importlib.util
import json
import os

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(REPO_ROOT, "scripts", "audit", "build_race_day_12_sigma_and_report.py")


def _import_module():
    spec = importlib.util.spec_from_file_location("build_race_day_12_sigma_and_report", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _five_unresolved_horse_rows():
    return [
        {
            "type": "HORSE",
            "race_id": "924518",
            "resolved_race_id": "rp_DUN_20260712_2.00",
            "horse_id": "rp_DUN_ipanema_queen",
            "horse_name": "Ipanema Queen",
            "resolution_method": "UNRESOLVED",
            "reason": "NO_CANDIDATE_FOUND",
            "race_completeness": "PARTIAL",
            "shadow_exclusion_reason": "EXCLUDED_IDENTITY_AMBIGUOUS",
        },
        {
            "type": "HORSE",
            "race_id": "924521",
            "resolved_race_id": "rp_DUN_20260712_3.45",
            "horse_id": "rp_DUN_desert_of_the_sea",
            "horse_name": "Desert Of The Sea",
            "resolution_method": "UNRESOLVED",
            "reason": "NO_CANDIDATE_FOUND",
            "race_completeness": "PARTIAL",
            "shadow_exclusion_reason": "EXCLUDED_IDENTITY_AMBIGUOUS",
        },
        {
            "type": "HORSE",
            "race_id": "924521",
            "resolved_race_id": "rp_DUN_20260712_3.45",
            "horse_id": "rp_DUN_monroe_dasher",
            "horse_name": "Monroe Dasher",
            "resolution_method": "UNRESOLVED",
            "reason": "NO_CANDIDATE_FOUND",
            "race_completeness": "PARTIAL",
            "shadow_exclusion_reason": "EXCLUDED_IDENTITY_AMBIGUOUS",
        },
        {
            "type": "HORSE",
            "race_id": "924521",
            "resolved_race_id": "rp_DUN_20260712_3.45",
            "horse_id": "rp_DUN_roman_harry",
            "horse_name": "Roman Harry",
            "resolution_method": "UNRESOLVED",
            "reason": "NO_CANDIDATE_FOUND",
            "race_completeness": "PARTIAL",
            "shadow_exclusion_reason": "EXCLUDED_IDENTITY_AMBIGUOUS",
        },
        {
            "type": "HORSE",
            "race_id": "924522",
            "resolved_race_id": "rp_DUN_20260712_4.20",
            "horse_id": "rp_DUN_grey_fable",
            "horse_name": "Grey Fable",
            "resolution_method": "UNRESOLVED",
            "reason": "NO_CANDIDATE_FOUND",
            "race_completeness": "PARTIAL",
            "shadow_exclusion_reason": "EXCLUDED_IDENTITY_AMBIGUOUS",
        },
    ]


def _five_partial_race_rows():
    race_ids = ["924518", "924519", "924521", "924522", "924524"]
    return [
        {
            "type": "RACE",
            "race_id": rid,
            "resolved_race_id": f"rp_DUN_20260712_x.xx",
            "horse_id": None,
            "horse_name": None,
            "resolution_method": "DUNDALK_COURSE_DATE_EXACT_OFFTIME_MATCH",
            "reason": "RESULT_RUNNERS_NOT_IN_PREDICTION:['x']",
            "race_completeness": "PARTIAL",
            "shadow_exclusion_reason": "EXCLUDED_INCOMPLETE_RESULT",
        }
        for rid in race_ids
    ]


@pytest.fixture()
def fixture_dir(tmp_path, monkeypatch):
    reports_dir = tmp_path / "data" / "reports"
    results_dir = tmp_path / "data" / "results"
    reports_dir.mkdir(parents=True)
    results_dir.mkdir(parents=True)

    partial_race_ids = {"924518", "924519", "924521", "924522", "924524"}
    per_race = []
    for i in range(28):
        rid = str(920000 + i)
        is_partial = i < 5
        if is_partial:
            rid = sorted(partial_race_ids)[i]
        per_race.append(
            {
                "race_id": rid,
                "course": "dundalk-aw" if is_partial else "sligo",
                "off": "2.00",
                "verdict_race_id": rid,
                "prediction_run_id": f"velo_verdicts:{rid}:x:y",
                "source_row_hash": "abc",
                "duplicate_row_count": 0,
                "multiple_candidates": False,
                "tie_break_reason": "SINGLE_CANDIDATE",
                "race_resolution_method": "DIRECT_ID_MATCH",
                "runners_predicted": 5,
                "runners_resulted": 5,
                "runners_resolved": 5 if not is_partial else 4,
                "runners_ambiguous_or_unresolved": 0 if not is_partial else 1,
                "result_universe_complete": not is_partial,
                "prediction_before_off": True,
                "winner_horse": "Some Horse",
                "winner_id": "1",
                "top_pick_pred_id": "1",
                "top_pick_resolved_id": "1",
                "top_pick_is_winner": not is_partial,
                "top_pick_is_frame": True,
            }
        )

    (reports_dir / "_race_day_12_per_race_summary.json").write_text(json.dumps(per_race), encoding="utf-8")

    exclusion_ledger = _five_partial_race_rows() + _five_unresolved_horse_rows()
    (reports_dir / "_race_day_12_exclusion_ledger.json").write_text(json.dumps(exclusion_ledger), encoding="utf-8")

    manifest = {
        "results_source_sha256": "deadbeef",
        "prediction_source": "velo_verdicts (Supabase)",
        "prediction_source_note": "test note",
        "dundalk_id_reconciliation": {"924518": "rp_DUN_20260712_2.00"},
        "dundalk_mapping_evidence": [{"resolution_method": "COURSE_DATE_EXACT_OFFTIME_MATCH"}],
        "dundalk_mapping_source_manifest_sha256": "cafef00d",
        "time_safety_distribution": {
            "EXCLUDED_UNTIMED_ODDS": 214,
            "EXCLUDED_INCOMPLETE_RESULT": 37,
            "EXCLUDED_IDENTITY_AMBIGUOUS": 5,
        },
        "allow_flag_law": {},
        "total_events": 256,
        "assertions": {
            "unresolved_horse_exclusion_count": 5,
            "partial_ambiguous_race_count": 5,
            "every_unresolved_horse_in_csv": True,
            "every_partial_race_has_reason": True,
            "no_excluded_race_shadow_eligible": True,
        },
    }
    (reports_dir / "learning_events_v2_2_2026_07_12_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    (results_dir / "rp_results_2026_07_12.json").write_text(json.dumps({"results": []}), encoding="utf-8")
    (reports_dir / "race_day_12_exclusions_2026_07_12.csv").write_text("type,race_id\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_sigma_exclusions_populated_from_canonical_ledger(fixture_dir):
    mod = _import_module()
    mod.main()

    sigma = json.loads((fixture_dir / "data" / "reports" / "sigma_2026_07_12_read_only.json").read_text())
    assert sigma["exclusions"] != []
    assert len(sigma["exclusions"]) == 10  # 5 race-level + 5 horse-level
    assert sum(1 for e in sigma["exclusions"] if e["type"] == "HORSE") == 5
    assert sum(1 for e in sigma["exclusions"] if e["type"] == "RACE") == 5


def test_all_five_partial_races_represented(fixture_dir):
    mod = _import_module()
    mod.main()

    sigma = json.loads((fixture_dir / "data" / "reports" / "sigma_2026_07_12_read_only.json").read_text())
    partial_race_ids = {e["race_id"] for e in sigma["exclusions"] if e["type"] == "RACE"}
    assert partial_race_ids == {"924518", "924519", "924521", "924522", "924524"}


def test_five_unresolved_horses_in_exclusions(fixture_dir):
    mod = _import_module()
    mod.main()

    sigma = json.loads((fixture_dir / "data" / "reports" / "sigma_2026_07_12_read_only.json").read_text())
    horse_ids = {e["horse_id"] for e in sigma["exclusions"] if e["type"] == "HORSE"}
    assert len(horse_ids) == 5


def test_state_learning_model_training_promotion_remain_zero_and_sealed(fixture_dir):
    mod = _import_module()
    mod.main()

    eod = json.loads((fixture_dir / "data" / "reports" / "race_day_12_eod_truth_2026_07_12.json").read_text())
    assert eod["classifications"]["NO_STATE_LEARNING"] is True
    assert eod["classifications"]["NO_MODEL_TRAINING"] is True
    assert eod["classifications"]["NO_MODEL_PROMOTION"] is True
    assert eod["learning_events_v2_2"]["consumption_status"] == "SEALED_NOT_CONSUMED"
