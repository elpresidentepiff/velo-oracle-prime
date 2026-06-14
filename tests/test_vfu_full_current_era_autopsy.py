"""
tests/test_vfu_full_current_era_autopsy.py
============================================
VFU-04 — Tests for the full current-era autopsy pass with quality tiers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_full_current_era_autopsy import assign_tier

ENRICHED_UNION   = ROOT / "data/reports/current_era_sigma_union_rows_enriched_vfu_v1.json"
RECORDS_FILE     = ROOT / "data/reports/vfu_full_current_era_autopsy_records.jsonl"
PASSPORTS_FILE   = ROOT / "data/reports/vfu_full_current_era_passport_candidates.jsonl"
PATTERNS_FILE    = ROOT / "data/reports/vfu_full_current_era_pattern_evidence.jsonl"
GAPS_FILE        = ROOT / "data/reports/vfu_full_current_era_quality_gaps.json"
SUMMARY_JSON     = ROOT / "data/reports/vfu_full_current_era_autopsy_summary.json"
CANON_PASSPORT   = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ── 1. Full pass reads enriched current-era union ────────────────────────────

def test_full_pass_reads_enriched_union():
    assert ENRICHED_UNION.exists(), "Enriched union file must exist before VFU-04 runs"
    rows = json.loads(ENRICHED_UNION.read_text())
    assert len(rows) == 1263, f"Expected 1263 rows, got {len(rows)}"


# ── 2. Output row count does not exceed input row count ──────────────────────

def test_output_row_count_not_exceed_input():
    if not RECORDS_FILE.exists():
        pytest.skip("VFU-04 records not yet generated — run vfu_full_current_era_autopsy.py first")
    records = _load_jsonl(RECORDS_FILE)
    assert len(records) <= 1263, f"Output has {len(records)} rows, exceeds input of 1263"
    assert len(records) >= 900, f"Expected at least 900 autopsy records (TIER_E would exclude some)"


# ── 3. Evidence quality tiers are assigned ───────────────────────────────────

def test_evidence_quality_tiers_assigned():
    if not RECORDS_FILE.exists():
        pytest.skip("VFU-04 records not yet generated")
    records = _load_jsonl(RECORDS_FILE)
    valid_tiers = {
        "TIER_A_FULL", "TIER_B_GOOD_NO_PICK_SP", "TIER_C_LIMITED_IDENTITY",
        "TIER_D_EVENT_ONLY", "TIER_E_UNUSABLE",
    }
    for r in records[:20]:
        tier = r.get("evidence_quality_tier")
        assert tier in valid_tiers, f"Invalid tier: {tier}"


def test_tier_assignment_logic():
    # TIER_A: has pick_sp + core fields
    row_a = {"race_date": "2026-05-21", "horse_name": "Test", "course": "Ascot",
              "outcome": "WIN", "vp": 0.45, "pick_sp": 5.0}
    assert assign_tier(row_a) == "TIER_A_FULL"

    # TIER_B: has actual_winner_sp but no pick_sp
    row_b = {"race_date": "2026-05-21", "horse_name": "Test", "course": "Ascot",
              "outcome": "MISS", "vp": 0.35, "pick_sp": None, "actual_winner_sp": 3.0}
    assert assign_tier(row_b) == "TIER_B_GOOD_NO_PICK_SP"

    # TIER_C: no pick_sp, no actual_winner_sp
    row_c = {"race_date": "2026-05-21", "horse_name": "Test", "course": "Ascot",
              "outcome": "MISS", "vp": 0.35, "pick_sp": None, "actual_winner_sp": None}
    assert assign_tier(row_c) == "TIER_C_LIMITED_IDENTITY"

    # TIER_D: no horse_name
    row_d = {"race_date": "2026-05-21", "horse_name": None, "course": "Ascot",
              "outcome": "MISS", "vp": 0.35}
    assert assign_tier(row_d) == "TIER_D_EVENT_ONLY"

    # TIER_E: no VP
    row_e = {"race_date": "2026-05-21", "horse_name": "Test", "course": "Ascot",
             "outcome": "WIN", "vp": None}
    assert assign_tier(row_e) == "TIER_E_UNUSABLE"


# ── 4. Rows without pick_sp are excluded from ROI ────────────────────────────

def test_rows_without_pick_sp_excluded_from_roi():
    if not RECORDS_FILE.exists():
        pytest.skip("VFU-04 records not yet generated")
    records = _load_jsonl(RECORDS_FILE)
    for r in records:
        if r.get("pick_sp") is None:
            assert r.get("excluded_from_roi") is True, (
                f"Row with no pick_sp must be excluded_from_roi=True: {r.get('autopsy_id')}"
            )


# ── 5. Rows without horse_name/date do not create Passport candidates ─────────

def test_no_passport_candidates_without_horse_identity():
    if not PASSPORTS_FILE.exists():
        pytest.skip("VFU-04 passport file not yet generated")
    passports = _load_jsonl(PASSPORTS_FILE)
    for pc in passports:
        assert pc.get("horse_name"), "Passport candidate must have horse_name"
        assert pc.get("race_date"), "Passport candidate must have race_date"


# ── 6. Passport candidates are dry-run only ───────────────────────────────────

def test_passport_candidates_dry_run_only():
    if not PASSPORTS_FILE.exists():
        pytest.skip("VFU-04 passport file not yet generated")
    passports = _load_jsonl(PASSPORTS_FILE)
    assert len(passports) > 0, "Expected at least some passport candidates"
    for pc in passports:
        assert pc.get("do_not_merge") is True, \
            f"Passport candidate must have do_not_merge=True: {pc.get('horse_name')}"
        assert pc.get("canonical_passport_mutated") is False, \
            "Passport candidate must confirm canonical_passport_mutated=False"
        assert pc.get("human_review_required") is True, \
            "All passport candidates require human review"


# ── 7. Canonical Horse Passport is not mutated ───────────────────────────────

def test_canonical_passport_not_mutated():
    # Output files must not overwrite the canonical passport
    assert str(RECORDS_FILE) != str(CANON_PASSPORT)
    assert str(PASSPORTS_FILE) != str(CANON_PASSPORT)

    if CANON_PASSPORT.exists():
        content = CANON_PASSPORT.read_text(encoding="utf-8")
        # Must contain passport-like content, not autopsy data
        assert "VFU_FULL_CURRENT_ERA_DRY_RUN" not in content, \
            "Canonical passport must not contain VFU dry-run provenance"


# ── 8. Pattern evidence JSONL is created ─────────────────────────────────────

def test_pattern_evidence_jsonl_created():
    if not PATTERNS_FILE.exists():
        pytest.skip("VFU-04 pattern file not yet generated")
    patterns = _load_jsonl(PATTERNS_FILE)
    assert len(patterns) > 0, "Expected pattern evidence records"
    required_fields = {"pattern_class", "outcome", "vp", "evidence_quality_tier", "excluded_from_roi"}
    for p in patterns[:5]:
        for fld in required_fields:
            assert fld in p, f"Pattern evidence missing field: {fld}"


# ── 9. Repeated horse tracker groups repeated names ──────────────────────────

def test_repeated_horse_tracker():
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-04 summary not yet generated")
    summary = json.loads(SUMMARY_JSON.read_text())
    repeated = summary.get("top_repeated_horses", [])
    assert summary.get("repeated_horses_found", 0) >= 0, "Repeated horse count must be non-negative"
    # Every tracker entry must have required fields
    required = {"horse_name", "appearance_count", "wins", "candidate_label"}
    for h in repeated[:5]:
        for fld in required:
            assert fld in h, f"Horse tracker missing field: {fld}"
    # All tracker entries have at least 2 appearances
    for h in repeated:
        assert h["appearance_count"] >= 2, \
            f"Tracker should only include horses with 2+ appearances: {h['horse_name']}"


# ── 10. Mar–Apr rows are excluded ────────────────────────────────────────────

def test_mar_apr_rows_excluded():
    if not RECORDS_FILE.exists():
        pytest.skip("VFU-04 records not yet generated")
    records = _load_jsonl(RECORDS_FILE)
    for r in records:
        date = r.get("race_date") or ""
        if date:
            assert date >= "2026-05-08", (
                f"Pre-surgery row found in autopsy output: {date} "
                f"— Mar/Apr rows must not be in current-era pass"
            )


# ── 11. Supabase is not required ─────────────────────────────────────────────

def test_script_has_no_supabase_dependency():
    script = ROOT / "scripts/ops/vfu_full_current_era_autopsy.py"
    assert script.exists()
    source = script.read_text(encoding="utf-8")
    code_lines = [l for l in source.splitlines() if not l.strip().startswith("#")]
    code = "\n".join(code_lines)
    assert "import supabase" not in code.lower()
    assert "SUPABASE_URL" not in code
    assert "create_client" not in code


# ── 12. Summary report is generated ─────────────────────────────────────────

def test_summary_report_generated():
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-04 summary not yet generated")
    summary = json.loads(SUMMARY_JSON.read_text())
    required_keys = {
        "total_rows_scanned", "autopsies_created", "tier_counts",
        "vp_threshold_table", "course_tier_table", "passport_candidates_created",
        "pattern_evidence_created", "repeated_horses_found",
        "vfu05_recommendation", "final_classifications",
        "canonical_passport_mutated", "supabase_written",
    }
    for k in required_keys:
        assert k in summary, f"Summary missing key: {k}"
    assert summary["canonical_passport_mutated"] is False
    assert summary["supabase_written"] is False
    assert summary["total_rows_scanned"] == 1263

    classifications = summary.get("final_classifications", [])
    assert "VFU_04_FULL_CURRENT_ERA_AUTOPSY_COMPLETE" in classifications
    assert "NO_SUPABASE_WRITES" in classifications
    assert "ROI_LIMITED_TO_PICK_SP_ROWS" in classifications
    assert "CANONICAL_HORSE_PASSPORT_NOT_MUTATED" in classifications


# ── 13. Quality gap report is generated ──────────────────────────────────────

def test_quality_gap_report_generated():
    if not GAPS_FILE.exists():
        pytest.skip("VFU-04 quality gaps not yet generated")
    gaps = json.loads(GAPS_FILE.read_text())
    assert "horse_id_null_all_rows" in gaps
    assert gaps["horse_id_null_all_rows"] is True, \
        "horse_id is null for all current-era rows — must be documented"
    assert "pick_sp_coverage_pct" in gaps
    assert "local_only_rows_no_identity" in gaps
    assert gaps["local_only_rows_no_identity"] == 294, \
        "Expected 294 LOCAL_ONLY rows with no identity"
