"""
tests/test_vfu_doctrine.py
===========================
Guardrail tests for VFU-01 Phase 1 doctrine and schema.
Documentation validation only — no runtime autopsy execution.
"""

import os
import json
import pytest

DOCS = "docs/current"
REPORTS = "data/reports"

VFU_DOCTRINE = f"{DOCS}/VELO_FORENSICS_UNIT_V1.md"
AUTOPSY_SCHEMA = f"{DOCS}/VFU_RACE_AUTOPSY_SCHEMA_V1.md"
PASSPORT_EXT = f"{DOCS}/HORSE_PASSPORT_FORENSIC_EXTENSION_V1.md"
PP_SCHEMA = f"{DOCS}/PATTERN_PROSECUTOR_SCHEMA_V1.md"
TAXONOMY = f"{DOCS}/VFU_FAILURE_TAXONOMY_V1.md"
BUILD_PLAN_JSON = f"{REPORTS}/vfu_01_build_plan.json"
BUILD_PLAN_MD = f"{REPORTS}/vfu_01_build_plan.md"


# ─── 1. All doctrine files exist ─────────────────────────────────────────────

def test_vfu_doctrine_exists():
    assert os.path.exists(VFU_DOCTRINE), f"VFU doctrine missing: {VFU_DOCTRINE}"

def test_autopsy_schema_exists():
    assert os.path.exists(AUTOPSY_SCHEMA), f"Autopsy schema missing: {AUTOPSY_SCHEMA}"

def test_passport_extension_exists():
    assert os.path.exists(PASSPORT_EXT), f"Passport extension schema missing: {PASSPORT_EXT}"

def test_pattern_prosecutor_schema_exists():
    assert os.path.exists(PP_SCHEMA), f"Pattern Prosecutor schema missing: {PP_SCHEMA}"

def test_failure_taxonomy_exists():
    assert os.path.exists(TAXONOMY), f"Failure taxonomy missing: {TAXONOMY}"

def test_build_plan_json_exists():
    assert os.path.exists(BUILD_PLAN_JSON), f"Build plan JSON missing: {BUILD_PLAN_JSON}"


# ─── 2. Doctrine contains mandatory sentence ──────────────────────────────────

def test_vfu_doctrine_contains_core_sentence():
    text = open(VFU_DOCTRINE, encoding="utf-8").read()
    assert "Sigma learns patterns" in text, "VFU doctrine missing core sentence"
    assert "Horse Passport remembers the living horse" in text, "VFU doctrine missing core sentence"


# ─── 3. Doctrine confirms no scoring change ───────────────────────────────────

def test_vfu_doctrine_no_scoring_change():
    text = open(VFU_DOCTRINE, encoding="utf-8").read()
    assert "No live scoring" in text or "no scoring changes" in text.lower(), \
        "VFU doctrine must state no live scoring changes"


# ─── 4. Doctrine confirms no Supabase writes ─────────────────────────────────

def test_vfu_doctrine_no_supabase_writes():
    text = open(VFU_DOCTRINE, encoding="utf-8").read()
    assert "No Supabase writes" in text or "no supabase writes" in text.lower(), \
        "VFU doctrine must state no Supabase writes"


# ─── 5. Horse Passport confirmed as canonical ────────────────────────────────

def test_vfu_doctrine_passport_canonical():
    text = open(VFU_DOCTRINE, encoding="utf-8").read()
    assert "canonical" in text.lower(), "VFU doctrine must confirm Horse Passport as canonical"
    assert "does not replace" in text.lower() or "not replace" in text.lower(), \
        "VFU doctrine must state VFU does not replace Passport"


# ─── 6. Autopsy schema contains required fields ──────────────────────────────

def test_autopsy_schema_required_fields():
    text = open(AUTOPSY_SCHEMA, encoding="utf-8").read()
    required = [
        "race_id", "race_date", "course", "vp_score", "vp_gate_label",
        "actual_winner", "predicted_outcome", "miss_classification",
        "passport_update_candidate", "pattern_update_candidate",
        "human_review_required", "failure_class", "source_quality"
    ]
    missing = [f for f in required if f not in text]
    assert len(missing) == 0, f"Autopsy schema missing fields: {missing}"


# ─── 7. Passport extension contains current-state labels ─────────────────────

def test_passport_extension_current_state_labels():
    text = open(PASSPORT_EXT, encoding="utf-8").read()
    required_labels = [
        "IMPROVING", "DECLINING", "EXPOSED", "HIDDEN",
        "SETUP_DEPENDENT", "READY_NEXT_TIME", "TRAP_LEAD_CANDIDATE"
    ]
    missing = [l for l in required_labels if l not in text]
    assert len(missing) == 0, f"Passport extension missing current-state labels: {missing}"


# ─── 8. Failure taxonomy contains all 22 required classes ────────────────────

def test_failure_taxonomy_required_classes():
    text = open(TAXONOMY, encoding="utf-8").read()
    required = [
        "VP_FALSE_POSITIVE", "VP_FALSE_NEGATIVE",
        "COURSE_DRAIN_CONFIRMED", "COURSE_STRENGTH_CONFIRMED",
        "SP_DEAD_ZONE_FAILURE", "MID_PRICE_WALL",
        "WINNER_OUTSIDE_FRAME", "WINNER_INSIDE_FRAME_BUT_WRONG_TOP_PICK",
        "LONGSHOT_RELEASE_MISSED", "FAVOURITE_TRAP",
        "INTENT_OVERRIDE_MISSED", "TRAP_LEAD_PATTERN_MISSED",
        "SETUP_MISREAD", "TRIP_SURFACE_MISMATCH", "PACE_SETUP_WRONG",
        "MARKET_SIGNAL_IGNORED", "HORSE_PROFILE_OUTDATED",
        "REPEAT_HORSE_MEMORY_MISSED", "DATA_MISSING",
        "SOURCE_DEGRADED", "HORSE_IDENTITY_MISMATCH",
        "RESULT_RECONCILIATION_ERROR"
    ]
    missing = [c for c in required if c not in text]
    assert len(missing) == 0, f"Failure taxonomy missing classes: {missing}"


# ─── 9. Build plan JSON structure valid ──────────────────────────────────────

def test_build_plan_json_valid():
    with open(BUILD_PLAN_JSON, encoding="utf-8") as f:
        plan = json.load(f)
    assert plan["status"] == "PHASE_1_COMPLETE"
    assert "phases" in plan
    assert plan["phases"]["phase_1"]["status"] == "COMPLETE"
    assert plan["phases"]["phase_2"]["status"] == "LOCKED"
    assert plan["canonical_passport_path"] != ""


# ─── 10. Build plan confirms guardrails ──────────────────────────────────────

def test_build_plan_guardrails():
    with open(BUILD_PLAN_JSON, encoding="utf-8") as f:
        plan = json.load(f)
    guardrails = plan["phases"]["phase_1"]["guardrails_confirmed"]
    assert guardrails["no_autopsy_execution"] is True
    assert guardrails["no_supabase_writes"] is True
    assert guardrails["no_live_scoring_change"] is True
    assert guardrails["horse_passport_canonical"] is True
    assert guardrails["no_duplicate_dossier_system"] is True


# ─── 11. No VFU autopsy execution script exists yet ──────────────────────────

def test_no_autopsy_execution_script():
    autopsy_scripts = [
        "scripts/ops/run_vfu_autopsy.py",
        "scripts/ops/execute_race_autopsy.py",
        "scripts/ops/vfu_autopsy_runner.py"
    ]
    for s in autopsy_scripts:
        assert not os.path.exists(s), \
            f"Autopsy execution script found in Phase 1: {s} — must not exist yet"


# ─── 12. Final classifications in build plan ─────────────────────────────────

def test_build_plan_final_classifications():
    with open(BUILD_PLAN_JSON, encoding="utf-8") as f:
        plan = json.load(f)
    classifications = plan["final_classifications"]
    required = [
        "VFU_01_DOCTRINE_CREATED",
        "HORSE_PASSPORT_CONFIRMED_AS_CANONICAL_DOSSIER",
        "VFU_DEFINED_AS_INVESTIGATIVE_FEEDER",
        "NO_AUTOPSY_EXECUTION_YET",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES"
    ]
    missing = [c for c in required if c not in classifications]
    assert len(missing) == 0, f"Missing final classifications: {missing}"
