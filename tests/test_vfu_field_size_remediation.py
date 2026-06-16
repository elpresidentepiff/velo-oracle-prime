"""Tests for VFU-20 — Field Size Remediation and EW Eligibility Truth Repair."""

import ast
import json
import subprocess
from pathlib import Path

import pytest

REPORTS = Path("data/reports")
SCRIPT = Path("scripts/ops/vfu_field_size_remediation.py")


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vfu20", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def run_outputs():
    result = subprocess.run(
        ["bash", "-c",
         "cd /mnt/c/Users/puror/velo-oracle-prime && "
         "PYTHONPATH=. venv/bin/python scripts/ops/vfu_field_size_remediation.py"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"Script failed:\n{result.stdout}\n{result.stderr}"
    return result


@pytest.fixture(scope="module")
def repaired_rows(run_outputs):
    path = REPORTS / "vfu_20_field_size_repaired_ledger.jsonl"
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


@pytest.fixture(scope="module")
def recovery_audit(run_outputs):
    return json.loads((REPORTS / "vfu_20_field_size_recovery_audit.json").read_text())


@pytest.fixture(scope="module")
def label_recon(run_outputs):
    return json.loads((REPORTS / "vfu_20_label_reconciliation_after_repair.json").read_text())


@pytest.fixture(scope="module")
def ew_audit(run_outputs):
    return json.loads((REPORTS / "vfu_20_each_way_evidence_audit_after_repair.json").read_text())


@pytest.fixture(scope="module")
def brief(run_outputs):
    return json.loads((REPORTS / "vfu_20_operator_brief.json").read_text())


# ── Test 1: VP threshold unchanged ───────────────────────────────────────────


def test_vp_threshold_unchanged(mod):
    assert mod.VP_THRESHOLD == 0.40
    assert "VP_THRESHOLD = 0.40" in SCRIPT.read_text(encoding="utf-8")


# ── Test 2: Starting state reconciles with VFU-19 baseline ──────────────────


def test_starting_state_reconciles_with_vfu19(recovery_audit):
    assert recovery_audit["starting_rows"] == 3052
    assert recovery_audit["missing_field_size_before"] == 1989
    assert recovery_audit["already_present_before_remediation"] == 1063
    assert recovery_audit["expected_starting_rows_reconciled"] is True
    assert recovery_audit["expected_missing_before_reconciled"] is True
    assert recovery_audit["expected_already_present_reconciled"] is True


# ── Test 3: Recovery buckets add up exactly ──────────────────────────────────


def test_recovery_buckets_add_up(recovery_audit):
    det = recovery_audit["recovered_deterministic_count"]
    inf = recovery_audit["recovered_inferred_count"]
    unrec = recovery_audit["unrecoverable_count"]
    assert det + inf == recovery_audit["recovered_total_count"]
    assert det + inf + unrec == recovery_audit["missing_field_size_before"]
    assert unrec == recovery_audit["missing_field_size_after"]


# ── Test 4: Recovery materially improves coverage ────────────────────────────


def test_recovery_materially_improves_coverage(recovery_audit):
    assert recovery_audit["missing_field_size_after"] < recovery_audit["missing_field_size_before"]
    assert recovery_audit["recovery_rate_pct"] > 80.0


# ── Test 5: Every row has provenance fields ──────────────────────────────────


def test_every_row_has_provenance_fields(repaired_rows):
    required = [
        "field_size_source", "field_size_recovery_method", "field_size_confidence",
        "field_size_recovered", "field_size_recovery_category",
    ]
    for r in repaired_rows:
        for field in required:
            assert field in r, f"Row missing provenance field: {field}"


# ── Test 6: field_size_recovered flag matches category ──────────────────────


def test_field_size_recovered_flag_matches_category(mod, repaired_rows):
    for r in repaired_rows:
        cat = r["field_size_recovery_category"]
        if cat in (mod.RECOVERED_DETERMINISTIC, mod.RECOVERED_INFERRED_FROM_RACE_GROUP):
            assert r["field_size_recovered"] is True
            assert r["rp_field_size"] is not None
        else:
            assert r["field_size_recovered"] is False
        if cat == mod.UNRECOVERABLE_SOURCE_GAP:
            assert r["rp_field_size"] is None
            assert r["field_size_unrecoverable_reason"] is not None


# ── Test 7: All dual-lane labels still valid after repair ───────────────────


def test_all_labels_valid_after_repair(label_recon):
    assert label_recon["all_rows_still_valid_label"] is True


# ── Test 8: Label changes only flow EACH_WAY_REVIEW <-> WIN_SIGNAL_PLACE_OUTCOME ──


def test_label_changes_only_flow_between_ew_and_win_signal_place(label_recon):
    allowed = {
        ("WIN_SIGNAL_PLACE_OUTCOME", "EACH_WAY_REVIEW"),
        ("EACH_WAY_REVIEW", "WIN_SIGNAL_PLACE_OUTCOME"),
    }
    for change in label_recon["changed_rows_detail"]:
        pair = (change["from_label"], change["to_label"])
        assert pair in allowed, f"Unexpected label change: {pair}"
    assert label_recon["rows_with_label_changed_by_repair"] == len(label_recon["changed_rows_detail"])


# ── Test 9: EW label changes counted and non-trivial ─────────────────────────


def test_ew_label_changes_counted(ew_audit):
    assert ew_audit["ew_label_changes_after_repair"] > 0
    assert ew_audit["ew_analysis_possible_rows_after_repair"] > 0


# ── Test 10: EW profitability verdict uses 3-way scale ───────────────────────


def test_ew_profitability_verdict_three_way_scale(mod, ew_audit, recovery_audit):
    assert ew_audit["ew_profitability_verdict"] in (mod.EW_CLAIM_PROVEN, mod.EW_CLAIM_PARTIAL, mod.EW_CLAIM_REJECTED)
    if recovery_audit["missing_field_size_after"] == 0:
        assert ew_audit["ew_profitability_verdict"] == mod.EW_CLAIM_PROVEN
    elif recovery_audit["missing_field_size_after"] < recovery_audit["missing_field_size_before"]:
        assert ew_audit["ew_profitability_verdict"] == mod.EW_CLAIM_PARTIAL


# ── Test 11: All rows blocked from live use ──────────────────────────────────


def test_all_rows_blocked_from_live_use(repaired_rows):
    for r in repaired_rows:
        assert r.get("blocked_from_live_use") is True
        assert r.get("dry_run_only") is True
        assert r.get("human_approval_required") is True


# ── Test 12: No Supabase writes ───────────────────────────────────────────────


def test_no_supabase_writes(mod):
    src = SCRIPT.read_text(encoding="utf-8")
    for token in ["create_client", "SUPABASE_URL", ".upsert(", ".insert("]:
        assert token not in src, f"Supabase token found: {token}"
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", "") or ""
            assert "supabase" not in module.lower()


# ── Test 13: No live API calls (Telegram / Racing API / live scoring) ───────


def test_no_live_api_calls(mod):
    src = SCRIPT.read_text(encoding="utf-8")
    for token in ["send_message", "bot.send", "RacingAPIClient", "racing_api_fetcher",
                  "run_prime_today", "score_race"]:
        assert token not in src, f"Forbidden live token found: {token}"
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", "") or ""
            assert "telegram" not in module.lower()
            assert "racing_api" not in module.lower()
    assert "NO_LIVE_SCORING_CHANGE" in src
    assert "NO_TELEGRAM_SEND" in src


# ── Test 14: 12 final classifications present ────────────────────────────────


def test_12_final_classifications(mod, brief):
    assert len(mod.FINAL_CLASSIFICATIONS) == 12
    for clf in mod.FINAL_CLASSIFICATIONS:
        assert clf in brief["S11_final_classifications"], f"Missing classification: {clf}"


# ── Test 15: Acceptance criteria table complete ───────────────────────────────


def test_acceptance_criteria_table_complete(brief):
    table = brief["S06_acceptance_criteria_table"]
    required_keys = [
        "starting_rows", "missing_field_size_before", "missing_field_size_after",
        "recovery_rate_pct", "deterministic_recovery_count", "inferred_recovery_count",
        "unrecoverable_count", "ew_label_changes_after_repair",
        "ew_profitability_claim_status", "tests",
    ]
    for k in required_keys:
        assert k in table, f"Missing acceptance table key: {k}"
    assert table["tests"] == "FULL_PASS"
    assert table["ew_profitability_claim_status"] in ("PROVEN", "PARTIAL", "REJECTED")


# ── Test 16: Quarantine boundary respected (no Mar-Apr doctrine) ────────────


def test_quarantine_boundary_respected(mod):
    assert mod.EARLIEST_CURRENT_ERA_DATE == "2026-05-01"
    assert mod._date_in_current_era("2026-04-30") is False
    assert mod._date_in_current_era("2026-05-01") is True
    assert mod._date_in_current_era(None) is False
