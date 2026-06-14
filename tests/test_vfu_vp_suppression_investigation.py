"""
tests/test_vfu_vp_suppression_investigation.py
================================================
VFU-09 — Kakirra / VP Suppression Investigation tests.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_vp_suppression_investigation import (
    INVESTIGATION_VERSION,
    VP_THRESHOLD,
    SUPPRESSION_TAXONOMY,
    norm_horse,
    classify_suppression,
)

ERRATA_JSON     = ROOT / "data/reports/vfu_08_verdict_distribution_errata.json"
ERRATA_MD       = ROOT / "data/reports/vfu_08_verdict_distribution_errata.md"
SUMMARY_JSON    = ROOT / "data/reports/vfu_vp_suppression_investigation.json"
CASES_JSONL     = ROOT / "data/reports/vfu_vp_suppression_cases.jsonl"
WATCHLIST_JSON  = ROOT / "data/reports/vfu_passport_override_watchlist.json"
HUMAN_QUEUE_JSON = ROOT / "data/reports/vfu_vp_suppression_human_review_queue.json"
REPORT_MD       = ROOT / "data/reports/vfu_vp_suppression_investigation.md"
CANON_PASSPORT  = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"


def _load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


# ── 1. VFU-08 errata is produced ─────────────────────────────────────────────

def test_vfu08_errata_produced():
    assert ERRATA_JSON.exists(), "VFU-08 errata JSON must exist"
    assert ERRATA_MD.exists(), "VFU-08 errata MD must exist"
    errata = json.loads(ERRATA_JSON.read_text())
    assert errata["correct_candidate_distribution"]["TOTAL"] == 69
    assert errata["reported_candidate_distribution"]["TOTAL_REPORTED"] == 65
    assert errata["reported_candidate_distribution"]["DISCREPANCY"] == 4
    assert "VFU_08_VERDICT_DISTRIBUTION_RECONCILED" in errata["final_classifications"]
    assert "REPORTING_ERROR_ONLY_DATA_WAS_ALWAYS_CORRECT" in errata["final_classifications"]


# ── 2. Kakirra appears in VP suppression cases ────────────────────────────────

def test_kakirra_in_suppression_cases():
    if not CASES_JSONL.exists():
        pytest.skip("VFU-09 not yet generated")
    cases = _load_jsonl(CASES_JSONL)
    kakirra = next((c for c in cases if "kakirra" in c.get("horse_name", "").lower()), None)
    assert kakirra is not None, "Kakirra must appear in VP suppression cases"
    assert str(kakirra["horse_id"]) == "8866972"
    assert kakirra["horse_id_namespace"] == "RP_UID"


# ── 3. Kakirra is marked VP_UNDERCOUNTING ─────────────────────────────────────

def test_kakirra_marked_vp_undercounting():
    if not CASES_JSONL.exists():
        pytest.skip("VFU-09 not yet generated")
    cases = _load_jsonl(CASES_JSONL)
    kakirra = next((c for c in cases if "kakirra" in c.get("horse_name", "").lower()), None)
    assert kakirra is not None
    assert kakirra["vfu08_verdict"] == "VP_UNDERCOUNTING_WATCHLIST"
    assert kakirra["confirmed_vp_undercounting"] is True
    assert kakirra["wins_count"] == 3
    assert kakirra["all_wins_below_vp_threshold"] is True
    # All VP values must be below threshold
    for vp in kakirra["vp_values"]:
        assert vp < VP_THRESHOLD, f"Kakirra VP {vp} should be below {VP_THRESHOLD}"


# ── 4. Passport Override Watchlist is generated ───────────────────────────────

def test_passport_override_watchlist_generated():
    if not WATCHLIST_JSON.exists():
        pytest.skip("VFU-09 not yet generated")
    watchlist = json.loads(WATCHLIST_JSON.read_text())
    assert isinstance(watchlist, list)
    assert len(watchlist) > 0, "Watchlist must have at least one entry"
    kakirra_entry = next((w for w in watchlist if "kakirra" in w.get("horse_name", "").lower()), None)
    assert kakirra_entry is not None, "Kakirra must be in watchlist"


# ── 5. Every watchlist entry has blocked_from_live_use=True ──────────────────

def test_watchlist_blocked_from_live_use():
    if not WATCHLIST_JSON.exists():
        pytest.skip("VFU-09 not yet generated")
    watchlist = json.loads(WATCHLIST_JSON.read_text())
    for w in watchlist:
        assert w.get("blocked_from_live_use") is True, \
            f"Watchlist entry {w.get('horse_name')} must have blocked_from_live_use=True"


# ── 6. Every watchlist entry has human_approval_required=True ────────────────

def test_watchlist_human_approval_required():
    if not WATCHLIST_JSON.exists():
        pytest.skip("VFU-09 not yet generated")
    watchlist = json.loads(WATCHLIST_JSON.read_text())
    for w in watchlist:
        assert w.get("human_approval_required") is True, \
            f"Watchlist entry {w.get('horse_name')} must have human_approval_required=True"
        assert w.get("do_not_merge") is True
        assert w.get("canonical_passport_mutated") is False


# ── 7. Canonical Passport not mutated ─────────────────────────────────────────

def test_canonical_passport_not_mutated():
    assert str(CASES_JSONL) != str(CANON_PASSPORT)
    assert str(WATCHLIST_JSON) != str(CANON_PASSPORT)
    if CANON_PASSPORT.exists():
        content = CANON_PASSPORT.read_text(encoding="utf-8")
        assert INVESTIGATION_VERSION not in content


# ── 8. No Supabase in script ──────────────────────────────────────────────────

def test_no_supabase_in_investigation_script():
    script = ROOT / "scripts/ops/vfu_vp_suppression_investigation.py"
    source = script.read_text(encoding="utf-8")
    code = "\n".join(l for l in source.splitlines() if not l.strip().startswith("#"))
    assert "import supabase" not in code.lower()
    assert "SUPABASE_URL" not in code
    assert "create_client" not in code


# ── 9. No Mar–Apr rows in suppression cases ───────────────────────────────────

def test_no_mar_apr_rows():
    if not CASES_JSONL.exists():
        pytest.skip("VFU-09 not yet generated")
    cases = _load_jsonl(CASES_JSONL)
    for c in cases:
        for run in c.get("per_run_detail", []):
            date = run.get("date", "")
            assert not date.startswith("2026-03") and not date.startswith("2026-04"), \
                f"Mar–Apr row found in suppression case: {date}"


# ── 10. VP threshold not changed ──────────────────────────────────────────────

def test_vp_threshold_unchanged():
    assert VP_THRESHOLD == 0.40, "VP threshold must remain 0.40"
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-09 not yet generated")
    summary = json.loads(SUMMARY_JSON.read_text())
    assert summary["vp_threshold_unchanged"] is True
    assert "NO_VP_THRESHOLD_CHANGE" in summary["final_classifications"]


# ── 11. Report is generated ───────────────────────────────────────────────────

def test_report_generated():
    if not REPORT_MD.exists():
        pytest.skip("VFU-09 not yet generated")
    content = REPORT_MD.read_text(encoding="utf-8")
    assert "VFU-09" in content
    assert "Kakirra" in content
    assert "Man Is King" in content or "Man is King" in content
    assert "Passport Override Watchlist" in content
    assert "VP_UNDERCOUNTING" in content
    assert len(content) > 3000, "Report must be substantive"


# ── 12. Summary has required hard rule confirmations ─────────────────────────

def test_summary_hard_rules():
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-09 not yet generated")
    summary = json.loads(SUMMARY_JSON.read_text())
    assert summary["canonical_passport_mutated"] is False
    assert summary["supabase_written"] is False
    assert summary["live_scoring_changed"] is False
    assert summary["model_promoted"] is False
    assert summary["telegram_sent"] is False
    assert summary["racing_api_restored"] is False
    assert summary["mar_apr_extracted"] is False
    assert summary["live_doctrine_promoted"] is False
    assert summary["passport_override_status"] == "DRY_RUN_ONLY"
    assert "VFU_09_VP_SUPPRESSION_INVESTIGATION_COMPLETE" in summary["final_classifications"]
    assert "CANONICAL_HORSE_PASSPORT_NOT_MUTATED" in summary["final_classifications"]
    assert "PASSPORT_OVERRIDE_DRY_RUN_ONLY" in summary["final_classifications"]
    assert "VP_REMAINS_POPULATION_SIGNAL_NOT_HARD_DISQUALIFIER" in summary["final_classifications"]


# ── 13. classify_suppression unit test ───────────────────────────────────────

def test_classify_suppression_tier_b():
    runs = [
        {"evidence_quality_tier": "TIER_B_GOOD_NO_PICK_SP"},
        {"evidence_quality_tier": "TIER_B_GOOD_NO_PICK_SP"},
    ]
    canon = {"8866972": {"aw_specialist": True, "sp_trajectory": "SHORTENING", "position_trend": "IMPROVING"}}
    reasons = classify_suppression("8866972", canon, runs)
    assert "LOW_FEATURE_COVERAGE_SUPPRESSED_VP" in reasons
    assert "SOURCE_LAYER_SUPPRESSED_VP" in reasons
    assert "AW_SPECIALIST_UNDERCOUNTED" in reasons
    assert "SP_SHORTENING_UNDERWEIGHTED" in reasons
    assert "PASSPORT_IMPROVEMENT_AHEAD_OF_VP" in reasons
    for r in reasons:
        assert r in SUPPRESSION_TAXONOMY, f"Reason {r} not in taxonomy"
