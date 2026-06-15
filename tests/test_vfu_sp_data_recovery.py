"""
tests/test_vfu_sp_data_recovery.py
====================================
VFU-14 — SP Data Recovery + False-GREEN Price Attribution test suite.
14 required tests.

Run via WSL:
  wsl -e bash -c "cd /mnt/c/Users/puror/velo-oracle-prime && PYTHONPATH=. venv/bin/python -m pytest tests/test_vfu_sp_data_recovery.py -v"
"""
import json
import re
from pathlib import Path

import pytest

ROOT   = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ops/vfu_sp_data_recovery.py"

ENRICHED_JSONL  = ROOT / "data/reports/vfu_14_false_green_sp_enriched_cases.jsonl"
UNMATCHED_JSON  = ROOT / "data/reports/vfu_14_sp_recovery_unmatched.json"
AMBIGUOUS_JSON  = ROOT / "data/reports/vfu_14_sp_recovery_ambiguous.json"
ATTR_JSON       = ROOT / "data/reports/vfu_14_false_green_price_attribution.json"
ATTR_MD         = ROOT / "data/reports/vfu_14_false_green_price_attribution.md"
SUMMARY_JSON    = ROOT / "data/reports/vfu_14_sp_data_recovery_summary.json"
SUMMARY_MD      = ROOT / "data/reports/vfu_14_sp_data_recovery_summary.md"

VP_THRESHOLD    = 0.40
ERA_CURRENT_START = "2026-05-08"

VALID_PRICE_BANDS = {"ODDS_ON", "SHORT", "MID_PRICE", "DANGER", "LONGSHOT", "UNKNOWN"}

VALID_ATTRIBUTION_LABELS = {
    "PLACE_SIGNAL_NOT_WIN_SIGNAL",
    "HIGH_VP_SHORT_PRICE_FAILURE",
    "HIGH_VP_MID_PRICE_WALL",
    "HIGH_VP_DANGER_ZONE_FAILURE",
    "HIGH_VP_LONGSHOT_FALSE_CONFIDENCE",
    "HIGH_VP_PLACE_ONLY_SIGNAL",
    "HIGH_VP_DRAIN_COURSE_WARNING",
    "HIGH_VP_LOW_SOURCE_CONFIDENCE",
    "HIGH_VP_NO_PICK_SP_REMAINING",
    "INSUFFICIENT_PRICE_EVIDENCE",
}

VALID_MISSING_REASONS = {
    "HORSE_NAME_UNKNOWN",
    "RAC_PREFIX_NOT_IN_ANY_SOURCE",
    "DATE_NOT_IN_RP_RESULTS_FILES",
    "RP_PREFIX_RACE_NOT_IN_RESULTS_FILES",
    "RACE_FOUND_BUT_HORSE_NOT_IN_RUNNERS",
    "NUMERIC_RID_NOT_IN_NEW_FORMAT_RESULTS",
    "NON_STANDARD_RACE_ID_FORMAT",
    "NO_LOCAL_SOURCE_MATCH",
}

VALID_SP_SOURCES = {
    "vfu_13_original",
    "innovation_csv",
    "sigma_2k_training",
    "rp_results_new_format_numeric_rid",
    "rp_results_new_format_cdo_fallback",
}

REQUIRED_FINAL_CLASSIFICATIONS = [
    "VFU_14_SP_DATA_RECOVERY_COMPLETE",
    "FALSE_GREEN_PRICE_ATTRIBUTION_RERUN_COMPLETE",
    "PICK_SP_RECOVERY_REPORTED",
    "MISSING_PICK_SP_RECLASSIFIED_AS_ATTRIBUTION_BLOCKER",
    "MISS_AND_PLACED_CASES_SEPARATED",
    "PLACE_SIGNAL_NOT_WIN_SIGNAL_DECLARED",
    "NO_VP_THRESHOLD_CHANGE",
    "NO_LIVE_DOCTRINE_PROMOTION",
    "MAR_APR_QUARANTINE_MAINTAINED",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "NO_LIVE_SCORING_CHANGE",
    "NO_SUPABASE_WRITES",
    "NO_MODEL_PROMOTION",
    "NO_TELEGRAM_SEND",
    "NO_RACING_API_RESTORATION",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_enriched() -> list[dict]:
    return [
        json.loads(ln)
        for ln in ENRICHED_JSONL.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]


def load_summary() -> dict:
    return json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))


def load_attr() -> dict:
    return json.loads(ATTR_JSON.read_text(encoding="utf-8"))


def load_unmatched() -> list[dict]:
    return json.loads(UNMATCHED_JSON.read_text(encoding="utf-8"))


# ── Test 01: Script exists and imports cleanly ─────────────────────────────────

def test_01_script_exists_and_imports():
    """VFU-14 script must exist with required functions and VP_THRESHOLD=0.40."""
    assert SCRIPT.exists(), f"Script missing: {SCRIPT}"
    import importlib.util
    spec = importlib.util.spec_from_file_location("vfu_sp_data_recovery", SCRIPT)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "main"),        "Script must define main()"
    assert hasattr(mod, "match_sp"),    "Script must define match_sp()"
    assert hasattr(mod, "price_band"),  "Script must define price_band()"
    assert hasattr(mod, "assign_attribution"), "Script must define assign_attribution()"
    assert mod.VP_THRESHOLD == 0.40,    f"VP_THRESHOLD must be 0.40, got {mod.VP_THRESHOLD}"
    assert mod.SP_RECOVERY_VERSION == "VFU_14_SP_DATA_RECOVERY_V1"


# ── Test 02: Reads VFU-13 input ────────────────────────────────────────────────

def test_02_reads_vfu13_false_green_cases():
    """VFU-13 input file must exist and contain valid FG cases."""
    fg_path = ROOT / "data/reports/vfu_13_false_green_cases.jsonl"
    assert fg_path.exists(), f"VFU-13 FG cases file missing: {fg_path}"
    cases = [json.loads(ln) for ln in fg_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(cases) == 121, f"Expected 121 FG cases, got {len(cases)}"
    for c in cases:
        assert c.get("vp") is not None
        assert str(c.get("race_date", ""))[:10] >= ERA_CURRENT_START


# ── Test 03: All four SP sources accessible ────────────────────────────────────

def test_03_all_four_sp_sources_accessible():
    """All 4 SP sources must be readable."""
    assert (ROOT / "data/velo_innovation_protocol_1k_deduped.csv").exists(), \
        "S1: innovation CSV missing"
    assert (ROOT / "data/training/sigma_2k_training_dataset_latest.json").exists(), \
        "S2: sigma_2k missing"
    rp_results = list((ROOT / "data/results").glob("rp_results_2026_*.json"))
    assert len(rp_results) > 0, "S3+S4: no rp_results files found"
    # At least one new-format file (has 'results' key with numeric race_ids)
    new_fmt = [
        f for f in rp_results
        if isinstance(json.loads(f.read_text(encoding="utf-8")), dict)
        and "results" in json.loads(f.read_text(encoding="utf-8"))
    ]
    assert len(new_fmt) > 5, f"Expected >5 new-format rp_results files, got {len(new_fmt)}"


# ── Test 04: All 7 required output files created ──────────────────────────────

def test_04_all_output_files_created():
    """All 7 VFU-14 output files must exist."""
    required = [
        ENRICHED_JSONL, UNMATCHED_JSON, AMBIGUOUS_JSON,
        ATTR_JSON, ATTR_MD, SUMMARY_JSON, SUMMARY_MD,
    ]
    missing = [str(p) for p in required if not p.exists()]
    assert not missing, f"Output files missing: {missing}"


# ── Test 05: Enriched cases have all required SP fields ───────────────────────

def test_05_enriched_cases_have_required_fields():
    """Every enriched case must carry all VFU-14 SP fields."""
    cases = load_enriched()
    assert len(cases) == 121, f"Expected 121 enriched cases, got {len(cases)}"

    required_fields = [
        "pick_sp_source", "pick_sp_join_key", "pick_sp_join_confidence",
        "pick_sp_missing_reason", "pick_sp_ambiguous",
        "actual_winner_sp", "actual_winner_sp_source",
        "price_band", "price_attribution_status", "sp_recovery_version",
    ]
    for i, c in enumerate(cases):
        for field in required_fields:
            assert field in c, f"Case {i} ({c.get('horse_name')}) missing field '{field}'"

        assert c.get("sp_recovery_version") == "VFU_14_SP_DATA_RECOVERY_V1", \
            f"Case {i} has wrong sp_recovery_version"

        pb = c.get("price_band")
        assert pb in VALID_PRICE_BANDS, f"Case {i} has invalid price_band: {pb}"

        al = c.get("price_attribution_status")
        assert al in VALID_ATTRIBUTION_LABELS, \
            f"Case {i} ({c.get('horse_name')}) has invalid attribution: {al}"

        src = c.get("pick_sp_source")
        if c.get("pick_sp") is not None:
            assert src in VALID_SP_SOURCES, f"Case {i} has invalid pick_sp_source: {src}"


# ── Test 06: PLACED cases labelled PLACE_SIGNAL_NOT_WIN_SIGNAL ────────────────

def test_06_placed_cases_labelled_place_signal():
    """All PLACED cases (is_placed_not_won=True) must be PLACE_SIGNAL_NOT_WIN_SIGNAL."""
    cases = load_enriched()
    placed = [c for c in cases if c.get("is_placed_not_won")]
    assert len(placed) > 0, "Expected at least one PLACED case"

    for c in placed:
        att = c.get("price_attribution_status")
        assert att == "PLACE_SIGNAL_NOT_WIN_SIGNAL", (
            f"PLACED case {c.get('horse_name')} has wrong attribution: {att}"
        )
        assert not c.get("is_miss"), f"Placed case {c.get('horse_name')} must not be is_miss"


# ── Test 07: Unmatched cases have explicit missing reasons ────────────────────

def test_07_unmatched_cases_have_missing_reasons():
    """Every unmatched case must have a valid pick_sp_missing_reason."""
    unmatched = load_unmatched()
    assert len(unmatched) > 0, "Expected some unmatched cases"

    for i, c in enumerate(unmatched):
        assert c.get("pick_sp") is None, \
            f"Unmatched case {i} has pick_sp={c.get('pick_sp')} — should be None"
        reason = c.get("pick_sp_missing_reason")
        assert reason in VALID_MISSING_REASONS, (
            f"Unmatched case {i} ({c.get('horse_name')}) has invalid reason: {reason}"
        )
        assert c.get("price_band") == "UNKNOWN", \
            f"Unmatched case {i} price_band should be UNKNOWN, got {c.get('price_band')}"


# ── Test 08: No ambiguous SP guessing ─────────────────────────────────────────

def test_08_no_ambiguous_guessing():
    """Script must not guess. If ambiguous: pick_sp_ambiguous=True + explicit source."""
    cases = load_enriched()
    for i, c in enumerate(cases):
        if c.get("pick_sp_ambiguous"):
            assert c.get("pick_sp_source") is not None, \
                f"Ambiguous case {i} must still have a declared pick_sp_source"
            assert c.get("pick_sp") is not None, \
                f"Ambiguous case {i} must still declare pick_sp (highest-priority source)"

    # Summary must report ambiguous count
    summary = load_summary()
    assert "ambiguous" in summary.get("stats", {}), "Summary must report ambiguous count"


# ── Test 09: Price band assignment is correct ─────────────────────────────────

def test_09_price_band_assignment_correct():
    """Price band must match SP value for all cases with a pick_sp."""
    cases = load_enriched()
    band_map = [
        ("ODDS_ON", 0.0, 2.0),
        ("SHORT",   2.0, 4.0),
        ("MID_PRICE", 4.0, 6.0),
        ("DANGER",  6.0, 10.0),
        ("LONGSHOT", 10.0, float("inf")),
    ]
    for i, c in enumerate(cases):
        sp = c.get("pick_sp")
        pb = c.get("price_band")
        if sp is None:
            assert pb == "UNKNOWN", f"Case {i}: sp=None but price_band={pb}"
            continue
        expected = next(
            (name for name, lo, hi in band_map if lo <= sp < hi), None
        )
        assert expected is not None, f"Case {i}: SP={sp} does not map to any band"
        assert pb == expected, (
            f"Case {i} ({c.get('horse_name')}): SP={sp} → expected band {expected}, got {pb}"
        )


# ── Test 10: VP threshold unchanged ───────────────────────────────────────────

def test_10_vp_threshold_unchanged():
    """VP_THRESHOLD must be 0.40 in script and summary."""
    from scripts.ops.vfu_sp_data_recovery import VP_THRESHOLD as VPT
    assert VPT == 0.40

    summary = load_summary()
    assert summary.get("vp_threshold") == 0.40
    assert summary.get("vp_threshold_unchanged") is True
    assert "NO_VP_THRESHOLD_CHANGE" in summary.get("final_classifications", [])


# ── Test 11: No Supabase writes in script ─────────────────────────────────────

def test_11_no_supabase_writes_in_script():
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


# ── Test 12: No Passport mutation in script ────────────────────────────────────

def test_12_no_passport_mutation():
    """Script must not mutate canonical Horse Passport (no parquet writes)."""
    code = SCRIPT.read_text(encoding="utf-8")
    parquet_writes = [
        ln for ln in code.splitlines()
        if "to_parquet" in ln and not ln.strip().startswith("#")
    ]
    assert not parquet_writes, f"Script must not write parquet: {parquet_writes}"

    summary = load_summary()
    assert summary.get("canonical_passport_mutated") is False
    assert "CANONICAL_HORSE_PASSPORT_NOT_MUTATED" in summary.get("final_classifications", [])


# ── Test 13: MISS and PLACED cases separated ──────────────────────────────────

def test_13_miss_and_placed_cases_separated():
    """MISS and PLACED must be mutually exclusive, sum to total non-WIN cases."""
    cases = load_enriched()
    miss_cases   = [c for c in cases if c.get("is_miss")]
    placed_cases = [c for c in cases if c.get("is_placed_not_won")]

    assert len(miss_cases) > 0,   "Expected MISS cases"
    assert len(placed_cases) > 0, "Expected PLACED cases"

    # Mutually exclusive
    overlap = [c for c in cases if c.get("is_miss") and c.get("is_placed_not_won")]
    assert not overlap, f"{len(overlap)} cases flagged as both MISS and PLACED"

    # Total must be 121 (all FG cases)
    assert len(cases) == 121

    summary = load_summary()
    assert "MISS_AND_PLACED_CASES_SEPARATED" in summary.get("final_classifications", [])
    assert "PLACE_SIGNAL_NOT_WIN_SIGNAL_DECLARED" in summary.get("final_classifications", [])


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

    # Summary MD must mention key content
    md = SUMMARY_MD.read_text(encoding="utf-8")
    assert "VFU-14" in md
    assert "0.40" in md
    assert "DRY RUN" in md or "dry_run" in md.lower()

    # Summary must have all hard safety flags
    assert summary.get("canonical_passport_mutated") is False
    assert summary.get("supabase_written") is False
    assert summary.get("live_scoring_changed") is False
    assert summary.get("model_promoted") is False
    assert summary.get("telegram_sent") is False
    assert summary.get("mar_apr_quarantine_only") is True
    assert summary.get("blocked_from_live_use") is True
    assert summary.get("human_approval_required") is True
    assert summary.get("dry_run_only") is True
