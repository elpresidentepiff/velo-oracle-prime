"""
Tests for scripts/ops/persist_canonical_model_scorecard.py — the idempotent
Supabase writer for canonical_model_scorecards.

Asserts: required columns enforced, only canonical_model_scorecards is ever
targeted (never velo_verdicts/sigma_audits/racing_horse_runs), and the
Little Lady Rock regression row survives payload construction unchanged.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import importlib.util
spec = importlib.util.spec_from_file_location(
    "persist_canonical_model_scorecard",
    ROOT / "scripts" / "ops" / "persist_canonical_model_scorecard.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _write_csv(tmp_path, rows, columns=None):
    columns = columns or mod.REQUIRED_COLUMNS
    path = tmp_path / "scorecard.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _base_row(**overrides):
    row = {c: "" for c in mod.REQUIRED_COLUMNS}
    row.update({
        "date": "2026-07-05", "race_id": "922118", "course": "Market Rasen",
        "off_time": "2.20", "model_name": "NEW_BUILD_LANE_A_MODEL", "lane_name": "lane_a",
        "source_path": "data/new_build/reports/two_lane_readiness_2026_07_05.json",
        "source_field": "race_day_scorecards[].lane_a_top3.prob", "sort_direction": "descending",
        "rank": "1", "horse": "Little Lady Rock", "horse_id": "7618350",
        "score": "0.217898", "sp_dec": "41.0", "result_position": "1",
        "win": "True", "frame": "True", "policy_decision": "NO_EDGE",
        "stake_authorised": "False", "dashboard_visible": "True",
        "learning_class": "MODEL_HIT_POLICY_BLOCKED", "tie_status": "N/A", "notes": "",
    })
    row.update(overrides)
    return row


def test_required_columns_enforced(tmp_path):
    bad_path = tmp_path / "bad.csv"
    with bad_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "race_id"])
        writer.writeheader()
        writer.writerow({"date": "2026-07-05", "race_id": "922118"})
    try:
        mod._load_csv(bad_path)
        assert False, "expected SystemExit for missing required columns"
    except SystemExit:
        pass


def test_little_lady_rock_regression_check_passes_on_correct_row(tmp_path):
    rows = [_base_row()]
    problems = mod._validate_little_lady_rock(rows, "2026-07-05")
    assert problems == []


def test_little_lady_rock_regression_check_fails_on_wrong_rank(tmp_path):
    rows = [_base_row(rank="2")]
    problems = mod._validate_little_lady_rock(rows, "2026-07-05")
    assert problems, "regression check must fail when Lane A rank is not 1"


def test_little_lady_rock_regression_check_fails_on_wrong_policy(tmp_path):
    rows = [_base_row(policy_decision="WIN_TRUST")]
    problems = mod._validate_little_lady_rock(rows, "2026-07-05")
    assert problems, "regression check must fail when policy_decision is not NO_EDGE"


def test_row_to_payload_preserves_little_lady_rock_facts():
    row = _base_row()
    payload = mod._row_to_payload(row, "2026-07-05", "deadbeef")
    assert payload["horse"] == "Little Lady Rock"
    assert payload["rank"] == 1
    assert payload["sp_dec"] == 41.0
    assert payload["policy_decision"] == "NO_EDGE"
    assert payload["stake_authorised"] is False
    assert payload["learning_class"] == "MODEL_HIT_POLICY_BLOCKED"


def test_sb_upsert_only_targets_canonical_model_scorecards_table():
    assert mod.TABLE_PATH == "/canonical_model_scorecards"
    # Guard against accidental table-name drift toward existing VELO tables.
    for forbidden in ("velo_verdicts", "sigma_audits", "racing_horse_runs", "runner_prediction_snapshots"):
        assert forbidden not in mod.TABLE_PATH


def test_dry_run_does_not_call_sb_upsert(monkeypatch, tmp_path):
    called = {"n": 0}

    def _fake_upsert(rows):
        called["n"] += 1
        return len(rows), None

    monkeypatch.setattr(mod, "_sb_upsert", _fake_upsert)
    monkeypatch.setattr(mod, "ROOT", tmp_path)  # redirect audit output away from real data/reports/
    csv_path = _write_csv(tmp_path, [_base_row()])
    monkeypatch.setattr(sys, "argv", [
        "persist_canonical_model_scorecard.py", "--date", "2026-07-05",
        "--csv", str(csv_path),
    ])
    mod.main()
    assert called["n"] == 0, "dry-run (no --execute) must never call _sb_upsert"
