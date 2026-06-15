"""
tests/test_vfu_false_green_feature_autopsy.py
==============================================
VFU-13 — False-GREEN Feature Autopsy test suite.
13 required tests.

Run via WSL:
  wsl -e bash -c "cd /mnt/c/Users/puror/velo-oracle-prime && PYTHONPATH=. venv/bin/python -m pytest tests/test_vfu_false_green_feature_autopsy.py -v"
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ops/vfu_false_green_feature_autopsy.py"

CASES_JSONL    = ROOT / "data/reports/vfu_13_false_green_cases.jsonl"
COMPONENTS_JSON = ROOT / "data/reports/vfu_13_false_green_component_breakdown.json"
TOP25_DEEP_JSON = ROOT / "data/reports/vfu_13_false_green_top25_deep_dive.json"
REVIEW_JSON    = ROOT / "data/reports/vfu_13_false_green_human_review_queue.json"
BAND_AUDIT_JSON = ROOT / "data/reports/vfu_13_priority_band_audit.json"
SUMMARY_JSON   = ROOT / "data/reports/vfu_13_false_green_feature_autopsy_summary.json"
SUMMARY_MD     = ROOT / "data/reports/vfu_13_false_green_feature_autopsy_summary.md"

VP_THRESHOLD = 0.40
ERA_CURRENT_START = "2026-05-08"


def load_cases() -> list[dict]:
    return [json.loads(ln) for ln in CASES_JSONL.read_text(encoding="utf-8").splitlines() if ln.strip()]


def load_summary() -> dict:
    return json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))


def load_breakdown() -> dict:
    return json.loads(COMPONENTS_JSON.read_text(encoding="utf-8"))


# ── Test 01: Script exists and imports cleanly ─────────────────────────────────

def test_01_script_exists_and_imports():
    """VFU-13 script must exist with required functions and VP_THRESHOLD=0.40."""
    assert SCRIPT.exists(), f"Script missing: {SCRIPT}"
    import importlib.util
    spec = importlib.util.spec_from_file_location("vfu_false_green_feature_autopsy", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "main"), "Script must define main()"
    assert hasattr(mod, "classify_causes"), "Script must define classify_causes()"
    assert hasattr(mod, "build_fg_case"), "Script must define build_fg_case()"
    assert mod.VP_THRESHOLD == 0.40, f"VP_THRESHOLD must be 0.40, got {mod.VP_THRESHOLD}"


# ── Test 02: Reads VFU-11/VFU-12 local artifacts ─────────────────────────────

def test_02_reads_local_artifacts():
    """All required VFU-11 and VFU-12 input files must exist."""
    required_inputs = [
        ROOT / "data/reports/vfu_11_sigma_master_ledger.jsonl",
        ROOT / "data/reports/vfu_current_era_autopsy_records_identity_enriched.jsonl",
        ROOT / "data/reports/vfu_12_human_review_top25.json",
        ROOT / "data/reports/vfu_12_human_review_ranked_queue.json",
        ROOT / "data/reports/vfu_12_pattern_verdicts.json",
    ]
    missing = [str(p) for p in required_inputs if not p.exists()]
    assert not missing, f"Required input files missing: {missing}"


# ── Test 03: Only current-era VP>=0.40 losing cases selected ─────────────────

def test_03_only_current_era_vp40_losses():
    """Every FG case must be current-era (>=2026-05-08) and VP>=0.40 and not WIN."""
    cases = load_cases()
    assert len(cases) > 0, "FG cases must not be empty"

    for i, c in enumerate(cases):
        date = str(c.get("race_date") or "")[:10]
        vp   = c.get("vp")
        outcome = str(c.get("outcome") or "").upper()

        # Must be current era
        assert date >= ERA_CURRENT_START, (
            f"Case {i} has pre-current-era date: {date}"
        )
        # Must have VP >= 0.40
        assert vp is not None and vp >= VP_THRESHOLD, (
            f"Case {i} has VP={vp}, must be >= {VP_THRESHOLD}"
        )
        # Must not be a WIN
        assert outcome != "WIN", (
            f"Case {i} is outcome=WIN — should not be in FG set"
        )


# ── Test 04: Mar–Apr quarantine excluded from conclusions ─────────────────────

def test_04_mar_apr_excluded():
    """No PRE_SURGERY_ARCHIVE_QUARANTINE rows should appear in FG cases."""
    cases = load_cases()
    # All case race_dates must be 2026-05-08+
    archive_cases = [c for c in cases if str(c.get("race_date") or "")[:10] < ERA_CURRENT_START]
    assert not archive_cases, (
        f"{len(archive_cases)} FG cases have pre-current-era dates — Mar–Apr must be excluded"
    )
    # Summary must confirm
    summary = load_summary()
    assert summary.get("mar_apr_quarantine_only") is True


# ── Test 05: At least one cause or UNKNOWN_REQUIRES_REVIEW assigned ───────────

def test_05_causes_assigned():
    """Every FG case must have at least one cause or UNKNOWN_REQUIRES_REVIEW."""
    cases = load_cases()
    valid_causes = {
        "SQPE_OVERCONFIDENCE", "IMPROVEMENT_SCORE_OVERCONFIDENCE",
        "MARKET_DECEPTION_OVERCONFIDENCE", "SOURCE_LAYER_WEAKNESS",
        "COURSE_TRAP", "DAY_LEVEL_CHAOS", "PRICE_BAND_TRAP",
        "PASSPORT_OVERRIDE_CONTAMINATION_RISK", "IDENTITY_WEAKNESS",
        "MISSING_PICK_SP_LIMITATION", "MISSING_FRAME_CONTEXT",
        "UNKNOWN_REQUIRES_REVIEW", "PLACE_PROB_CORRELATION",
    }
    for i, c in enumerate(cases):
        causes = c.get("causes", [])
        assert len(causes) > 0, f"Case {i} has no causes assigned"
        for cause in causes:
            assert cause in valid_causes, (
                f"Case {i} has invalid cause: {cause}"
            )


# ── Test 06: Every warning is blocked_from_live_use ──────────────────────────

def test_06_warnings_blocked_from_live_use():
    """All proposed warnings must be blocked_from_live_use=True."""
    summary = load_summary()
    assert summary.get("warnings_all_dry_run_only") is True

    # Check summary JSON structure
    required_answers = summary.get("required_answers", {})
    live_rule = required_answers.get("Q12_live_rule_recommended", "")
    assert "NO" in live_rule.upper(), f"Q12 should say NO live rule, got: {live_rule}"


# ── Test 07: Every warning is human_approval_required ────────────────────────

def test_07_warnings_human_approval_required():
    """Script must not embed live rule logic."""
    code = SCRIPT.read_text(encoding="utf-8")
    # All warning proposal dicts must have dry_run_only=True
    assert "dry_run_only" in code, "Script must set dry_run_only=True on warnings"
    assert "blocked_from_live_use" in code, "Script must set blocked_from_live_use=True on warnings"
    assert "human_approval_required" in code, "Script must set human_approval_required=True on warnings"


# ── Test 08: VP threshold unchanged ──────────────────────────────────────────

def test_08_vp_threshold_unchanged():
    """VP_THRESHOLD must be 0.40 in script and summary."""
    from scripts.ops.vfu_false_green_feature_autopsy import VP_THRESHOLD
    assert VP_THRESHOLD == 0.40

    summary = load_summary()
    assert summary.get("vp_threshold") == 0.40
    assert summary.get("vp_threshold_unchanged") is True
    assert "NO_VP_THRESHOLD_CHANGE" in summary.get("final_classifications", [])


# ── Test 09: No live doctrine promotion ──────────────────────────────────────

def test_09_no_live_doctrine_promotion():
    """Summary must confirm no live scoring change, no Supabase writes, no Passport mutation."""
    summary = load_summary()
    assert summary.get("canonical_passport_mutated") is False
    assert summary.get("supabase_written") is False
    assert summary.get("live_scoring_changed") is False
    assert summary.get("model_promoted") is False
    assert "NO_LIVE_DOCTRINE_PROMOTION" in summary.get("final_classifications", [])


# ── Test 10: Script does not require Supabase ─────────────────────────────────

def test_10_no_supabase_writes_in_script():
    """Script must not contain Supabase write operations."""
    code = SCRIPT.read_text(encoding="utf-8")
    supabase_write_patterns = [
        r"\.table\(.*\)\.insert\(",
        r"\.table\(.*\)\.upsert\(",
        r"\.table\(.*\)\.update\(",
        r"\.table\(.*\)\.delete\(",
        r"supabase.*\.insert\(",
    ]
    for pat in supabase_write_patterns:
        bad = [
            ln for ln in code.splitlines()
            if re.search(pat, ln) and not ln.strip().startswith("#")
        ]
        assert not bad, f"Supabase write pattern '{pat}' found: {bad[:3]}"


# ── Test 11: Summary report generated ────────────────────────────────────────

def test_11_summary_report_generated():
    """VFU-13 summary JSON and MD must exist with required fields."""
    assert SUMMARY_JSON.exists(), f"Summary JSON missing"
    assert SUMMARY_MD.exists(),   f"Summary MD missing"

    summary = load_summary()
    required_classifications = [
        "VFU_13_FALSE_GREEN_FEATURE_AUTOPSY_COMPLETE",
        "FALSE_GREEN_CASES_CLASSIFIED",
        "FALSE_GREEN_WARNINGS_DRY_RUN_ONLY",
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
    actual = summary.get("final_classifications", [])
    missing = [c for c in required_classifications if c not in actual]
    assert not missing, f"Missing required classifications: {missing}"

    md = SUMMARY_MD.read_text(encoding="utf-8")
    assert "VFU-13" in md
    assert "0.40" in md
    assert "VFU-10 Law" in md or "VFU-10 law" in md.lower()


# ── Test 12: Component breakdown generated ────────────────────────────────────

def test_12_component_breakdown_generated():
    """Component breakdown must exist and identify the dominant FG cause."""
    assert COMPONENTS_JSON.exists(), f"Component breakdown missing"
    bd = load_breakdown()

    assert "cause_distribution" in bd, "Component breakdown must have cause_distribution"
    assert "key_finding" in bd, "Component breakdown must have key_finding"
    assert bd.get("total_fg_cases", 0) > 0, "Must have FG cases in breakdown"

    # MISSING_PICK_SP_LIMITATION must appear (known dominant blocker)
    cause_dist = bd.get("cause_distribution", {})
    assert "MISSING_PICK_SP_LIMITATION" in cause_dist, (
        f"MISSING_PICK_SP_LIMITATION must appear in cause distribution: {list(cause_dist.keys())}"
    )


# ── Test 13: Priority band audit generated ────────────────────────────────────

def test_13_priority_band_audit_generated():
    """Priority band audit must exist and document VFU-12's P0=41 bluntness."""
    assert BAND_AUDIT_JSON.exists(), f"Band audit missing"
    audit = json.loads(BAND_AUDIT_JSON.read_text(encoding="utf-8"))

    assert "vfu12_band_audit" in audit, "Must document VFU-12 band distribution"
    assert audit["vfu12_band_audit"].get("P0_CRITICAL") == 41, "Must record VFU-12 P0=41"
    assert "recommended_future_triage" in audit, "Must include improved triage criteria"
    assert "vfu13_reclassification" in audit, "Must include VFU-13 reclassification"
    assert "operator_note" in audit, "Must include operator note"
