"""
tests/test_vfu_pattern_prosecutor.py
======================================
VFU-05 — Pattern Prosecutor tests.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RECORDS_FILE   = ROOT / "data/reports/vfu_full_current_era_autopsy_records.jsonl"
PP_RECORDS     = ROOT / "data/reports/vfu_pattern_prosecutor_evidence_records.jsonl"
WATCHLIST_FILE = ROOT / "data/reports/vfu_pattern_prosecutor_watchlist.json"
REJECTED_FILE  = ROOT / "data/reports/vfu_pattern_prosecutor_rejected_patterns.json"
QUEUE_FILE     = ROOT / "data/reports/vfu_pattern_prosecutor_human_review_queue.json"
SUMMARY_JSON   = ROOT / "data/reports/vfu_pattern_prosecutor_current_era_summary.json"
CANON_PASSPORT = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"


def _load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _summary() -> dict:
    return json.loads(SUMMARY_JSON.read_text())


# ── 1. Reads VFU current-era autopsy outputs ─────────────────────────────────

def test_reads_vfu_autopsy_outputs():
    assert RECORDS_FILE.exists(), "VFU-04 autopsy records must exist"
    records = _load_jsonl(RECORDS_FILE)
    assert len(records) == 1263


# ── 2. Pattern records include blocked_from_live_use=True ────────────────────

def test_all_patterns_blocked_from_live_use():
    if not PP_RECORDS.exists():
        pytest.skip("VFU-05 not yet generated")
    patterns = _load_jsonl(PP_RECORDS)
    assert len(patterns) > 0
    for p in patterns:
        assert p.get("blocked_from_live_use") is True, \
            f"Pattern {p.get('pattern_id')} must have blocked_from_live_use=True"


# ── 3. Pattern records require human_approval_required=True ──────────────────

def test_all_patterns_require_human_approval():
    if not PP_RECORDS.exists():
        pytest.skip("VFU-05 not yet generated")
    patterns = _load_jsonl(PP_RECORDS)
    for p in patterns:
        assert p.get("human_approval_required") is True, \
            f"Pattern {p.get('pattern_id')} must have human_approval_required=True"


# ── 4. Price patterns use only rows with pick_sp ─────────────────────────────

def test_price_patterns_use_only_pick_sp_rows():
    if not PP_RECORDS.exists():
        pytest.skip("VFU-05 not yet generated")
    patterns = _load_jsonl(PP_RECORDS)
    price_patterns = [p for p in patterns if "PRICE_BELIEF" in p.get("pattern_id", "")]
    assert len(price_patterns) >= 3, "Expected at least 3 price belief patterns"
    for p in price_patterns:
        assert "SP_SAMPLE_LIMITED" in (p.get("sample_size_warning") or ""), \
            f"Price pattern {p['pattern_id']} must carry SP_SAMPLE_LIMITED warning"
        # Evidence count should not exceed 107 (TIER_A rows only)
        assert p.get("evidence_count", 0) <= 107, \
            f"Price pattern {p['pattern_id']} uses {p.get('evidence_count')} rows, max is 107 TIER_A"


# ── 5. Rows without pick_sp excluded from ROI claims ────────────────────────

def test_no_roi_without_pick_sp():
    if not PP_RECORDS.exists():
        pytest.skip("VFU-05 not yet generated")
    patterns = _load_jsonl(PP_RECORDS)
    # DATA_BELIEF_25 must explicitly block ROI
    roi_blocked = [p for p in patterns if p.get("pattern_id") == "DATA_BELIEF_25"]
    assert len(roi_blocked) == 1
    assert roi_blocked[0]["verdict"] == "DATA_BLOCKED"
    assert "pick_sp" in roi_blocked[0]["reason"].lower()


# ── 6. Repeated-horse patterns marked NAME_ONLY_CONFIDENCE ───────────────────

def test_repeated_horse_patterns_name_only():
    if not PP_RECORDS.exists():
        pytest.skip("VFU-05 not yet generated")
    patterns = _load_jsonl(PP_RECORDS)
    horse_patterns = [p for p in patterns if "HORSE_BELIEF" in p.get("pattern_id", "")]
    assert len(horse_patterns) >= 3
    for p in horse_patterns:
        warn = (p.get("sample_size_warning") or "") + (p.get("reason") or "")
        assert "NAME_ONLY" in warn.upper() or "name_only" in warn.lower() or "horse_id" in warn.lower(), \
            f"Horse pattern {p['pattern_id']} must carry NAME_ONLY_CONFIDENCE warning"


# ── 7. Course patterns include sample warnings ────────────────────────────────

def test_course_patterns_have_sample_warnings():
    if not PP_RECORDS.exists():
        pytest.skip("VFU-05 not yet generated")
    patterns = _load_jsonl(PP_RECORDS)
    course_patterns = [p for p in patterns if "COURSE_BELIEF" in p.get("pattern_id", "")]
    assert len(course_patterns) >= 5
    for p in course_patterns:
        assert p.get("sample_size_warning"), \
            f"Course pattern {p['pattern_id']} must have sample_size_warning"


# ── 8. Hard course bans not produced ─────────────────────────────────────────

def test_no_hard_course_bans():
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-05 summary not yet generated")
    summary = _summary()
    assert summary.get("hard_course_bans_issued") is False
    assert "NO_HARD_COURSE_BANS" in summary.get("final_classifications", [])


# ── 9. Passport automation blocked when horse_id coverage is zero ────────────

def test_passport_automation_blocked():
    if not PP_RECORDS.exists():
        pytest.skip("VFU-05 not yet generated")
    patterns = _load_jsonl(PP_RECORDS)
    horse_id_pattern = next(
        (p for p in patterns if p.get("pattern_id") == "DATA_BELIEF_24"), None
    )
    assert horse_id_pattern is not None, "DATA_BELIEF_24 (horse_id blocks Passport) must exist"
    assert horse_id_pattern["verdict"] == "DATA_BLOCKED"
    assert "PASSPORT_AUTOMATION_BLOCKED_PENDING_HORSE_ID" in _summary().get("final_classifications", [])


# ── 10. Mar–Apr rows excluded ────────────────────────────────────────────────

def test_mar_apr_rows_excluded():
    if not PP_RECORDS.exists():
        pytest.skip("VFU-05 not yet generated")
    patterns = _load_jsonl(PP_RECORDS)
    assert _summary().get("source_scope") == "current_era_only_2026_05_08_to_2026_06_13"
    # Verify no autopsy record predates surgery date
    records = _load_jsonl(RECORDS_FILE)
    for r in records:
        date = r.get("race_date") or ""
        if date:
            assert date >= "2026-05-08", f"Pre-surgery row in records: {date}"


# ── 11. Supabase not required ─────────────────────────────────────────────────

def test_no_supabase_in_pattern_prosecutor():
    script = ROOT / "scripts/ops/vfu_pattern_prosecutor.py"
    source = script.read_text(encoding="utf-8")
    code = "\n".join(l for l in source.splitlines() if not l.strip().startswith("#"))
    assert "import supabase" not in code.lower()
    assert "SUPABASE_URL" not in code
    assert "create_client" not in code


# ── 12. Summary report generated ─────────────────────────────────────────────

def test_summary_report_generated():
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-05 not yet generated")
    summary = _summary()
    required = {
        "report_type", "generated_at", "vfu04_tier_counts", "vfu04_tier_reconciled",
        "patterns", "watchlist", "rejected", "summary_answers",
        "canonical_passport_mutated", "supabase_written", "final_classifications",
    }
    for k in required:
        assert k in summary, f"Summary missing key: {k}"
    assert summary["canonical_passport_mutated"] is False
    assert summary["supabase_written"] is False
    assert summary["vfu04_tier_reconciled"] is True
    assert summary["vfu04_tier_total"] == 1263
    assert "VFU_05_PATTERN_PROSECUTOR_COMPLETE" in summary["final_classifications"]


# ── 13. Watchlist generated ───────────────────────────────────────────────────

def test_watchlist_generated():
    if not WATCHLIST_FILE.exists():
        pytest.skip("VFU-05 not yet generated")
    watchlist = json.loads(WATCHLIST_FILE.read_text())
    assert len(watchlist) > 0, "Expected at least one watchlist pattern"
    required = {"pattern_id", "label", "what_would_confirm", "what_would_kill_it",
                "blocked_from_live_use", "human_approval_required"}
    for w in watchlist:
        for fld in required:
            assert fld in w, f"Watchlist entry missing field: {fld}"
        assert w["blocked_from_live_use"] is True
        assert w["human_approval_required"] is True


# ── 14. Rejected/data-blocked report generated ───────────────────────────────

def test_rejected_report_generated():
    if not REJECTED_FILE.exists():
        pytest.skip("VFU-05 not yet generated")
    rejected = json.loads(REJECTED_FILE.read_text())
    assert len(rejected) > 0, "Expected at least one rejected/blocked pattern"
    for r in rejected:
        assert r.get("verdict") in ("DATA_BLOCKED", "REJECT_FOR_NOW")
        assert r.get("blocked_from_live_use") is True


# ── 15. Human review queue generated ─────────────────────────────────────────

def test_human_review_queue_generated():
    if not QUEUE_FILE.exists():
        pytest.skip("VFU-05 not yet generated")
    queue = json.loads(QUEUE_FILE.read_text())
    assert len(queue) > 0, "Expected human review queue entries"
    types = {q.get("queue_type") for q in queue}
    assert "FALSE_GREEN_PRECEDENT" in types, "Queue must include Jun 09 false-GREEN"
    assert "VP_FALSE_POSITIVE" in types or "REPEATED_HORSE" in types


# ── 16. VFU-04 tier errata handled ───────────────────────────────────────────

def test_vfu04_tier_errata_reconciled():
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-05 not yet generated")
    summary = _summary()
    tc = summary.get("vfu04_tier_counts", {})
    assert "TIER_D_EVENT_ONLY" in tc, "TIER_D must be in reconciled tier counts"
    assert tc.get("TIER_D_EVENT_ONLY") == 294, \
        f"Expected TIER_D=294, got {tc.get('TIER_D_EVENT_ONLY')}"
    assert sum(tc.values()) == 1263, \
        f"Tier counts must sum to 1263, got {sum(tc.values())}"
    assert summary.get("vfu04_tier_reconciled") is True
