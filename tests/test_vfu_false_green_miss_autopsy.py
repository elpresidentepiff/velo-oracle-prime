"""
tests/test_vfu_false_green_miss_autopsy.py
===========================================
VFU-15 — False-GREEN MISS Autopsy test suite.
14 required tests.

Run via WSL:
  wsl -e bash -c "cd /mnt/c/Users/puror/velo-oracle-prime && PYTHONPATH=. venv/bin/python -m pytest tests/test_vfu_false_green_miss_autopsy.py -v"
"""
import json
import re
from pathlib import Path

import pytest

ROOT   = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ops/vfu_false_green_miss_autopsy.py"

MISS_JSONL      = ROOT / "data/reports/vfu_15_miss_cases.jsonl"
BY_BAND_JSON    = ROOT / "data/reports/vfu_15_miss_by_price_band.json"
COMPONENT_JSON  = ROOT / "data/reports/vfu_15_miss_component_breakdown.json"
SOURCE_GAP_JSON = ROOT / "data/reports/vfu_15_miss_source_gap.json"
DENOM_JSON      = ROOT / "data/reports/vfu_15_miss_denominator_audit.json"
NAMED_GAPS_JSON = ROOT / "data/reports/vfu_15_miss_named_evidence_gaps.json"
SUMMARY_JSON    = ROOT / "data/reports/vfu_15_miss_autopsy_summary.json"
SUMMARY_MD      = ROOT / "data/reports/vfu_15_miss_autopsy_summary.md"

VP_THRESHOLD     = 0.40
ERA_CURRENT_START = "2026-05-08"

VALID_SP_CLASSIFICATIONS = {
    "ODDS_ON_MISS", "SHORT_PRICE_MISS", "MID_PRICE_MISS",
    "DANGER_ZONE_MISS", "LONGSHOT_MISS", "DRAIN_MISS",
    "SP_SOURCE_ZERO_BLOCKER", "SOURCE_GAP_NO_SP",
}

VALID_COMPONENT_DRIVERS = {
    "PLACE_PROB_DOMINANT", "SQPE_ELEVATED",
    "IMPROVEMENT_ELEVATED", "MARKET_DECEPTION_ELEVATED",
    "MIXED_SIGNAL", "COMPONENT_DATA_MISSING",
}

VALID_MARKET_AGREEMENT = {
    "MARKET_AGREED_MISS", "MARKET_NEUTRAL", "MARKET_SCEPTICAL", "NO_MARKET_DATA",
}

REQUIRED_FINAL_CLASSIFICATIONS = [
    "VFU_15_FALSE_GREEN_MISS_AUTOPSY_COMPLETE",
    "MISS_CASES_SCOPE_56_ONLY",
    "PLACED_CASES_EXCLUDED",
    "SHORT_PRICE_MISS_IS_DOMINANT_FAILURE_MODE",
    "PLACE_PROB_DOMINANT_IN_MISS_COMPONENT_CASES",
    "SP_SOURCE_ZERO_BLOCKER_LOGGED",
    "DENOMINATOR_AUDIT_COMPLETE",
    "NAMED_EVIDENCE_GAPS_DOCUMENTED",
    "NO_VP_THRESHOLD_CHANGE",
    "NO_LIVE_DOCTRINE_PROMOTION",
    "MAR_APR_QUARANTINE_MAINTAINED",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "NO_LIVE_SCORING_CHANGE",
    "NO_SUPABASE_WRITES",
    "NO_MODEL_PROMOTION",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_miss() -> list[dict]:
    return [
        json.loads(ln)
        for ln in MISS_JSONL.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]


def load_summary() -> dict:
    return json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))


def load_by_band() -> dict:
    return json.loads(BY_BAND_JSON.read_text(encoding="utf-8"))


def load_component() -> dict:
    return json.loads(COMPONENT_JSON.read_text(encoding="utf-8"))


def load_source_gap() -> dict:
    return json.loads(SOURCE_GAP_JSON.read_text(encoding="utf-8"))


def load_denom() -> dict:
    return json.loads(DENOM_JSON.read_text(encoding="utf-8"))


def load_named_gaps() -> dict:
    return json.loads(NAMED_GAPS_JSON.read_text(encoding="utf-8"))


# ── Test 01: Script exists and imports cleanly ─────────────────────────────────

def test_01_script_exists_and_imports():
    """VFU-15 script must exist with required functions and VP_THRESHOLD=0.40."""
    assert SCRIPT.exists(), f"Script missing: {SCRIPT}"
    import importlib.util
    spec = importlib.util.spec_from_file_location("vfu_false_green_miss_autopsy", SCRIPT)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "main"),                "Script must define main()"
    assert hasattr(mod, "sp_classification"),   "Script must define sp_classification()"
    assert hasattr(mod, "component_driver"),    "Script must define component_driver()"
    assert hasattr(mod, "annotate_miss_case"),  "Script must define annotate_miss_case()"
    assert mod.VP_THRESHOLD == 0.40,            f"VP_THRESHOLD must be 0.40, got {mod.VP_THRESHOLD}"
    assert mod.VALIDATION_VERSION == "VFU_15_FALSE_GREEN_MISS_AUTOPSY_V1"


# ── Test 02: Reads VFU-14 enriched cases ──────────────────────────────────────

def test_02_reads_vfu14_enriched_cases():
    """VFU-14 enriched cases must exist and contain 121 entries."""
    enriched_path = ROOT / "data/reports/vfu_14_false_green_sp_enriched_cases.jsonl"
    assert enriched_path.exists(), f"VFU-14 enriched cases missing: {enriched_path}"
    cases = [json.loads(ln) for ln in enriched_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(cases) == 121, f"Expected 121 enriched cases, got {len(cases)}"

    # All must be current-era FG cases
    for c in cases:
        assert str(c.get("race_date", ""))[:10] >= ERA_CURRENT_START
        assert c.get("vp") is not None and c.get("vp") >= VP_THRESHOLD
        assert str(c.get("outcome", "")).upper() != "WIN"


# ── Test 03: Only MISS cases in scope ─────────────────────────────────────────

def test_03_only_miss_cases_in_scope():
    """MISS cases must be exactly 56, all is_miss=True, is_placed_not_won=False."""
    miss = load_miss()
    assert len(miss) == 56, f"Expected 56 MISS cases, got {len(miss)}"

    for i, c in enumerate(miss):
        assert c.get("is_miss") is True, \
            f"Case {i} ({c.get('horse_name')}) must have is_miss=True"
        assert not c.get("is_placed_not_won"), \
            f"Case {i} ({c.get('horse_name')}) must not be is_placed_not_won"
        vp = c.get("vp")
        assert vp is not None and vp >= VP_THRESHOLD, \
            f"Case {i} VP={vp} must be >= {VP_THRESHOLD}"


# ── Test 04: PLACED cases excluded ────────────────────────────────────────────

def test_04_placed_cases_excluded():
    """PLACED cases (65) must not appear in VFU-15 MISS output."""
    miss = load_miss()
    # None should be placed
    placed_in_miss = [c for c in miss if c.get("is_placed_not_won")]
    assert not placed_in_miss, (
        f"{len(placed_in_miss)} PLACED cases leaked into MISS autopsy: "
        + str([c.get("horse_name") for c in placed_in_miss[:3]])
    )

    # Summary must confirm placed_cases_excluded
    summary = load_summary()
    assert summary.get("placed_cases_excluded") is True
    assert "PLACED_CASES_EXCLUDED" in summary.get("final_classifications", [])
    assert summary["stats"]["placed_cases_excluded"] == 65


# ── Test 05: SP classifications are valid and cover all 56 ────────────────────

def test_05_sp_classifications_valid():
    """Every MISS case must have a valid vfu15_sp_classification covering all 56."""
    miss = load_miss()
    from collections import Counter
    spc_counts = Counter(c.get("vfu15_sp_classification") for c in miss)

    for i, c in enumerate(miss):
        spc = c.get("vfu15_sp_classification")
        assert spc in VALID_SP_CLASSIFICATIONS, (
            f"Case {i} ({c.get('horse_name')}) has invalid sp_classification: {spc}"
        )
    # Total must equal 56
    assert sum(spc_counts.values()) == 56, f"SP classification counts do not sum to 56: {dict(spc_counts)}"
    # SHORT_PRICE_MISS must be the largest group (dominant failure mode)
    dominant = spc_counts.most_common(1)[0][0]
    assert dominant == "SHORT_PRICE_MISS", (
        f"Expected SHORT_PRICE_MISS as dominant failure, got {dominant}"
    )


# ── Test 06: SP_SOURCE_ZERO_BLOCKER correctly identified ──────────────────────

def test_06_sp_source_zero_blocker_logged():
    """June 5 zero-SP cases must be classified SP_SOURCE_ZERO_BLOCKER, not guessed."""
    miss = load_miss()
    zero_block = [c for c in miss if c.get("vfu15_sp_classification") == "SP_SOURCE_ZERO_BLOCKER"]
    assert len(zero_block) > 0, "Expected at least one SP_SOURCE_ZERO_BLOCKER case"

    for c in zero_block:
        # Must have no pick_sp (not guessed)
        assert c.get("pick_sp") is None, (
            f"SP_SOURCE_ZERO_BLOCKER case {c.get('horse_name')} must have pick_sp=None"
        )
        # Must have the correct missing reason
        assert c.get("pick_sp_missing_reason") == "RACE_FOUND_BUT_HORSE_NOT_IN_RUNNERS", (
            f"SP_SOURCE_ZERO_BLOCKER case must have RACE_FOUND_BUT_HORSE_NOT_IN_RUNNERS reason"
        )

    # Source gap report must document these
    gap = load_source_gap()
    assert gap.get("sp_source_zero_blocker") == len(zero_block)
    assert "zero_blocker_note" in gap
    assert "SP_SOURCE_ZERO_BLOCKER" in gap["zero_blocker_note"]

    # Summary must confirm
    summary = load_summary()
    assert "SP_SOURCE_ZERO_BLOCKER_LOGGED" in summary.get("final_classifications", [])


# ── Test 07: Denominator audit correct (109 vs 121) ──────────────────────────

def test_07_denominator_audit_correct():
    """Denominator audit must explain 109 vs 121 with correct counts."""
    denom = load_denom()

    assert denom.get("total_fg_cases") == 121
    assert denom.get("already_had_sp_vfu13") == 12
    assert denom.get("sp_recovery_denominator") == 109
    assert denom.get("recovered_by_vfu14") == 89
    assert denom.get("still_missing_after_vfu14") == 20
    assert denom.get("total_with_sp_now") == 12 + 89  # 101

    summary = load_summary()
    assert "DENOMINATOR_AUDIT_COMPLETE" in summary.get("final_classifications", [])


# ── Test 08: Named evidence gaps documented (Food For Thought) ────────────────

def test_08_named_evidence_gaps_documented():
    """Food For Thought must be identified as a named P0 evidence gap."""
    named = load_named_gaps()

    fft = named.get("food_for_thought_status", {})
    assert fft.get("found") is True, "Food For Thought must be found in MISS set"
    assert fft.get("horse_name") == "Food For Thought"
    assert fft.get("evidence_gap_classification") == "P0_HUMAN_REVIEW_DATA_LINEAGE"
    assert "RAC_PREFIX_NOT_IN_ANY_SOURCE" in (fft.get("pick_sp_missing_reason") or "")
    assert "Beverley" in (fft.get("course") or "")

    summary = load_summary()
    assert "NAMED_EVIDENCE_GAPS_DOCUMENTED" in summary.get("final_classifications", [])


# ── Test 09: Component driver assigned for all cases ─────────────────────────

def test_09_component_driver_assigned():
    """Every MISS case must have a valid vfu15_component_driver."""
    miss = load_miss()

    for i, c in enumerate(miss):
        cd = c.get("vfu15_component_driver")
        assert cd in VALID_COMPONENT_DRIVERS, (
            f"Case {i} ({c.get('horse_name')}) has invalid component_driver: {cd}"
        )

    # Cases WITHOUT component data must be COMPONENT_DATA_MISSING
    no_data = [c for c in miss if not c.get("has_component_data")]
    for c in no_data:
        assert c.get("vfu15_component_driver") == "COMPONENT_DATA_MISSING", (
            f"{c.get('horse_name')} has no component data but driver != COMPONENT_DATA_MISSING"
        )

    # Component breakdown must report PLACE_PROB_DOMINANT as most common driver
    comp = load_component()
    driver_dist = comp.get("component_driver_distribution", {})
    if driver_dist:
        top_driver = max(driver_dist, key=driver_dist.get)
        assert top_driver == "PLACE_PROB_DOMINANT", (
            f"Expected PLACE_PROB_DOMINANT as top driver in cases with data, got {top_driver}"
        )


# ── Test 10: VP threshold unchanged ───────────────────────────────────────────

def test_10_vp_threshold_unchanged():
    """VP_THRESHOLD must be 0.40 in script and summary."""
    from scripts.ops.vfu_false_green_miss_autopsy import VP_THRESHOLD as VPT
    assert VPT == 0.40

    summary = load_summary()
    assert summary.get("vp_threshold") == 0.40
    assert summary.get("vp_threshold_unchanged") is True
    assert "NO_VP_THRESHOLD_CHANGE" in summary.get("final_classifications", [])


# ── Test 11: No Supabase writes in script ─────────────────────────────────────

def test_11_no_supabase_writes():
    """Script must not contain Supabase write operations."""
    code = SCRIPT.read_text(encoding="utf-8")
    write_patterns = [
        r"\.table\(.*\)\.insert\(",
        r"\.table\(.*\)\.upsert\(",
        r"\.table\(.*\)\.update\(",
        r"\.table\(.*\)\.delete\(",
        r"supabase.*\.insert\(",
    ]
    for pat in write_patterns:
        bad = [
            ln for ln in code.splitlines()
            if re.search(pat, ln) and not ln.strip().startswith("#")
        ]
        assert not bad, f"Supabase write pattern '{pat}' found: {bad[:3]}"

    summary = load_summary()
    assert summary.get("supabase_written") is False
    assert "NO_SUPABASE_WRITES" in summary.get("final_classifications", [])


# ── Test 12: No Passport mutation ────────────────────────────────────────────

def test_12_no_passport_mutation():
    """Script must not mutate canonical Horse Passport."""
    code = SCRIPT.read_text(encoding="utf-8")
    parquet_writes = [
        ln for ln in code.splitlines()
        if "to_parquet" in ln and not ln.strip().startswith("#")
    ]
    assert not parquet_writes, f"Script must not write parquet: {parquet_writes}"

    summary = load_summary()
    assert summary.get("canonical_passport_mutated") is False
    assert "CANONICAL_HORSE_PASSPORT_NOT_MUTATED" in summary.get("final_classifications", [])


# ── Test 13: All 8 output files created ───────────────────────────────────────

def test_13_all_output_files_created():
    """All 8 VFU-15 output files must exist."""
    required = [
        MISS_JSONL, BY_BAND_JSON, COMPONENT_JSON, SOURCE_GAP_JSON,
        DENOM_JSON, NAMED_GAPS_JSON, SUMMARY_JSON, SUMMARY_MD,
    ]
    missing = [str(p) for p in required if not p.exists()]
    assert not missing, f"Output files missing: {missing}"

    # Each MISS case must have VFU-15 annotation fields
    miss = load_miss()
    for i, c in enumerate(miss):
        assert "vfu15_sp_classification"  in c, f"Case {i} missing vfu15_sp_classification"
        assert "vfu15_component_driver"   in c, f"Case {i} missing vfu15_component_driver"
        assert "vfu15_market_agreement"   in c, f"Case {i} missing vfu15_market_agreement"
        assert "vfu15_surface"            in c, f"Case {i} missing vfu15_surface"
        assert "vfu15_is_drain"           in c, f"Case {i} missing vfu15_is_drain"
        assert c.get("vfu15_validation_version") == "VFU_15_FALSE_GREEN_MISS_AUTOPSY_V1"


# ── Test 14: Summary has all 15 required final classifications ────────────────

def test_14_summary_has_required_classifications():
    """Summary JSON and MD must carry all 15 required final classifications."""
    assert SUMMARY_JSON.exists()
    assert SUMMARY_MD.exists()

    summary = load_summary()
    actual  = summary.get("final_classifications", [])

    missing = [c for c in REQUIRED_FINAL_CLASSIFICATIONS if c not in actual]
    assert not missing, f"Missing required classifications: {missing}"
    assert len(actual) >= 15, f"Expected >=15 classifications, got {len(actual)}"

    # Safety flags
    assert summary.get("canonical_passport_mutated") is False
    assert summary.get("supabase_written") is False
    assert summary.get("live_scoring_changed") is False
    assert summary.get("model_promoted") is False
    assert summary.get("mar_apr_quarantine_only") is True
    assert summary.get("blocked_from_live_use") is True
    assert summary.get("human_approval_required") is True
    assert summary.get("dry_run_only") is True

    # MD must reference key content
    md = SUMMARY_MD.read_text(encoding="utf-8")
    assert "VFU-15" in md
    assert "0.40" in md
    assert "DRY RUN" in md or "dry_run" in md.lower()
    assert "56" in md  # MISS count
    assert "PLACED" in md  # exclusion note
