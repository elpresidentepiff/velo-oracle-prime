"""Tests for VFU-17 — Win / Place Position Engine."""

import json
import subprocess
from pathlib import Path

import pytest

REPORTS = Path("data/reports")
SCRIPT = Path("scripts/ops/vfu_win_place_position_engine.py")


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vfu17", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def run_outputs():
    """Run the script once and make all output files available."""
    result = subprocess.run(
        ["bash", "-c",
         "cd /mnt/c/Users/puror/velo-oracle-prime && "
         "PYTHONPATH=. venv/bin/python scripts/ops/vfu_win_place_position_engine.py"],
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, f"Script failed:\n{result.stdout}\n{result.stderr}"
    return result


# ── Test 1: Place cutoff logic ────────────────────────────────────────────────


def test_place_cutoff_logic(mod):
    """Place cutoff returns correct values for all field-size bands."""
    assert mod.place_cutoff(3) == (1, mod.PLACE_CUTOFF_WIN_ONLY)
    assert mod.place_cutoff(4) == (1, mod.PLACE_CUTOFF_WIN_ONLY)
    assert mod.place_cutoff(5) == (2, mod.PLACE_CUTOFF_FIELD_SIZE)
    assert mod.place_cutoff(7) == (2, mod.PLACE_CUTOFF_FIELD_SIZE)
    assert mod.place_cutoff(8) == (3, mod.PLACE_CUTOFF_FIELD_SIZE)
    assert mod.place_cutoff(15) == (3, mod.PLACE_CUTOFF_FIELD_SIZE)
    assert mod.place_cutoff(16) == (4, mod.PLACE_CUTOFF_FIELD_SIZE)
    assert mod.place_cutoff(20) == (4, mod.PLACE_CUTOFF_FIELD_SIZE)


# ── Test 2: Missing field_size → PLACE_CUTOFF_UNKNOWN ────────────────────────


def test_missing_field_size_produces_unknown(mod):
    """None field_size must produce PLACE_CUTOFF_UNKNOWN — never a guess."""
    cutoff, conf = mod.place_cutoff(None)
    assert cutoff is None
    assert conf == mod.PLACE_CUTOFF_UNKNOWN


# ── Test 3: Outcome → WIN/PLACE/MISS correctly ───────────────────────────────


def test_outcome_to_win_place_miss(mod):
    """Raw sigma outcomes map correctly to outcome classes."""
    assert mod._SIGMA_OUTCOME_MAP["WIN"] == mod.WIN
    assert mod._SIGMA_OUTCOME_MAP["PLACED"] == mod.PLACE
    assert mod._SIGMA_OUTCOME_MAP["FRAME"] == mod.FRAME
    assert mod._SIGMA_OUTCOME_MAP["MISS"] == mod.MISS
    assert mod._SIGMA_OUTCOME_MAP[None] == mod.UNKNOWN_RESULT

    is_place, conf = mod.actual_place_from_outcome("WIN")
    assert is_place is True and conf == mod.WIN

    is_place, conf = mod.actual_place_from_outcome("PLACED")
    assert is_place is True and conf == mod.PLACE

    is_place, conf = mod.actual_place_from_outcome("MISS")
    assert is_place is False and conf == mod.MISS

    assert mod.actual_win_from_outcome("WIN") is True
    assert mod.actual_win_from_outcome("PLACED") is False
    assert mod.actual_win_from_outcome("MISS") is False


# ── Test 4: No invented place outcome when data missing ───────────────────────


def test_no_invented_place_outcome(mod):
    """When outcome is None, result must be UNKNOWN_RESULT — never PLACE."""
    is_place, conf = mod.actual_place_from_outcome(None)
    assert is_place is None
    assert conf == mod.UNKNOWN_RESULT
    # Unknown outcome also returns None win
    assert mod.actual_win_from_outcome(None) is None


# ── Test 5: Place specialist candidates are dry-run only ─────────────────────


def test_place_specialist_dry_run_only(run_outputs):
    """All place specialist candidates must be blocked_from_live_use=True."""
    path = REPORTS / "vfu_17_place_specialist_candidates.json"
    assert path.exists()
    candidates = json.loads(path.read_text(encoding="utf-8"))
    assert len(candidates) > 0, "No place specialist candidates found"
    for c in candidates:
        assert c.get("blocked_from_live_use") is True, (
            f"{c.get('horse_name')} missing blocked_from_live_use"
        )
        assert c.get("human_review_required") is True
        assert c.get("do_not_merge") is True

    # Named specialists must be present
    names = {c.get("horse_name", "").lower() for c in candidates}
    assert "navy light" in names, "Navy Light not in place specialists"
    assert "gaelic approach" in names, "Gaelic Approach not in place specialists"
    assert "humble spark" in names, "Humble Spark not in place specialists"


# ── Test 6: Win-to-place downgrades generated ─────────────────────────────────


def test_win_to_place_downgrades_generated(run_outputs):
    """Downgrades must exist and contain horses where VP >= 0.40 but placed only."""
    path = REPORTS / "vfu_17_win_to_place_downgrades.json"
    assert path.exists()
    downgrades = json.loads(path.read_text(encoding="utf-8"))
    assert len(downgrades) > 0, "No win-to-place downgrades found"
    for d in downgrades:
        assert d.get("blocked_from_live_use") is True
        assert d.get("best_vp") is not None
        assert d.get("best_vp") >= 0.40, (
            f"Downgrade {d.get('horse_name')} has VP={d.get('best_vp')} < 0.40"
        )


# ── Test 7: Place-to-win upgrades generated ───────────────────────────────────


def test_place_to_win_upgrades_generated(run_outputs):
    """Upgrade candidates must exist and have upgrade signals."""
    path = REPORTS / "vfu_17_place_to_win_upgrades.json"
    assert path.exists()
    upgrades = json.loads(path.read_text(encoding="utf-8"))
    assert len(upgrades) > 0, "No place-to-win upgrades found"
    for u in upgrades:
        assert u.get("blocked_from_live_use") is True
        assert u.get("do_not_promote_without_review") is True
        assert len(u.get("upgrade_signals", [])) > 0


# ── Test 8: All outputs blocked_from_live_use=True ────────────────────────────


def test_all_outputs_blocked(run_outputs):
    """Win/place records JSONL must have blocked_from_live_use=True on every row."""
    records = [
        json.loads(ln)
        for ln in (REPORTS / "vfu_17_win_place_records.jsonl").read_text().splitlines()
        if ln.strip()
    ]
    assert len(records) > 0
    for r in records:
        assert r.get("blocked_from_live_use") is True, (
            f"Record {r.get('ledger_id')} missing blocked_from_live_use"
        )
        assert r.get("dry_run_only") is True


# ── Test 9: No canonical Passport mutation ────────────────────────────────────


def test_no_passport_mutation(mod):
    """Script source must not call Passport write functions."""
    src = SCRIPT.read_text(encoding="utf-8")
    for token in ["upsert_horse_passport", "update_passport", "write_passport", "do_not_merge ="]:
        assert token not in src, f"Passport mutation call found: {token}"
    import ast
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", "") or ""
            assert "supabase" not in module


# ── Test 10: No Supabase dependency ──────────────────────────────────────────


def test_no_supabase_dependency(mod):
    """Script must not import or call Supabase."""
    src = SCRIPT.read_text(encoding="utf-8")
    for token in ["create_client", "SUPABASE_URL", ".upsert(", ".insert("]:
        assert token not in src, f"Supabase token found: {token}"


# ── Test 11: VP threshold unchanged ──────────────────────────────────────────


def test_vp_threshold_unchanged(mod):
    """VP_THRESHOLD must be exactly 0.40."""
    assert mod.VP_THRESHOLD == 0.40
    assert "VP_THRESHOLD = 0.40" in SCRIPT.read_text(encoding="utf-8")


# ── Test 12: No live scoring change ──────────────────────────────────────────


def test_no_live_scoring_change(mod):
    """Script must not contain live scoring write or dispatch calls."""
    src = SCRIPT.read_text(encoding="utf-8")
    for token in ["run_prime_today", "score_race", "send_telegram",
                  "telegram.Bot(", "telegram.bot", "bot.send_message"]:
        assert token not in src, f"Live scoring token found: {token}"
    # Must have NO_LIVE_SCORING_CHANGE in final classifications
    assert "NO_LIVE_SCORING_CHANGE" in src


# ── Test 13: Summary report generated + 15 classifications ───────────────────


def test_summary_report_generated(run_outputs):
    """Summary JSON + MD must exist and contain all 15 final classifications."""
    json_path = REPORTS / "vfu_17_win_place_position_summary.json"
    md_path = REPORTS / "vfu_17_win_place_position_summary.md"
    assert json_path.exists(), "Summary JSON not created"
    assert md_path.exists(), "Summary MD not created"

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "final_classifications" in data
    for clf in [
        "VFU_17_WIN_PLACE_POSITION_ENGINE_COMPLETE",
        "WIN_PLACE_OUTCOME_CLASSES_CREATED",
        "PLACE_SPECIALIST_CANDIDATES_CREATED",
        "WIN_TO_PLACE_DOWNGRADES_CREATED",
        "PLACE_TO_WIN_UPGRADES_CREATED",
        "NO_INVENTED_PLACE_OUTCOMES",
        "PLACE_LOGIC_DRY_RUN_ONLY",
        "NO_LIVE_SCORING_CHANGE",
        "NO_VP_THRESHOLD_CHANGE",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
        "NAVY_LIGHT_GAELIC_APPROACH_HUMBLE_SPARK_CONFIRMED_PLACE_SPECIALISTS",
    ]:
        assert clf in data["final_classifications"], f"Missing: {clf}"

    # Outcome distribution must cover 3052 current-era rows
    oc = data.get("outcome_distribution", {})
    total_in_oc = sum(oc.values())
    assert total_in_oc == data["total_current_era_rows"], (
        f"Outcome dist total {total_in_oc} != rows {data['total_current_era_rows']}"
    )

    # All 7 output files present
    for fname in [
        "vfu_17_win_place_position_summary.json",
        "vfu_17_win_place_position_summary.md",
        "vfu_17_win_place_records.jsonl",
        "vfu_17_place_specialist_candidates.json",
        "vfu_17_win_to_place_downgrades.json",
        "vfu_17_place_to_win_upgrades.json",
        "vfu_17_human_review_queue.json",
    ]:
        assert (REPORTS / fname).exists(), f"Output file missing: {fname}"
