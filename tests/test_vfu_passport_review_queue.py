"""
tests/test_vfu_passport_review_queue.py
========================================
VFU-08 — Formal Passport Update Review Queue tests.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_passport_review_queue import (
    norm_horse,
    vfu08_verdict,
    REVIEW_VERSION,
    VP_THRESHOLD,
    VFU08_VERDICTS,
    CORE_DOCTRINE,
)

CANDIDATES_JSONL  = ROOT / "data/reports/vfu_passport_review_candidates.jsonl"
REJECTED_JSON     = ROOT / "data/reports/vfu_passport_review_rejected.json"
OP_QUEUE_JSON     = ROOT / "data/reports/vfu_passport_review_operator_decision_queue.json"
REVIEW_QUEUE_JSON = ROOT / "data/reports/vfu_passport_review_queue.json"
REVIEW_QUEUE_MD   = ROOT / "data/reports/vfu_passport_review_queue.md"
KAKIRRA_MD        = ROOT / "data/reports/vfu_passport_review_kakirra_case_study.md"
SUMMARY_JSON      = ROOT / "data/reports/vfu_08_review_summary.json"
CANON_PASSPORT    = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"


def _load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


# ── 1. All verdict values are from approved set ───────────────────────────────

def test_all_verdicts_from_approved_set():
    if not CANDIDATES_JSONL.exists():
        pytest.skip("VFU-08 not yet generated")
    rows = _load_jsonl(CANDIDATES_JSONL)
    for r in rows:
        v = r.get("vfu08_verdict")
        assert v in VFU08_VERDICTS, f"Unknown VFU-08 verdict: {v} for {r.get('horse_name')}"


# ── 2. Required fields present on every candidate ─────────────────────────────

def test_candidate_required_fields():
    if not CANDIDATES_JSONL.exists():
        pytest.skip("VFU-08 not yet generated")
    rows = _load_jsonl(CANDIDATES_JSONL)
    required = {
        "horse_name", "vfu08_verdict", "vfu08_passport_proposal",
        "do_not_merge", "human_review_required", "canonical_passport_mutated",
        "review_version",
    }
    for r in rows:
        for fld in required:
            assert fld in r, f"Candidate missing field: {fld} for {r.get('horse_name')}"
        assert r["do_not_merge"] is True
        assert r["human_review_required"] is True
        assert r["canonical_passport_mutated"] is False
        assert r["review_version"] == REVIEW_VERSION


# ── 3. EOD identities NOT approved for Passport ───────────────────────────────

def test_eod_identities_not_approved_for_passport():
    if not CANDIDATES_JSONL.exists():
        pytest.skip("VFU-08 not yet generated")
    rows = _load_jsonl(CANDIDATES_JSONL)
    for r in rows:
        ns = r.get("horse_id_namespace")
        verdict = r.get("vfu08_verdict")
        if ns not in ("RP_UID", None):
            assert verdict == "NEEDS_IDENTITY_RECONCILIATION", (
                f"{r.get('horse_name')}: EOD namespace {ns} must be NEEDS_IDENTITY_RECONCILIATION, "
                f"got {verdict}"
            )


# ── 4. Kakirra is VP_UNDERCOUNTING_WATCHLIST ─────────────────────────────────

def test_kakirra_vp_undercounting_watchlist():
    if not OP_QUEUE_JSON.exists():
        pytest.skip("VFU-08 not yet generated")
    queue = json.loads(OP_QUEUE_JSON.read_text())
    kakirra = next(
        (e for e in queue if "kakirra" in (e.get("horse_name") or "").lower()),
        None,
    )
    assert kakirra is not None, "Kakirra must be in operator decision queue"
    assert kakirra["vfu08_verdict"] == "VP_UNDERCOUNTING_WATCHLIST"
    assert kakirra["do_not_merge"] is True


# ── 5. Review queue compatibility with VFU-07 test ───────────────────────────

def test_review_queue_vfu07_compatibility():
    if not REVIEW_QUEUE_JSON.exists():
        pytest.skip("VFU-08 not yet generated")
    queue = json.loads(REVIEW_QUEUE_JSON.read_text())
    assert len(queue) > 0
    types = {e["queue_type"] for e in queue}
    assert "KAKIRRA_CASE_STUDY" in types
    assert "PASSPORT_CANDIDATE_REVIEW" in types
    # Kakirra first (as per VFU-07 test_review_queue_entry_types)
    assert queue[0]["queue_type"] == "KAKIRRA_CASE_STUDY"
    for e in queue:
        assert e.get("do_not_merge") is True


# ── 6. Canonical Passport not mutated ─────────────────────────────────────────

def test_canonical_passport_not_mutated():
    assert str(CANDIDATES_JSONL) != str(CANON_PASSPORT)
    assert str(REVIEW_QUEUE_JSON) != str(CANON_PASSPORT)
    if CANON_PASSPORT.exists():
        content = CANON_PASSPORT.read_text(encoding="utf-8")
        assert REVIEW_VERSION not in content
        assert "VFU_PASSPORT_REVIEW_QUEUE" not in content


# ── 7. All proposals have do_not_merge and human_review_required ──────────────

def test_all_proposals_blocked():
    if not CANDIDATES_JSONL.exists():
        pytest.skip("VFU-08 not yet generated")
    rows = _load_jsonl(CANDIDATES_JSONL)
    for r in rows:
        proposal = r.get("vfu08_passport_proposal", {})
        assert proposal.get("do_not_merge") is True, \
            f"Proposal for {r.get('horse_name')} must have do_not_merge=True"
        assert proposal.get("human_review_required") is True
        assert proposal.get("canonical_passport_mutated") is False


# ── 8. vfu08_verdict unit: EOD → NEEDS_IDENTITY_RECONCILIATION ───────────────

def test_unit_eod_needs_reconciliation():
    cand = {
        "horse_name": "Test Horse",
        "horse_id": "hrs_99999",
        "horse_id_namespace": "RACING_API_HRS",
        "outcome": "WIN",
        "vp_at_race": 0.52,
        "score_total": 8,
    }
    result = vfu08_verdict(cand, {}, {})
    assert result == "NEEDS_IDENTITY_RECONCILIATION"


# ── 9. vfu08_verdict unit: RP_UID + WIN + score >=8 → APPROVE ────────────────

def test_unit_rp_uid_win_approve():
    cand = {
        "horse_name": "Strong Winner",
        "horse_id": "1234567",
        "horse_id_namespace": "RP_UID",
        "outcome": "WIN",
        "vp_at_race": 0.48,
        "score_total": 9,
    }
    result = vfu08_verdict(cand, {}, {})
    assert result == "APPROVE_FOR_PASSPORT_UPDATE_REVIEW"


# ── 10. vfu08_verdict unit: RP_UID + WIN + low VP → VP_UNDERCOUNTING ─────────

def test_unit_rp_uid_win_below_vp_threshold():
    cand = {
        "horse_name": "Kakirra",
        "horse_id": "8866972",
        "horse_id_namespace": "RP_UID",
        "outcome": "WIN",
        "vp_at_race": 0.27,
        "score_total": 6,
    }
    result = vfu08_verdict(cand, {}, {})
    assert result == "VP_UNDERCOUNTING_WATCHLIST"


# ── 11. vfu08_verdict unit: PLACED → PLACE_EW_PROFILE_ONLY ──────────────────

def test_unit_placed_place_ew_profile():
    cand = {
        "horse_name": "Place Specialist",
        "horse_id": "7777777",
        "horse_id_namespace": "RP_UID",
        "outcome": "PLACED",
        "vp_at_race": 0.44,
        "score_total": 5,
    }
    result = vfu08_verdict(cand, {}, {})
    assert result == "PLACE_EW_PROFILE_ONLY"


# ── 12. No Supabase in VFU-08 script ─────────────────────────────────────────

def test_no_supabase_in_vfu08_script():
    script = ROOT / "scripts/ops/vfu_passport_review_queue.py"
    source = script.read_text(encoding="utf-8")
    code = "\n".join(l for l in source.splitlines() if not l.strip().startswith("#"))
    assert "import supabase" not in code.lower()
    assert "SUPABASE_URL" not in code
    assert "create_client" not in code


# ── 13. Summary confirms all hard rules ───────────────────────────────────────

def test_summary_hard_rules():
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-08 not yet generated")
    summary = json.loads(SUMMARY_JSON.read_text())
    assert summary["any_candidate_merged"] is False
    assert summary["canonical_passport_mutated"] is False
    assert summary["supabase_written"] is False
    assert summary["live_scoring_changed"] is False
    assert summary["model_promoted"] is False
    assert summary["telegram_sent"] is False
    assert summary["racing_api_restored"] is False
    assert summary["mar_apr_extracted"] is False
    assert "VFU_08_PASSPORT_REVIEW_QUEUE_COMPLETE" in summary["final_classifications"]
    assert "CANONICAL_HORSE_PASSPORT_NOT_MUTATED" in summary["final_classifications"]
    assert "NO_SUPABASE_WRITES" in summary["final_classifications"]
    assert "NO_LIVE_SCORING_CHANGE" in summary["final_classifications"]
