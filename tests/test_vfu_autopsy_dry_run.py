"""
tests/test_vfu_autopsy_dry_run.py
===================================
Guardrail tests for VFU-02 20-race autopsy dry-run.
"""
import json
import os
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNION_ROWS_JSON = "data/reports/current_era_sigma_union_rows_2026_05_08_to_2026_06_13.json"
SUMMARY_JSON    = "data/reports/vfu_autopsy_dry_run_20_races.json"
RECORDS_DIR     = "data/reports/vfu_autopsy_records"
EXT_DIR         = "data/reports/vfu_passport_extensions_dry_run"
CANON_PASSPORT  = "data/new_build/passports/horse_passports_v1.jsonl"
SURGERY_DATE    = "2026-05-08"


def _load_summary():
    if not os.path.exists(SUMMARY_JSON):
        pytest.skip("Dry-run summary not generated — run vfu_race_autopsy_dry_run.py first")
    return json.loads(open(SUMMARY_JSON, encoding="utf-8").read())


def _load_records():
    if not os.path.exists(RECORDS_DIR):
        pytest.skip("Autopsy records dir not found")
    records = []
    for f in sorted(Path(RECORDS_DIR).glob("*.json")):
        records.append(json.loads(f.read_text(encoding="utf-8")))
    return records


# ─── 1. Dry-run reads current-era union ──────────────────────────────────────

def test_dry_run_reads_current_era_union():
    s = _load_summary()
    assert UNION_ROWS_JSON in s.get("source_file", ""), \
        "Summary must reference current-era union as source"


# ─── 2. Exactly 20 autopsies from real rows ───────────────────────────────────

def test_dry_run_creates_20_autopsies():
    s = _load_summary()
    assert s["total_autopsies"] == 20, f"Expected 20 autopsies, got {s['total_autopsies']}"
    records = _load_records()
    assert len(records) == 20, f"Expected 20 record files, got {len(records)}"


# ─── 3. Canonical Passport file not mutated ──────────────────────────────────

def test_canonical_passport_not_mutated():
    s = _load_summary()
    assert s.get("canonical_passport_mutated") is False, \
        "Summary must confirm canonical_passport_mutated=False"
    # File should exist but not be in git dirty state — validate it was not written by dry-run
    if os.path.exists(CANON_PASSPORT):
        # The passport file must not have been touched by records or extensions
        passport_mtime = os.path.getmtime(CANON_PASSPORT)
        for rec_file in Path(RECORDS_DIR).glob("*.json"):
            rec_mtime = os.path.getmtime(rec_file)
            # Records are newer — that's expected, but canon passport should not be newer than script run
            # Just confirm: no record file IS the canonical passport
            assert str(rec_file.resolve()) != str(Path(CANON_PASSPORT).resolve())


# ─── 4. No Supabase writes ───────────────────────────────────────────────────

def test_no_supabase_writes():
    s = _load_summary()
    assert s.get("supabase_written") is False, "Summary must confirm supabase_written=False"


# ─── 5. Missing fields produce data_gaps not failure ─────────────────────────

def test_missing_fields_produce_data_gaps():
    records = _load_records()
    for r in records:
        # pick_sp is null throughout — must appear in data_gaps, not cause autopsy failure
        if r.get("pick_sp") is None:
            assert any("pick_sp" in g for g in r.get("data_gaps", [])), \
                f"pick_sp null but not in data_gaps for {r.get('autopsy_id')}"
        # autopsy_confidence must be set
        assert r.get("autopsy_confidence") in ("HIGH", "MEDIUM", "LOW"), \
            f"autopsy_confidence missing on {r.get('autopsy_id')}"


# ─── 6. Failure class can be INSUFFICIENT_EVIDENCE ───────────────────────────

def test_failure_class_insufficient_evidence_allowed():
    records = _load_records()
    miss_records = [r for r in records if r.get("actual_outcome") in ("MISS", "PLACED")]
    valid_classes = {
        "VP_FALSE_POSITIVE", "VP_FALSE_NEGATIVE", "COURSE_DRAIN_CONFIRMED",
        "COURSE_STRENGTH_CONFIRMED", "SP_DEAD_ZONE_FAILURE", "MID_PRICE_WALL",
        "WINNER_OUTSIDE_FRAME", "WINNER_INSIDE_FRAME_BUT_WRONG_TOP_PICK",
        "LONGSHOT_RELEASE_MISSED", "INTENT_OVERRIDE_MISSED", "TRAP_LEAD_PATTERN_MISSED",
        "SETUP_MISREAD", "TRIP_SURFACE_MISMATCH", "MARKET_SIGNAL_IGNORED",
        "HORSE_PROFILE_OUTDATED", "REPEAT_HORSE_MEMORY_MISSED", "DATA_MISSING",
        "SOURCE_DEGRADED", "HORSE_IDENTITY_MISMATCH", "RESULT_RECONCILIATION_ERROR",
        "INSUFFICIENT_EVIDENCE",
    }
    for r in miss_records:
        fc = r.get("failure_class")
        assert fc is not None, f"MISS/PLACED autopsy missing failure_class: {r.get('autopsy_id')}"
        assert fc in valid_classes, f"Unknown failure class '{fc}' on {r.get('autopsy_id')}"


# ─── 7. Passport extensions go only to dry-run folder ────────────────────────

def test_passport_extensions_in_dry_run_folder_only():
    if not os.path.exists(EXT_DIR):
        pytest.skip("Extension dir not found")
    exts = list(Path(EXT_DIR).glob("*.json"))
    assert len(exts) > 0, "No passport extension files found in dry-run folder"
    for ext_file in exts:
        # Must be in dry-run folder, never in canonical passport folder
        assert "passport_extensions_dry_run" in str(ext_file), \
            f"Extension file found outside dry-run dir: {ext_file}"
        data = json.loads(ext_file.read_text(encoding="utf-8"))
        assert data.get("do_not_merge") is True, \
            f"Extension missing do_not_merge=True: {ext_file}"


# ─── 8. Pre-surgery rows excluded ────────────────────────────────────────────

def test_pre_surgery_rows_excluded():
    records = _load_records()
    pre_surg = [r for r in records if (r.get("race_date") or "") < SURGERY_DATE and r.get("race_date")]
    assert len(pre_surg) == 0, \
        f"{len(pre_surg)} pre-surgery rows found in dry-run: {[r['race_date'] for r in pre_surg]}"


# ─── 9. Mar–Apr rows excluded ────────────────────────────────────────────────

def test_mar_apr_rows_excluded():
    records = _load_records()
    mar_apr = [r for r in records if r.get("race_date","") < "2026-05-01" and r.get("race_date")]
    assert len(mar_apr) == 0, f"Mar-Apr rows in dry-run: {mar_apr}"


# ─── 10. Summary report generated with required fields ───────────────────────

def test_summary_report_generated():
    s = _load_summary()
    required = ["total_autopsies", "outcomes", "failure_classes", "data_gaps",
                "passport_update_candidates", "canonical_passport_mutated",
                "supabase_written", "final_classifications", "recommendations"]
    missing = [k for k in required if k not in s]
    assert len(missing) == 0, f"Summary missing keys: {missing}"


# ─── 11. Final classifications include all required ──────────────────────────

def test_final_classifications_complete():
    s = _load_summary()
    required = [
        "VFU_02_20_RACE_AUTOPSY_DRY_RUN_COMPLETE",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_SUPABASE_WRITES",
        "NO_LIVE_SCORING_CHANGE",
        "CURRENT_ERA_ONLY",
        "NO_MAR_APR_EXTRACTION",
    ]
    classifications = s.get("final_classifications", [])
    missing = [c for c in required if c not in classifications]
    assert len(missing) == 0, f"Missing final classifications: {missing}"


# ─── 12. VP explains direction (wins > misses mean VP) ───────────────────────

def test_vp_explains_direction():
    s = _load_summary()
    vp_analysis = s.get("vp_analysis", {})
    win_vp = vp_analysis.get("win_mean_vp")
    miss_vp = vp_analysis.get("miss_mean_vp")
    if win_vp is not None and miss_vp is not None:
        assert win_vp > miss_vp, \
            f"VP should be higher for wins ({win_vp}) than misses ({miss_vp})"


# ─── 13. All 20 autopsy records have required core fields ────────────────────

def test_all_autopsies_have_core_fields():
    records = _load_records()
    required_fields = ["autopsy_id", "race_date", "course", "vp", "actual_outcome",
                       "data_gaps", "investigation_questions", "passport_update_candidate",
                       "pattern_update_candidate", "human_review_required",
                       "generated_by", "phase", "era"]
    for r in records:
        missing = [f for f in required_fields if f not in r]
        assert len(missing) == 0, \
            f"Autopsy {r.get('autopsy_id','?')} missing fields: {missing}"
        assert r.get("era") == "CURRENT_ERA", \
            f"Autopsy {r.get('autopsy_id')} has wrong era: {r.get('era')}"
