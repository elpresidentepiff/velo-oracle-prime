"""Tests for VFU-18 — Place Data Enrichment + Dual-Lane Cockpit."""

import ast
import json
import subprocess
from pathlib import Path

import pytest

REPORTS = Path("data/reports")
SCRIPT = Path("scripts/ops/vfu_place_data_enrichment.py")


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vfu18", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def run_outputs():
    """Run script once and make all output files available."""
    result = subprocess.run(
        ["bash", "-c",
         "cd /mnt/c/Users/puror/velo-oracle-prime && "
         "PYTHONPATH=. venv/bin/python scripts/ops/vfu_place_data_enrichment.py"],
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, f"Script failed:\n{result.stdout}\n{result.stderr}"
    return result


@pytest.fixture(scope="module")
def dual_lane_rows(run_outputs):
    """All enriched rows from dual_lane_records.jsonl."""
    path = REPORTS / "vfu_18_dual_lane_records.jsonl"
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


@pytest.fixture(scope="module")
def summary(run_outputs):
    return json.loads((REPORTS / "vfu_18_place_data_enrichment_summary.json").read_text())


@pytest.fixture(scope="module")
def cockpit(run_outputs):
    return json.loads((REPORTS / "vfu_18_dual_lane_cockpit.json").read_text())


# ── Test 1: Place cutoff logic ────────────────────────────────────────────────


def test_place_cutoff_logic(mod):
    """Place cutoff function returns correct values across all field-size bands."""
    assert mod.place_cutoff(4) == (1, mod.PLACE_CUTOFF_WIN_ONLY)
    assert mod.place_cutoff(5) == (2, mod.PLACE_CUTOFF_FIELD_SIZE)
    assert mod.place_cutoff(7) == (2, mod.PLACE_CUTOFF_FIELD_SIZE)
    assert mod.place_cutoff(8) == (3, mod.PLACE_CUTOFF_FIELD_SIZE)
    assert mod.place_cutoff(15) == (3, mod.PLACE_CUTOFF_FIELD_SIZE)
    assert mod.place_cutoff(16) == (4, mod.PLACE_CUTOFF_FIELD_SIZE)
    assert mod.place_cutoff(None) == (None, mod.PLACE_CUTOFF_UNKNOWN)


# ── Test 2: Place terms estimate ──────────────────────────────────────────────


def test_place_terms_estimate(mod):
    """Place terms string maps correctly to field-size bands."""
    assert mod.place_terms_estimate(None) == "UNKNOWN"
    assert mod.place_terms_estimate(4) == "WIN_ONLY"
    assert mod.place_terms_estimate(5) == "1/4_ODDS_2_PLACES"
    assert mod.place_terms_estimate(7) == "1/4_ODDS_2_PLACES"
    assert mod.place_terms_estimate(8) == "1/5_ODDS_3_PLACES"
    assert mod.place_terms_estimate(15) == "1/5_ODDS_3_PLACES"
    assert mod.place_terms_estimate(16) == "1/4_ODDS_4_PLACES"


# ── Test 3: Each-way conclusion logic ────────────────────────────────────────


def test_each_way_conclusion_logic(mod):
    """Each-way conclusion logic returns correct labels."""
    # No field size → blocked
    assert mod.each_way_conclusion(mod.WIN, None) == mod.EW_CONCLUSION_BLOCKED
    assert mod.each_way_conclusion(mod.PLACE, None) == mod.EW_CONCLUSION_BLOCKED

    # WIN_ONLY (field <= 4)
    assert mod.each_way_conclusion(mod.WIN, 1) == mod.EW_WIN_ONLY_PAID
    assert mod.each_way_conclusion(mod.MISS, 1) == mod.EW_BOTH_MISS

    # Place available (field >= 5)
    assert mod.each_way_conclusion(mod.WIN, 2) == mod.EW_PROFITABLE
    assert mod.each_way_conclusion(mod.PLACE, 2) == mod.EW_PLACE_PAID_WIN_MISS
    assert mod.each_way_conclusion(mod.MISS, 3) == mod.EW_BOTH_MISS
    assert mod.each_way_conclusion(mod.FRAME, 3) == mod.EW_BOTH_MISS


# ── Test 4: Dual-lane label covers all 10 classes ────────────────────────────


def test_dual_lane_labels_complete(dual_lane_rows):
    """All 10 dual-lane labels must appear at least once in the enriched rows."""
    from scripts.ops.vfu_place_data_enrichment import ALL_DUAL_LANE_LABELS
    found = {r.get("dual_lane_label") for r in dual_lane_rows}
    for lbl in ALL_DUAL_LANE_LABELS:
        assert lbl in found, f"Dual-lane label not found in output: {lbl}"


# ── Test 5: WIN_LANE_CONFIRMED only for VP ≥ 0.40 + WIN ─────────────────────


def test_win_lane_confirmed_conditions(dual_lane_rows):
    """WIN_LANE_CONFIRMED rows must all have VP >= 0.40 and outcome WIN."""
    from scripts.ops.vfu_place_data_enrichment import WIN_LANE_CONFIRMED, VP_THRESHOLD
    confirmed = [r for r in dual_lane_rows if r.get("dual_lane_label") == WIN_LANE_CONFIRMED]
    assert len(confirmed) > 0, "No WIN_LANE_CONFIRMED rows"
    for r in confirmed:
        assert (r.get("vp") or 0) >= VP_THRESHOLD, (
            f"WIN_LANE_CONFIRMED row {r.get('ledger_id')} has VP={r.get('vp')} < {VP_THRESHOLD}"
        )
        assert r.get("outcome_class") == "WIN", (
            f"WIN_LANE_CONFIRMED row has outcome_class={r.get('outcome_class')}"
        )


# ── Test 6: EACH_WAY_REVIEW requires field_size >= 5 ─────────────────────────


def test_each_way_review_requires_field_size(dual_lane_rows):
    """EACH_WAY_REVIEW rows must all have VP >= 0.40, PLACE outcome, and field_size >= 5."""
    from scripts.ops.vfu_place_data_enrichment import EACH_WAY_REVIEW, VP_THRESHOLD
    ew_rows = [r for r in dual_lane_rows if r.get("dual_lane_label") == EACH_WAY_REVIEW]
    assert len(ew_rows) > 0, "No EACH_WAY_REVIEW rows"
    for r in ew_rows:
        assert (r.get("vp") or 0) >= VP_THRESHOLD, (
            f"EACH_WAY_REVIEW row {r.get('ledger_id')} has VP={r.get('vp')}"
        )
        assert r.get("outcome_class") == "PLACE", (
            f"EACH_WAY_REVIEW row has outcome_class={r.get('outcome_class')}"
        )
        assert (r.get("rp_field_size") or 0) >= 5, (
            f"EACH_WAY_REVIEW row has field_size={r.get('rp_field_size')}"
        )


# ── Test 7: All rows blocked_from_live_use=True ───────────────────────────────


def test_all_rows_blocked_from_live_use(dual_lane_rows):
    """Every enriched row must have blocked_from_live_use=True and dry_run_only=True."""
    assert len(dual_lane_rows) > 0
    for r in dual_lane_rows:
        assert r.get("blocked_from_live_use") is True, (
            f"Row {r.get('ledger_id')} missing blocked_from_live_use"
        )
        assert r.get("dry_run_only") is True, (
            f"Row {r.get('ledger_id')} missing dry_run_only"
        )
        assert r.get("human_approval_required") is True, (
            f"Row {r.get('ledger_id')} missing human_approval_required"
        )


# ── Test 8: Lineage reconciliation passes ────────────────────────────────────


def test_lineage_reconciliation_passes(run_outputs):
    """Lineage JSON must report LINEAGE_CLEAN and all phases clean."""
    path = REPORTS / "vfu_18_lineage_reconciliation.json"
    assert path.exists(), "vfu_18_lineage_reconciliation.json not created"
    lin = json.loads(path.read_text(encoding="utf-8"))
    assert lin["verdict"] == "LINEAGE_CLEAN_PROCEED_TO_VFU18", (
        f"Lineage verdict: {lin['verdict']}"
    )
    assert lin["all_phases_clean"] is True
    for phase in lin["phases"]:
        assert phase["lineage_clean"] is True, (
            f"Phase {phase['vfu']} not clean: missing={phase.get('report_files_missing')}"
        )
        assert phase["changed_live_scoring"] is False
        assert phase["mutated_passport"] is False
        assert phase["wrote_supabase"] is False
        assert phase["promoted_doctrine"] is False
        assert phase["sent_telegram"] is False
        assert phase["touched_racing_api"] is False


# ── Test 9: Place specialist watchlist ───────────────────────────────────────


def test_place_specialist_watchlist(run_outputs):
    """Watchlist must exist, have 16 specialists, all blocked."""
    path = REPORTS / "vfu_18_place_specialist_watchlist.json"
    assert path.exists()
    wl = json.loads(path.read_text(encoding="utf-8"))
    assert wl.get("blocked_from_live_use") is True
    assert wl.get("dry_run_only") is True
    assert wl["total_specialists"] == 16, f"Expected 16 specialists, got {wl['total_specialists']}"
    for e in wl["entries"]:
        assert e.get("blocked_from_live_use") is True


# ── Test 10: Win-to-place downgrades have VP >= 0.40 ─────────────────────────


def test_win_to_place_downgrades(run_outputs):
    """Win-to-place downgrade rows must all have VP >= 0.40."""
    path = REPORTS / "vfu_18_win_to_place_downgrades.json"
    assert path.exists()
    downgrades = json.loads(path.read_text(encoding="utf-8"))
    assert len(downgrades) > 0, "No win-to-place downgrades"
    from scripts.ops.vfu_place_data_enrichment import VP_THRESHOLD
    for d in downgrades:
        assert (d.get("vp") or 0) >= VP_THRESHOLD, (
            f"Downgrade {d.get('ledger_id')} has VP={d.get('vp')}"
        )
        assert d.get("blocked_from_live_use") is True
        assert d.get("dual_lane_label") in ("EACH_WAY_REVIEW", "WIN_SIGNAL_PLACE_OUTCOME")


# ── Test 11: Place-to-win upgrades have VP < 0.40 ────────────────────────────


def test_place_to_win_upgrades(run_outputs):
    """Place-to-win upgrade rows must have VP < 0.40 (place signal, not VP)."""
    path = REPORTS / "vfu_18_place_to_win_upgrades.json"
    assert path.exists()
    upgrades = json.loads(path.read_text(encoding="utf-8"))
    assert len(upgrades) > 0, "No place-to-win upgrades"
    from scripts.ops.vfu_place_data_enrichment import VP_THRESHOLD
    for u in upgrades:
        assert (u.get("vp") or 0) < VP_THRESHOLD, (
            f"Upgrade {u.get('ledger_id')} has VP={u.get('vp')} >= {VP_THRESHOLD}"
        )
        assert u.get("blocked_from_live_use") is True
        assert u.get("dual_lane_label") == "PLACE_SIGNAL_WIN_OUTCOME"


# ── Test 12: No Supabase writes ───────────────────────────────────────────────


def test_no_supabase_writes(mod):
    """Script must not import or call Supabase write functions."""
    src = SCRIPT.read_text(encoding="utf-8")
    for token in ["create_client", "SUPABASE_URL", ".upsert(", ".insert("]:
        assert token not in src, f"Supabase token found: {token}"
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", "") or ""
            assert "supabase" not in module, "supabase imported in script"


# ── Test 13: No live scoring or Telegram ─────────────────────────────────────


def test_no_live_scoring_or_telegram(mod):
    """Script must not contain live scoring write or Telegram dispatch calls."""
    src = SCRIPT.read_text(encoding="utf-8")
    for token in ["run_prime_today", "score_race", "telegram.Bot(",
                  "bot.send_message", "send_telegram"]:
        assert token not in src, f"Live scoring/Telegram token found: {token}"
    assert "NO_LIVE_SCORING_CHANGE" in src
    assert "NO_TELEGRAM_SEND" in src


# ── Test 14: VP threshold unchanged ──────────────────────────────────────────


def test_vp_threshold_unchanged(mod):
    """VP_THRESHOLD must be exactly 0.40 throughout."""
    assert mod.VP_THRESHOLD == 0.40
    assert "VP_THRESHOLD = 0.40" in SCRIPT.read_text(encoding="utf-8")


# ── Test 15: Summary report with 16 final classifications ────────────────────


def test_summary_report_with_16_classifications(run_outputs, summary):
    """Summary JSON + MD must exist and contain all 16 final classifications."""
    assert (REPORTS / "vfu_18_place_data_enrichment_summary.json").exists()
    assert (REPORTS / "vfu_18_place_data_enrichment_summary.md").exists()

    assert "final_classifications" in summary
    for clf in [
        "VFU_18_PLACE_DATA_ENRICHMENT_COMPLETE",
        "VFU_LINEAGE_RECONCILED",
        "DUAL_LANE_CLASSIFICATIONS_CREATED",
        "PLACE_SPECIALIST_WATCHLIST_CREATED",
        "WIN_TO_PLACE_DOWNGRADES_REPORTED",
        "PLACE_TO_WIN_UPGRADES_REPORTED",
        "FIELD_SIZE_GAPS_REPORTED",
        "NO_STAKING_INSTRUCTIONS_CREATED",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "NO_VP_THRESHOLD_CHANGE",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
    ]:
        assert clf in summary["final_classifications"], f"Missing classification: {clf}"

    assert summary["vp_threshold"] == 0.40
    assert summary["total_enriched_rows"] == 3052

    # All 10 output files present
    for fname in [
        "vfu_18_lineage_reconciliation.json",
        "vfu_18_lineage_reconciliation.md",
        "vfu_18_dual_lane_records.jsonl",
        "vfu_18_place_specialist_watchlist.json",
        "vfu_18_win_to_place_downgrades.json",
        "vfu_18_place_to_win_upgrades.json",
        "vfu_18_place_data_quality_gaps.json",
        "vfu_18_dual_lane_cockpit.json",
        "vfu_18_place_data_enrichment_summary.json",
        "vfu_18_place_data_enrichment_summary.md",
    ]:
        assert (REPORTS / fname).exists(), f"Output file missing: {fname}"
