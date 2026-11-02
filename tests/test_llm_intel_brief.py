"""Deterministic EOD truth-report regression tests."""

from __future__ import annotations

import csv
import json

from scripts.ops import run_llm_intel_brief as brief


def _sigma_rows():
    return [
        {
            "race_id": "100",
            "course": "Test",
            "predicted": "Alpha",
            "actual_name": "Winner One",
            "outcome": "PLACE",
            "assigned_product": "EW_CANDIDATE",
            "ew_outcome": "EW_PLACE",
        },
        {
            "race_id": "101",
            "course": "Test",
            "predicted": "Beta",
            "actual_name": "Beta",
            "outcome": "WIN",
            "assigned_product": "WIN_ONLY",
            "ew_outcome": None,
        },
    ]


def _ledger_rows():
    return [
        {
            "date": "2026-11-01",
            "race_id": "100",
            "velo_top_pick": "Alpha",
            "velo_outcome": "PLACE",
            "velo_assigned_product": "EW_CANDIDATE",
            "velo_ew_outcome": "EW_PLACE",
            "norpr_outcome": "MISS",
            "nb_outcome": "NO_DATA",
            "champion_outcome": "NO_DATA",
            "mp_outcome": "NO_DATA",
            "nbc_outcome": "NO_DATA",
        },
        {
            "date": "2026-11-01",
            "race_id": "101",
            "velo_top_pick": "Beta",
            "velo_outcome": "WIN",
            "velo_assigned_product": "WIN_ONLY",
            "velo_ew_outcome": "",
            "norpr_outcome": "WIN",
            "nb_outcome": "NO_DATA",
            "champion_outcome": "NO_DATA",
            "mp_outcome": "NO_DATA",
            "nbc_outcome": "NO_DATA",
        },
    ]


def _sigma_payload():
    return {
        "sigma_status": "PASS",
        "expected_predictions": 2,
        "evaluated_count": 2,
        "ew_tracking": {"ew_candidate_n": 1},
        "rows": _sigma_rows(),
    }


def test_eod_integrity_passes_only_for_matching_named_race_universe():
    integrity = brief._build_eod_integrity(
        _sigma_payload(), _sigma_rows(), _ledger_rows()
    )

    assert integrity["status"] == "PASS"
    assert integrity["sigma_row_count"] == 2
    assert integrity["ledger_row_count"] == 2
    assert integrity["ew_candidate_count"] == 1
    assert integrity["ew_candidate_race_ids"] == ["100"]
    assert integrity["ew_outcomes"] == {"EW_PLACE": 1}


def test_eod_integrity_blocks_missing_pick_and_race_count_drift():
    ledger = _ledger_rows()[:-1]
    ledger[0]["velo_top_pick"] = "?"

    integrity = brief._build_eod_integrity(_sigma_payload(), _sigma_rows(), ledger)

    assert integrity["status"] == "BLOCKED"
    assert "SIGMA_LEDGER_RACE_UNIVERSE_MISMATCH" in integrity["blocking_reasons"]
    assert "VELO_TOP_PICK_IDENTITY_MISSING" in integrity["blocking_reasons"]


def test_gather_eod_reads_canonical_sigma_rows_and_exact_ew_set(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "sigma_results").mkdir(parents=True)
    (data / "council_runs").mkdir()
    (data / "mission_control").mkdir()
    (data / "sigma_results" / "sigma_results_2026_11_01.json").write_text(
        json.dumps(_sigma_payload()), encoding="utf-8"
    )
    fieldnames = list(_ledger_rows()[0])
    with (data / "model_comparison_ledger.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_ledger_rows())

    monkeypatch.setattr(brief, "ROOT", tmp_path)
    monkeypatch.setattr(brief, "OUT_DIR", data / "reports")

    payload = brief._gather_eod("2026-11-01", "2026_11_01")

    assert len(payload["artifact_sigma_results"]["results"]) == 2
    assert payload["artifact_integrity"]["status"] == "PASS"
    assert payload["artifact_integrity"]["ew_candidate_race_ids"] == ["100"]


def test_verified_eod_renderer_uses_deterministic_counts():
    integrity = brief._build_eod_integrity(
        _sigma_payload(), _sigma_rows(), _ledger_rows()
    )
    text = brief._render_verified_eod({"artifact_integrity": integrity})

    assert "Expected/evaluated/Sigma rows: 2/2/2" in text
    assert "EW candidates: 1" in text
    assert "Race IDs: 100" in text
    assert "WIN 1, PLACE 1, MISS 0" in text
