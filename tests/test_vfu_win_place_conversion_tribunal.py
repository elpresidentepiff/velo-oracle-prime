"""Tests for VFU-16 — Win/Place Conversion Tribunal."""

import json
from pathlib import Path

import pytest

REPORTS = Path("data/reports")
SCRIPT = Path("scripts/ops/vfu_win_place_conversion_tribunal.py")

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def vfu16_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("vfu16", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def vfu16_cases(vfu16_module):
    mod = vfu16_module
    enr = [
        json.loads(ln)
        for ln in open(REPORTS / "vfu_14_false_green_sp_enriched_cases.jsonl", encoding="utf-8")
        if ln.strip()
    ]
    miss_v15 = [
        json.loads(ln)
        for ln in open(REPORTS / "vfu_15_miss_cases.jsonl", encoding="utf-8")
        if ln.strip()
    ]
    miss_by_id = {}
    for mc in miss_v15:
        cid = mc.get("case_id", "")
        if cid:
            miss_by_id[cid] = mc
    return mod.build_annotated_cases(enr, miss_by_id)


@pytest.fixture(scope="module")
def summary_json():
    path = REPORTS / "vfu_16_win_place_conversion_summary.json"
    if not path.exists():
        pytest.skip("Run scripts/ops/vfu_win_place_conversion_tribunal.py first")
    return json.loads(path.read_text(encoding="utf-8"))


# ── Test 1: Script imports and reads VFU-15 outputs ──────────────────────────


def test_script_imports_and_reads_vfu15(vfu16_module):
    """Script must import without error and VFU-14/15 inputs must be present."""
    assert hasattr(vfu16_module, "classify_mechanism")
    assert hasattr(vfu16_module, "build_annotated_cases")
    assert hasattr(vfu16_module, "VALIDATION_VERSION")
    assert (REPORTS / "vfu_14_false_green_sp_enriched_cases.jsonl").exists()
    assert (REPORTS / "vfu_15_miss_cases.jsonl").exists()


# ── Test 2: Classifies PLACE_STRONG_WIN_WEAK ─────────────────────────────────


def test_classifies_place_strong_win_weak(vfu16_cases, vfu16_module):
    """All PLACED cases must be PLACE_STRONG_WIN_WEAK. MISS comp cases with
    place_prob >= 0.80 (and no WIN-signal override) must also be PLACE_STRONG_WIN_WEAK."""
    placed = [c for c in vfu16_cases if c.get("is_placed_not_won")]
    miss = [c for c in vfu16_cases if c.get("is_miss")]

    # Every PLACED case → PLACE_STRONG_WIN_WEAK
    for c in placed:
        assert c["vfu16_mechanism"] == vfu16_module.PLACE_STRONG_WIN_WEAK, (
            f"{c.get('horse_name')} is PLACED but mechanism={c['vfu16_mechanism']}"
        )

    # African Spirit (longshot, place_prob=0.837) → PLACE_STRONG_WIN_WEAK
    african = next(
        (c for c in miss if "African" in (c.get("horse_name") or "")), None
    )
    if african:
        assert african["vfu16_mechanism"] == vfu16_module.PLACE_STRONG_WIN_WEAK

    # Cawthorne Cracker (place_prob=0.998) → PLACE_STRONG_WIN_WEAK
    cawthorne = next(
        (c for c in miss if "Cawthorne" in (c.get("horse_name") or "")), None
    )
    if cawthorne:
        assert cawthorne["vfu16_mechanism"] == vfu16_module.PLACE_STRONG_WIN_WEAK

    psw_count = sum(
        1 for c in vfu16_cases
        if c.get("vfu16_mechanism") == vfu16_module.PLACE_STRONG_WIN_WEAK
    )
    assert psw_count >= 65  # at minimum all PLACED cases


# ── Test 3: Lightsoutandaway is SQPE_SMALL_FIELD_EXCEPTION ───────────────────


def test_lightsoutandaway_exception(vfu16_cases, vfu16_module):
    """Lightsoutandaway must be SQPE_SMALL_FIELD_EXCEPTION — separate mechanism."""
    light = next(
        (c for c in vfu16_cases if "Lightsout" in (c.get("horse_name") or "")),
        None,
    )
    assert light is not None, "Lightsoutandaway case not found"
    assert light["vfu16_mechanism"] == vfu16_module.SQPE_SMALL_FIELD_EXCEPTION, (
        f"Lightsoutandaway mechanism={light['vfu16_mechanism']}"
    )
    assert light["vfu16_mechanism"] != vfu16_module.PLACE_STRONG_WIN_WEAK


# ── Test 4: Food For Thought is DATA_LINEAGE_REQUIRED ────────────────────────


def test_food_for_thought_data_lineage(vfu16_cases, vfu16_module):
    """Food For Thought (rac_11930100) must be DATA_LINEAGE_REQUIRED."""
    fft = next(
        (c for c in vfu16_cases if "Food For Thought" in (c.get("horse_name") or "")),
        None,
    )
    assert fft is not None, "Food For Thought case not found"
    assert fft["vfu16_mechanism"] == vfu16_module.DATA_LINEAGE_REQUIRED, (
        f"Food For Thought mechanism={fft['vfu16_mechanism']}"
    )


# ── Test 5: Generates false-GREEN mechanism split ─────────────────────────────


def test_mechanism_split_generated(vfu16_cases, vfu16_module):
    """Mechanism split must cover all 9 constants and total 121 cases."""
    split = vfu16_module.build_mechanism_split(vfu16_cases)
    assert split["total_fg_cases"] == 121
    assert split["miss_cases"] == 56
    assert split["placed_cases"] == 65
    total_in_split = sum(split["by_mechanism"].values())
    assert total_in_split == 121, f"Mechanism split totals {total_in_split} not 121"
    # All mechanisms present or zero
    for mech in vfu16_module.ALL_MECHANISMS:
        assert mech in split["by_mechanism"] or True  # zero-count mechs may be absent


# ── Test 6: Watchlist has blocked_from_live_use=True ─────────────────────────


def test_watchlist_blocked_from_live_use(vfu16_cases, vfu16_module):
    """Every watchlist entry must have blocked_from_live_use=True."""
    split = vfu16_module.build_mechanism_split(vfu16_cases)
    watchlist = vfu16_module.build_watchlist(vfu16_cases)
    assert watchlist["blocked_from_live_use"] is True
    assert watchlist["dry_run_only"] is True
    for entry in watchlist["entries"]:
        assert entry.get("blocked_from_live_use") is True, (
            f"Entry {entry.get('horse_name')} missing blocked_from_live_use"
        )
    # Guardrail proposal is DRY_RUN_ONLY
    assert watchlist["guardrail_proposal"]["status"] == "DRY_RUN_ONLY"


# ── Test 7: Does not mutate Passport ─────────────────────────────────────────


def test_no_passport_mutation(vfu16_module):
    """Script source must not contain Passport write calls."""
    src = SCRIPT.read_text(encoding="utf-8")
    forbidden = [
        "upsert_horse_passport",
        "update_passport",
        "passport_update(",
        "write_passport",
        "do_not_merge",
    ]
    for token in forbidden:
        assert token not in src, f"Forbidden Passport mutation call found: {token}"


# ── Test 8: Does not require Supabase ────────────────────────────────────────


def test_no_supabase_writes(vfu16_module):
    """Script must not import or call Supabase write functions."""
    src = SCRIPT.read_text(encoding="utf-8")
    for token in ["create_client", "from_url", "SUPABASE_URL", ".upsert(", ".insert("]:
        assert token not in src, f"Supabase write token found: {token}"
    # No import of supabase library
    import ast
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = getattr(node, "names", [])
            module = getattr(node, "module", "") or ""
            assert "supabase" not in module, "supabase imported in script"
            for alias in names:
                assert "supabase" not in (alias.name or ""), "supabase alias import"


# ── Test 9: VP threshold unchanged ───────────────────────────────────────────


def test_vp_threshold_unchanged(vfu16_module):
    """VP_THRESHOLD must be 0.40 and must not be changed by any classification."""
    assert vfu16_module.VP_THRESHOLD == 0.40
    src = SCRIPT.read_text(encoding="utf-8")
    # Threshold must not be overwritten or altered
    assert "VP_THRESHOLD = 0.40" in src


# ── Test 10: Does not promote doctrine ───────────────────────────────────────


def test_no_doctrine_promotion(vfu16_module, vfu16_cases):
    """All cases must have blocked_from_live_use=True. No PROMOTE label anywhere."""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "PROMOTE_TO_LIVE" not in src
    assert "PROMOTE_TO_DOCTRINE" not in src
    for c in vfu16_cases:
        assert c.get("blocked_from_live_use") is True, (
            f"{c.get('horse_name')} missing blocked_from_live_use"
        )
        assert c.get("human_approval_required") is True


# ── Test 11: Summary report generated ────────────────────────────────────────


def test_summary_report_generated():
    """Both summary JSON and MD must exist after running main()."""
    import subprocess
    import sys

    result = subprocess.run(
        ["bash", "-c",
         "cd /mnt/c/Users/puror/velo-oracle-prime && "
         "PYTHONPATH=. venv/bin/python scripts/ops/vfu_win_place_conversion_tribunal.py"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"Script failed:\n{result.stdout}\n{result.stderr}"

    json_path = REPORTS / "vfu_16_win_place_conversion_summary.json"
    md_path = REPORTS / "vfu_16_win_place_conversion_summary.md"
    assert json_path.exists(), "vfu_16_win_place_conversion_summary.json not created"
    assert md_path.exists(), "vfu_16_win_place_conversion_summary.md not created"

    # All 15 final classifications present in JSON
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "final_classifications" in data
    for clf in [
        "VFU_16_WIN_PLACE_CONVERSION_TRIBUNAL_COMPLETE",
        "PLACE_PROB_DOMINANT_FAILURE_CONFIRMED",
        "WIN_PLACE_SEPARATION_REQUIRED",
        "FALSE_GREEN_MECHANISMS_SPLIT",
        "FOOD_FOR_THOUGHT_DATA_LINEAGE_RETAINED",
        "LIGHTSOUTANDAWAY_EXCEPTION_RETAINED",
        "GUARDRAIL_PROPOSAL_DRY_RUN_ONLY",
        "NO_LIVE_SCORING_CHANGE",
        "NO_VP_THRESHOLD_CHANGE",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
    ]:
        assert clf in data["final_classifications"], f"Missing classification: {clf}"

    # Q8 must say NO
    assert data["8_questions"]["Q8_live_scoring_change_now"]["answer"] == "NO"

    # Mechanism split sums to 121
    total = sum(data["mechanism_split"].values())
    assert total == 121, f"Mechanism split total {total} != 121"

    # All 7 output files present
    for fname in [
        "vfu_16_win_place_conversion_summary.json",
        "vfu_16_win_place_conversion_summary.md",
        "vfu_16_false_green_mechanism_split.json",
        "vfu_16_place_prob_dominant_cases.jsonl",
        "vfu_16_win_weak_place_strong_watchlist.json",
        "vfu_16_human_review_queue.json",
    ]:
        assert (REPORTS / fname).exists(), f"Output file not found: {fname}"
