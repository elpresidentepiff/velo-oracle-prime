"""
tests/test_vfu_time_safe_passport_override_validation.py
==========================================================
VFU-10 — Time-Safe Passport Override Validation tests.

12 required tests:
  1.  Pre-era snapshot uses only dates before 2026-05-08
  2.  Does not use current-era contaminated Passport fields
  3.  Kakirra marked TEMPORAL_CONTAMINATION_UNRESOLVABLE
  4.  Man is King marked PARTIAL_CONTAMINATION
  5.  Group A VP<0.40 winner coverage counts present
  6.  Group C VP<0.40 non-winner comparison group present
  7.  Watchlist is dry-run only
  8.  Canonical Passport not mutated
  9.  No Supabase in script
  10. VP threshold unchanged at 0.40
  11. Mar–Apr not opened
  12. Summary report generated with required classifications
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_time_safe_passport_override_validation import (
    VALIDATION_VERSION,
    VP_THRESHOLD,
    ERA_START,
    KAKIRRA_ID,
    MAN_IS_KING_ID,
    norm_horse,
    classify_contamination,
    derive_time_safe_signals,
)

SUMMARY_JSON   = ROOT / "data/reports/vfu_time_safe_passport_override_validation.json"
REPORT_MD      = ROOT / "data/reports/vfu_time_safe_passport_override_validation.md"
CASES_JSONL    = ROOT / "data/reports/vfu_time_safe_passport_override_cases.jsonl"
UNCOVERED_JSON = ROOT / "data/reports/vfu_time_safe_passport_uncovered_cases.json"
WATCHLIST_JSON = ROOT / "data/reports/vfu_time_safe_passport_candidate_watchlist.json"
CANON_PASSPORT = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"
SCRIPT_FILE    = ROOT / "scripts/ops/vfu_time_safe_passport_override_validation.py"


def _load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


# ── 1. Pre-era snapshot uses only dates before ERA_START ──────────────────────

def test_era_start_constant_is_correct():
    """ERA_START must be 2026-05-08 — the current-era boundary."""
    assert ERA_START == "2026-05-08"


def test_summary_pre_era_snapshot_exists():
    """Summary must confirm pre-era snapshot was built."""
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-10 not yet generated")
    s = json.loads(SUMMARY_JSON.read_text())
    assert s["pre_era_snapshot_horses"] > 100_000, (
        "Pre-era snapshot must cover >100k horses from training data"
    )
    assert s["era_start"] == ERA_START


# ── 2. Does not use current-era contaminated fields ───────────────────────────

def test_no_current_era_passport_mutation():
    """Script must not write to canonical Passport or use current-era data."""
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-10 not yet generated")
    s = json.loads(SUMMARY_JSON.read_text())
    assert s["canonical_passport_mutated"] is False
    # Cases must not contain post-era run dates
    if CASES_JSONL.exists():
        cases = _load_jsonl(CASES_JSONL)
        for c in cases:
            snap = c.get("pre_era_snap") or {}
            last_date = snap.get("last_pre_era_date", "")
            if last_date:
                assert last_date < ERA_START, (
                    f"Snapshot date {last_date} is NOT before {ERA_START} for {c.get('horse_name')}"
                )


# ── 3. Kakirra marked TEMPORAL_CONTAMINATION_UNRESOLVABLE ────────────────────

def test_kakirra_temporal_contamination_unresolvable():
    """Kakirra has no pre-era data — must be TEMPORAL_CONTAMINATION_UNRESOLVABLE."""
    status = classify_contamination(KAKIRRA_ID, None)
    assert status == "TEMPORAL_CONTAMINATION_UNRESOLVABLE"


def test_kakirra_in_cases_correctly_classified():
    """Kakirra case record must carry the correct contamination status."""
    if not CASES_JSONL.exists():
        pytest.skip("VFU-10 not yet generated")
    cases = _load_jsonl(CASES_JSONL)
    kakirra = next(
        (c for c in cases if str(c.get("horse_id")) == KAKIRRA_ID), None
    )
    assert kakirra is not None, f"Kakirra (RP_UID {KAKIRRA_ID}) must appear in cases"
    assert kakirra["contamination_status"] == "TEMPORAL_CONTAMINATION_UNRESOLVABLE"
    assert kakirra["has_pre_era_snapshot"] is False
    assert kakirra["do_not_merge"] is True


# ── 4. Man is King marked PARTIAL_CONTAMINATION ───────────────────────────────

def test_man_is_king_partial_contamination():
    """Man is King has pre-era data but win_rate is contaminated — PARTIAL."""
    mock_snap = {"pp_win_rate": 0.0, "pp_career_runs": 36, "pp_avg_sp_last5": 12.6}
    status = classify_contamination(MAN_IS_KING_ID, mock_snap)
    assert status == "PARTIAL_CONTAMINATION"


def test_man_is_king_in_cases_correctly_classified():
    """Man is King case record must carry PARTIAL_CONTAMINATION."""
    if not CASES_JSONL.exists():
        pytest.skip("VFU-10 not yet generated")
    cases = _load_jsonl(CASES_JSONL)
    mik = next(
        (c for c in cases if str(c.get("horse_id")) == MAN_IS_KING_ID), None
    )
    assert mik is not None, f"Man is King (RP_UID {MAN_IS_KING_ID}) must appear in cases"
    assert mik["contamination_status"] == "PARTIAL_CONTAMINATION"
    snap = mik.get("pre_era_snap") or {}
    # Time-safe pre-era win_rate should be 0.0
    assert snap.get("pp_win_rate") == 0.0, (
        "Man is King pre-era pp_win_rate must be 0.0 (no pre-era wins)"
    )
    # SP was shortening — avg_sp_last5 should be < 20
    sp5 = snap.get("pp_avg_sp_last5")
    assert sp5 is not None and sp5 < 20.0, (
        "Man is King pre-era pp_avg_sp_last5 must be < 20 (SP shortened before era)"
    )


# ── 5. Group A VP<0.40 winner coverage counts present ─────────────────────────

def test_group_a_coverage_counts():
    """Summary must report Group A winner coverage from pre-era snapshot."""
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-10 not yet generated")
    s = json.loads(SUMMARY_JSON.read_text())
    assert s["group_a_distinct"] > 0
    assert s["group_a_covered"] > 0
    assert s["group_a_coverage_pct"] > 0
    # Coverage should be in the 50–80% range based on pre-build investigation
    assert 40.0 <= s["group_a_coverage_pct"] <= 90.0, (
        f"Group A coverage {s['group_a_coverage_pct']}% outside expected range 40-90%"
    )
    # Uncovered horses must sum correctly
    assert s["group_a_covered"] + s["group_a_uncovered"] == s["group_a_distinct"]


# ── 6. Group C VP<0.40 non-winner comparison group present ────────────────────

def test_group_c_present_in_summary():
    """Group C (VP<0.40 non-winners) must be in summary with stats."""
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-10 not yet generated")
    s = json.loads(SUMMARY_JSON.read_text())
    sc = s["group_stats_c"]
    assert sc["n_distinct_horses"] > 100, (
        "Group C must have >100 distinct horses"
    )
    assert sc["n_with_pre_era_snapshot"] > 0
    assert sc["avg_pp_avg_sp_last5"] is not None


def test_group_c_cases_in_jsonl():
    """Group C cases must be present in the cases JSONL."""
    if not CASES_JSONL.exists():
        pytest.skip("VFU-10 not yet generated")
    cases = _load_jsonl(CASES_JSONL)
    group_c = [c for c in cases if c.get("group") == "C"]
    assert len(group_c) > 100, f"Expected >100 Group C cases, got {len(group_c)}"


# ── 7. Watchlist is dry-run only ──────────────────────────────────────────────

def test_watchlist_dry_run_only():
    """Every watchlist entry must have blocked_from_live_use, do_not_merge, human_approval_required."""
    if not WATCHLIST_JSON.exists():
        pytest.skip("VFU-10 not yet generated")
    watchlist = json.loads(WATCHLIST_JSON.read_text())
    assert isinstance(watchlist, list)
    for w in watchlist:
        assert w.get("do_not_merge") is True, f"{w.get('horse_name')} missing do_not_merge"
        assert w.get("blocked_from_live_use") is True
        assert w.get("human_approval_required") is True
        assert w.get("canonical_passport_mutated") is False


# ── 8. Canonical Passport not mutated ─────────────────────────────────────────

def test_canonical_passport_not_mutated():
    """VFU-10 outputs must not be the canonical Passport, and must not inject into it."""
    assert str(CASES_JSONL) != str(CANON_PASSPORT)
    assert str(WATCHLIST_JSON) != str(CANON_PASSPORT)
    if CANON_PASSPORT.exists():
        content = CANON_PASSPORT.read_text(encoding="utf-8")
        assert VALIDATION_VERSION not in content
        assert "VFU_10" not in content


# ── 9. No Supabase in script ──────────────────────────────────────────────────

def test_no_supabase_in_script():
    """VFU-10 script must not contain Supabase client or URL references."""
    source = SCRIPT_FILE.read_text(encoding="utf-8")
    code = "\n".join(l for l in source.splitlines() if not l.strip().startswith("#"))
    assert "import supabase" not in code.lower()
    assert "SUPABASE_URL" not in code
    assert "create_client" not in code


# ── 10. VP threshold unchanged at 0.40 ────────────────────────────────────────

def test_vp_threshold_unchanged():
    """VP threshold must remain 0.40."""
    assert VP_THRESHOLD == 0.40
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-10 not yet generated")
    s = json.loads(SUMMARY_JSON.read_text())
    assert s["vp_threshold"] == 0.40
    assert s["vp_threshold_unchanged"] is True
    assert "NO_VP_THRESHOLD_CHANGE" in s["final_classifications"]


# ── 11. Mar–Apr not opened ────────────────────────────────────────────────────

def test_no_mar_apr_in_cases():
    """No case records must contain Mar–Apr 2026 dates."""
    if not CASES_JSONL.exists():
        pytest.skip("VFU-10 not yet generated")
    cases = _load_jsonl(CASES_JSONL)
    for c in cases:
        snap = c.get("pre_era_snap") or {}
        last_date = snap.get("last_pre_era_date", "")
        if last_date:
            assert not last_date.startswith("2026-03") and not last_date.startswith("2026-04"), (
                f"Mar–Apr date found in snapshot: {last_date} for {c.get('horse_name')}"
            )
    if not SUMMARY_JSON.exists():
        return
    s = json.loads(SUMMARY_JSON.read_text())
    assert s["mar_apr_extracted"] is False


# ── 12. Summary report with required classifications ──────────────────────────

def test_summary_hard_rules():
    """Summary must confirm all hard rules held."""
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-10 not yet generated")
    s = json.loads(SUMMARY_JSON.read_text())
    assert s["canonical_passport_mutated"] is False
    assert s["supabase_written"] is False
    assert s["live_scoring_changed"] is False
    assert s["model_promoted"] is False
    assert s["telegram_sent"] is False
    assert s["racing_api_restored"] is False
    assert s["mar_apr_extracted"] is False
    assert s["live_doctrine_promoted"] is False
    assert s["passport_override_status"] == "DRY_RUN_ONLY"
    assert s["kakirra_status"] == "TEMPORAL_CONTAMINATION_UNRESOLVABLE"
    assert s["man_is_king_status"] == "PARTIAL_CONTAMINATION"
    fc = s["final_classifications"]
    required_fc = [
        "VFU_10_TIME_SAFE_PASSPORT_OVERRIDE_VALIDATION_COMPLETE",
        "TEMPORAL_CONTAMINATION_AUDITED",
        "KAKIRRA_PREDICTIVE_PROOF_REJECTED_FOR_NOW",
        "MAN_IS_KING_PARTIAL_TIME_SAFE_SIGNAL_REVIEWED",
        "TIME_SAFE_PASSPORT_FEATURES_TESTED",
        "PASSPORT_OVERRIDE_REMAINS_DRY_RUN_ONLY",
        "NO_VP_THRESHOLD_CHANGE",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_MAR_APR_EXTRACTION",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
    ]
    for fc_item in required_fc:
        assert fc_item in fc, f"Missing final classification: {fc_item}"


def test_report_md_generated():
    """MD report must exist and contain key content."""
    if not REPORT_MD.exists():
        pytest.skip("VFU-10 not yet generated")
    content = REPORT_MD.read_text(encoding="utf-8")
    assert "VFU-10" in content
    assert "Kakirra" in content
    assert "Man is King" in content or "Man Is King" in content
    assert "TEMPORAL_CONTAMINATION" in content
    assert "DRY_RUN" in content
    assert len(content) > 3000, "Report must be substantive"


# ── Unit tests for helper functions ───────────────────────────────────────────

def test_norm_horse_strips_country():
    assert norm_horse("Man Is King (IRE)") == "man is king"
    assert norm_horse("A A Agility (NZ)") == "a a agility"
    assert norm_horse("Kakirra") == "kakirra"


def test_derive_time_safe_signals_sp_shortened():
    snap = {"pp_avg_sp_last5": 12.6, "pp_win_rate": 0.0, "pp_course_seen": 2}
    sigs = derive_time_safe_signals(snap)
    assert sigs["sp_shortened"] is True
    assert sigs["win_rate_meaningful"] is False
    assert sigs["course_experienced"] is True
    assert sigs["has_any_signal"] is True


def test_derive_time_safe_signals_none_snap():
    sigs = derive_time_safe_signals(None)
    assert sigs["sp_shortened"] is None
    assert sigs["has_any_signal"] is False
