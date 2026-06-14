"""
tests/test_vfu_passport_review.py
====================================
VFU-07 — Identity-Confirmed Passport Review tests.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_passport_review import (
    norm_horse, score_candidate, classify_cluster, build_kakirra_case_study,
    REVIEW_VERSION, VP_THRESHOLD, BASELINE_SR,
)

CAND_REVIEW   = ROOT / "data/reports/vfu_passport_candidate_review.json"
TRUTH_TABLE   = ROOT / "data/reports/vfu_repeated_horse_truth_table.json"
KAKIRRA_FILE  = ROOT / "data/reports/vfu_kakirra_case_study.json"
REVIEW_QUEUE  = ROOT / "data/reports/vfu_passport_review_queue.json"
SUMMARY_JSON  = ROOT / "data/reports/vfu_07_summary.json"
CANON_PASSPORT = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"
UNION_FILE    = ROOT / "data/reports/vfu_horse_id_bridge_enriched_union.json"


def _summary() -> dict:
    return json.loads(SUMMARY_JSON.read_text())


# ── 1. All scored candidates have verdict + required fields ───────────────────

def test_all_candidates_have_verdict():
    if not CAND_REVIEW.exists():
        pytest.skip("VFU-07 not yet generated")
    cands = json.loads(CAND_REVIEW.read_text())
    required = {"verdict", "score_total", "score_breakdown", "vp_alignment", "vp_band",
                "blocked_from_live_use", "human_approval_required", "do_not_merge", "review_version"}
    valid_verdicts = {
        "PROMOTE_TO_PASSPORT_REVIEW", "EOD_ID_NEEDS_RECONCILIATION",
        "OBSERVE_ONLY", "NEEDS_MORE_DATA",
    }
    for c in cands:
        for fld in required:
            assert fld in c, f"Candidate missing field: {fld}"
        assert c["verdict"] in valid_verdicts, f"Unknown verdict: {c['verdict']}"
        assert c["blocked_from_live_use"] is True
        assert c["human_approval_required"] is True
        assert c["do_not_merge"] is True
        assert c["review_version"] == REVIEW_VERSION


# ── 2. PROMOTE only when RP_UID + WIN ────────────────────────────────────────

def test_promote_requires_rp_uid_and_win():
    if not CAND_REVIEW.exists():
        pytest.skip("VFU-07 not yet generated")
    cands = json.loads(CAND_REVIEW.read_text())
    for c in cands:
        if c["verdict"] == "PROMOTE_TO_PASSPORT_REVIEW":
            assert c["horse_id_namespace"] == "RP_UID", \
                f"PROMOTE requires RP_UID, got {c['horse_id_namespace']} for {c['horse_name']}"
            assert c["outcome"] == "WIN", \
                f"PROMOTE should be WIN outcome, got {c['outcome']} for {c['horse_name']}"


# ── 3. score_candidate unit test ─────────────────────────────────────────────

def test_score_candidate_win_rp_uid_tier_b():
    cand = {
        "horse_name": "Test Horse", "horse_id": "9999", "horse_id_namespace": "RP_UID",
        "outcome": "WIN", "vp_at_race": 0.45, "evidence_quality_tier": "TIER_B_GOOD_NO_PICK_SP",
        "do_not_merge": True, "human_review_required": True, "race_date": "2026-05-21",
        "course": "Ascot", "pick_sp": None, "canonical_passport_mutated": False,
    }
    result = score_candidate(cand, {})
    assert result["verdict"] == "PROMOTE_TO_PASSPORT_REVIEW"
    assert result["score_total"] >= 4
    assert result["vp_alignment"] == "WIN_AT_THRESHOLD"
    assert result["blocked_from_live_use"] is True


# ── 4. VP alignment correctly classified ─────────────────────────────────────

def test_vp_alignment_win_below_threshold():
    cand = {
        "horse_name": "Kakirra", "horse_id": "8866972", "horse_id_namespace": "RP_UID",
        "outcome": "WIN", "vp_at_race": 0.27, "evidence_quality_tier": "TIER_B_GOOD_NO_PICK_SP",
        "do_not_merge": True, "human_review_required": True, "race_date": "2026-06-02",
        "course": "Wolverhampton", "pick_sp": None, "canonical_passport_mutated": False,
    }
    result = score_candidate(cand, {})
    assert result["vp_alignment"] == "WIN_BELOW_THRESHOLD"


# ── 5. Truth tables have required fields ─────────────────────────────────────

def test_truth_tables_required_fields():
    if not TRUTH_TABLE.exists():
        pytest.skip("VFU-07 not yet generated")
    tables = json.loads(TRUTH_TABLE.read_text())
    required = {
        "horse_name", "norm_name", "cluster_verdict", "per_run_truth_table",
        "vp_alignment_score", "wins_below_vp_threshold",
        "do_not_merge", "human_review_required", "review_version",
        "name_only_confidence",
    }
    valid_verdicts = {
        "VP_UNDERCOUNTING", "LEARNABLE_VP_POSITIVE", "PLACE_SPECIALIST",
        "NOISE", "NEEDS_MORE_RUNS", "HIGH_VP_NON_WINNER", "IDENTITY_UNRESOLVED",
    }
    for t in tables:
        for fld in required:
            assert fld in t, f"Truth table missing field: {fld} for {t.get('horse_name')}"
        assert t["cluster_verdict"] in valid_verdicts, \
            f"Unknown cluster verdict: {t['cluster_verdict']}"
        assert t["do_not_merge"] is True
        assert t["name_only_confidence"] is True


# ── 6. Kakirra is VP_UNDERCOUNTING ───────────────────────────────────────────

def test_kakirra_is_vp_undercounting():
    if not TRUTH_TABLE.exists():
        pytest.skip("VFU-07 not yet generated")
    tables = json.loads(TRUTH_TABLE.read_text())
    kakirra = next((t for t in tables if t["norm_name"] == "kakirra"), None)
    assert kakirra is not None, "Kakirra must be in truth table"
    assert kakirra["cluster_verdict"] == "VP_UNDERCOUNTING"
    assert kakirra["wins_below_vp_threshold"] == 3
    assert kakirra["wins"] == 3


# ── 7. Kakirra case study deep dive ──────────────────────────────────────────

def test_kakirra_case_study():
    if not KAKIRRA_FILE.exists():
        pytest.skip("VFU-07 not yet generated")
    k = json.loads(KAKIRRA_FILE.read_text())
    assert k["horse_rp_uid"] == 8866972
    assert k["vfu_wins"] == 3
    assert k["vfu_strike_rate"] == 1.0
    assert k["all_wins_below_vp_threshold"] is True
    assert k["analysis"]["pattern_type"] == "VP_UNDERCOUNTING"
    assert k["analysis"]["vp_vs_passport_verdict"] == "PASSPORT_TRUTH_AHEAD_OF_VP"
    assert k["do_not_merge"] is True
    assert k["blocked_from_live_use"] is True
    # All VPs must be below threshold
    for run in k["per_run_truth_table"]:
        assert run["vp"] is not None
        assert run["vp"] < VP_THRESHOLD, \
            f"Kakirra VP {run['vp']} should be below {VP_THRESHOLD} on {run['date']}"
        assert run["outcome"] == "WIN"


# ── 8. Review queue has required entry types ─────────────────────────────────

def test_review_queue_entry_types():
    if not REVIEW_QUEUE.exists():
        pytest.skip("VFU-07 not yet generated")
    queue = json.loads(REVIEW_QUEUE.read_text())
    assert len(queue) > 0
    types = {e["queue_type"] for e in queue}
    assert "KAKIRRA_CASE_STUDY" in types
    assert "PASSPORT_CANDIDATE_REVIEW" in types
    # Kakirra must be first (highest priority)
    assert queue[0]["queue_type"] == "KAKIRRA_CASE_STUDY"
    for e in queue:
        assert e.get("do_not_merge") is True


# ── 9. No merge executed ──────────────────────────────────────────────────────

def test_no_merge_executed():
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-07 not yet generated")
    summary = _summary()
    assert summary["canonical_passport_mutated"] is False
    assert summary["supabase_written"] is False
    assert "NO_PASSPORT_MERGE_EXECUTED" in summary["final_classifications"]


# ── 10. Canonical passport not mutated ───────────────────────────────────────

def test_canonical_passport_not_mutated():
    assert str(CAND_REVIEW) != str(CANON_PASSPORT)
    assert str(TRUTH_TABLE) != str(CANON_PASSPORT)
    if CANON_PASSPORT.exists():
        content = CANON_PASSPORT.read_text(encoding="utf-8")
        assert REVIEW_VERSION not in content


# ── 11. No Supabase in script ─────────────────────────────────────────────────

def test_no_supabase_in_review_script():
    script = ROOT / "scripts/ops/vfu_passport_review.py"
    source = script.read_text(encoding="utf-8")
    code = "\n".join(l for l in source.splitlines() if not l.strip().startswith("#"))
    assert "import supabase" not in code.lower()
    assert "SUPABASE_URL" not in code
    assert "create_client" not in code


# ── 12. Summary has required fields ──────────────────────────────────────────

def test_summary_required_fields():
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-07 not yet generated")
    summary = _summary()
    required = {
        "phase_a_passport_candidates", "phase_b_repeated_clusters", "phase_c_kakirra",
        "review_queue_entries", "passport_automation_status",
        "canonical_passport_mutated", "supabase_written", "final_classifications",
    }
    for k in required:
        assert k in summary, f"Summary missing key: {k}"
    assert "VFU_07_PASSPORT_REVIEW_COMPLETE" in summary["final_classifications"]
    assert "VP_UNDERCOUNTING_PATTERN_DOCUMENTED" in summary["final_classifications"]
    assert summary["passport_automation_status"] == "OPERATOR_GATE_REQUIRED_BEFORE_MERGE"


# ── 13. Phase A promote count ────────────────────────────────────────────────

def test_phase_a_promote_count():
    if not SUMMARY_JSON.exists():
        pytest.skip("VFU-07 not yet generated")
    summary = _summary()
    pa = summary["phase_a_passport_candidates"]
    assert pa["rp_uid_canonical"] == 41
    assert pa["promote_to_review_count"] > 0
    # All 69 candidates accounted for
    assert pa["total"] == 69


# ── 14. classify_cluster unit tests ──────────────────────────────────────────

def test_classify_cluster_vp_undercounting():
    cluster = {"wins": 3, "appearance_count": 3, "avg_vp": 0.265, "vp_trend": "FALLING"}
    runs = [
        {"vp": 0.343, "outcome": "WIN"},
        {"vp": 0.175, "outcome": "WIN"},
        {"vp": 0.277, "outcome": "WIN"},
    ]
    result = classify_cluster(cluster, runs)
    assert result == "VP_UNDERCOUNTING"


def test_classify_cluster_learnable():
    cluster = {"wins": 1, "appearance_count": 2, "avg_vp": 0.416, "vp_trend": "RISING"}
    runs = [{"vp": 0.38, "outcome": "WIN"}, {"vp": 0.45, "outcome": "PLACED"}]
    result = classify_cluster(cluster, runs)
    assert result == "LEARNABLE_VP_POSITIVE"


def test_classify_cluster_noise():
    cluster = {"wins": 0, "appearance_count": 2, "avg_vp": 0.223, "vp_trend": "FLAT"}
    runs = [{"vp": 0.163, "outcome": "MISS"}, {"vp": 0.282, "outcome": "MISS"}]
    result = classify_cluster(cluster, runs)
    assert result == "NOISE"
