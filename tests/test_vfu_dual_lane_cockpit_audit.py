"""Tests for VFU-19 — Dual-Lane Cockpit Accounting Audit + Operator Brief."""

import ast
import json
import subprocess
from pathlib import Path

import pytest

REPORTS = Path("data/reports")
SCRIPT = Path("scripts/ops/vfu_dual_lane_cockpit_audit.py")


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vfu19", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def run_outputs():
    result = subprocess.run(
        ["bash", "-c",
         "cd /mnt/c/Users/puror/velo-oracle-prime && "
         "PYTHONPATH=. venv/bin/python scripts/ops/vfu_dual_lane_cockpit_audit.py"],
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, f"Script failed:\n{result.stdout}\n{result.stderr}"
    return result


@pytest.fixture(scope="module")
def ledger_rows(run_outputs):
    path = REPORTS / "vfu_19_dual_lane_accounting_ledger.jsonl"
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


@pytest.fixture(scope="module")
def label_recon(run_outputs):
    return json.loads((REPORTS / "vfu_19_dual_lane_cockpit_audit.json").read_text())["label_reconciliation"]


@pytest.fixture(scope="module")
def vp_recon(run_outputs):
    return json.loads((REPORTS / "vfu_19_vp_fire_reconciliation.json").read_text())


@pytest.fixture(scope="module")
def ew_audit(run_outputs):
    return json.loads((REPORTS / "vfu_19_each_way_evidence_audit.json").read_text())


@pytest.fixture(scope="module")
def brief(run_outputs):
    return json.loads((REPORTS / "vfu_19_operator_brief.json").read_text())


# ── Test 1: VP threshold unchanged ───────────────────────────────────────────


def test_vp_threshold_unchanged(mod):
    assert mod.VP_THRESHOLD == 0.40
    assert "VP_THRESHOLD = 0.40" in SCRIPT.read_text(encoding="utf-8")


# ── Test 2: Row count matches VFU-18 base (3,052) ────────────────────────────


def test_row_count_matches_vfu18_base(ledger_rows):
    assert len(ledger_rows) == 3052


# ── Test 3: Label reconciliation matches VFU-18 exactly ─────────────────────


def test_label_reconciliation_matches_vfu18(label_recon):
    assert label_recon["label_reconciliation_matches_vfu18"] is True
    assert label_recon["label_counts_vfu19"] == label_recon["label_counts_vfu18"]


# ── Test 4: All 10 dual-lane labels present ──────────────────────────────────


def test_all_10_labels_present(mod, ledger_rows):
    found = {r.get("dual_lane_label") for r in ledger_rows}
    for lbl in mod.ALL_DUAL_LANE_LABELS:
        assert lbl in found, f"Missing dual-lane label: {lbl}"


# ── Test 5: VP fire reconciliation totals ────────────────────────────────────


def test_vp_fire_reconciliation_totals(vp_recon):
    assert vp_recon["total_vp_fires"] == 447
    assert vp_recon["label_win_lane_confirmed"] == 186
    assert vp_recon["win_hit_rate_pct"] == pytest.approx(41.6, abs=0.5)


# ── Test 6: VP fire discrepancy is explained, not hidden ────────────────────


def test_vp_fire_discrepancy_explained(vp_recon):
    """If raw outcome=WIN count differs from WIN_LANE_CONFIRMED count, the gap
    must be explained via the documented specialist-override mechanism, not silently dropped."""
    gap = vp_recon["raw_outcome_win_among_vp_fires"] - vp_recon["label_win_lane_confirmed"]
    assert vp_recon["specialist_override_count"] == gap
    if gap > 0:
        assert "PLACE_SPECIALIST" in vp_recon["discrepancy_note"]
    else:
        assert "No discrepancy" in vp_recon["discrepancy_note"]


# ── Test 7: Each-way evidence audit headline numbers ─────────────────────────


def test_ew_evidence_audit_headline(ew_audit):
    assert ew_audit["rows_missing_field_size_total"] == 1989
    assert ew_audit["ew_blocked_field_size"] == 809
    assert ew_audit["ew_profitability_verdict"] == "PARTIAL_EW_SIGNAL_NOT_PROFIT_PROOF"


# ── Test 8: EW audit label distribution sums to total rows ──────────────────


def test_ew_audit_label_distribution_sums_correctly(mod, ew_audit):
    dist = ew_audit["ew_audit_label_distribution"]
    assert set(dist.keys()) == set(mod.ALL_EW_AUDIT_LABELS)
    assert sum(dist.values()) == ew_audit["total_rows"]


# ── Test 9: Every row carries full accounting + safety fields ───────────────


def test_every_row_has_accounting_and_safety_fields(ledger_rows):
    required = [
        "ledger_id", "place_cutoff_used", "place_cutoff_confidence",
        "each_way_conclusion", "ew_audit_label",
    ]
    for r in ledger_rows:
        for field in required:
            assert field in r, f"Row missing accounting field: {field}"
        assert r.get("blocked_from_live_use") is True
        assert r.get("dry_run_only") is True
        assert r.get("human_approval_required") is True


# ── Test 10: ledger_id is unique per row ─────────────────────────────────────


def test_ledger_id_unique(ledger_rows):
    ids = [r["ledger_id"] for r in ledger_rows]
    assert len(ids) == len(set(ids))


# ── Test 11: 14 final classifications present in brief ──────────────────────


def test_14_final_classifications(mod, brief):
    assert len(mod.FINAL_CLASSIFICATIONS) == 14
    for clf in mod.FINAL_CLASSIFICATIONS:
        assert clf in brief["S12_final_classifications"], f"Missing classification: {clf}"


# ── Test 12: Operator brief has the required sections incl. VFU-20 options ──


def test_operator_brief_sections(brief):
    for section in [
        "S01_mission_scope", "S02_source_confirmation", "S03_label_reconciliation",
        "S04_vp_fire_reconciliation", "S05_dual_lane_distribution",
        "S06_each_way_evidence_headline", "S07_ew_audit_label_distribution",
        "S08_specialist_watchlist_cross_reference", "S09_downgrade_upgrade_cross_reference",
        "S10_safety_confirmations", "S11_vfu20_options", "S12_final_classifications",
    ]:
        assert section in brief, f"Missing brief section: {section}"

    opts = {o["id"] for o in brief["S11_vfu20_options"]["options"]}
    assert opts == {
        "FIELD_SIZE_REMEDIATION_FIRST", "PICK_SP_BACKFILL",
        "PROSPECTIVE_DUAL_LANE_VALIDATION", "PLACE_SPECIALIST_WATCHLIST_VALIDATION",
        "HOLD_EW_DEVELOPMENT",
    }
    assert brief["stop_banner"] == "STOP after VFU-19 — operator review required before VFU-20."


# ── Test 13: No Supabase writes ───────────────────────────────────────────────


def test_no_supabase_writes(mod):
    src = SCRIPT.read_text(encoding="utf-8")
    for token in ["create_client", "SUPABASE_URL", ".upsert(", ".insert("]:
        assert token not in src, f"Supabase token found: {token}"
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", "") or ""
            assert "supabase" not in module.lower()


# ── Test 14: No live scoring, Telegram, or Racing API calls ──────────────────


def test_no_live_scoring_telegram_or_racing_api(mod):
    src = SCRIPT.read_text(encoding="utf-8")
    for token in ["run_prime_today", "score_race", "telegram.Bot(",
                  "bot.send_message", "send_telegram", "RacingAPIClient",
                  "racing_api_fetcher"]:
        assert token not in src, f"Forbidden live token found: {token}"
    assert "NO_LIVE_SCORING_CHANGE" in src
    assert "NO_TELEGRAM_SEND" in src
    assert "NO_RACING_API_RESTORATION" in src


# ── Test 15: All output files present ────────────────────────────────────────


def test_all_output_files_present(run_outputs):
    for fname in [
        "vfu_19_dual_lane_accounting_ledger.jsonl",
        "vfu_19_vp_fire_reconciliation.json",
        "vfu_19_each_way_evidence_audit.json",
        "vfu_19_dual_lane_cockpit_audit.json",
        "vfu_19_dual_lane_cockpit_audit.md",
        "vfu_19_operator_brief.json",
        "vfu_19_operator_brief.md",
    ]:
        assert (REPORTS / fname).exists(), f"Output file missing: {fname}"


# ── Test 16: STOP enforced — no VFU-20 artifacts created by this script ─────


def test_stop_enforced_no_vfu20_artifacts(mod):
    src = SCRIPT.read_text(encoding="utf-8")
    assert "vfu_20" not in src.lower()
