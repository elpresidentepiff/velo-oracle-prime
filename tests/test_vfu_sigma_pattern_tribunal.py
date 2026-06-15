"""
tests/test_vfu_sigma_pattern_tribunal.py
=========================================
VFU-12 — Sigma Pattern Tribunal test suite.
13 required tests.

Run via WSL:
  wsl -e bash -c "cd /mnt/c/Users/puror/velo-oracle-prime && PYTHONPATH=. venv/bin/python -m pytest tests/test_vfu_sigma_pattern_tribunal.py -v"
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ops/vfu_sigma_pattern_tribunal.py"

VERDICTS_JSON  = ROOT / "data/reports/vfu_12_pattern_verdicts.json"
TOP25_JSON     = ROOT / "data/reports/vfu_12_human_review_top25.json"
RANKED_JSON    = ROOT / "data/reports/vfu_12_human_review_ranked_queue.json"
QUARANTINE_JSON = ROOT / "data/reports/vfu_12_quarantine_findings.json"
DATA_BLOCKED_JSON = ROOT / "data/reports/vfu_12_data_blocked_findings.json"
SUMMARY_JSON   = ROOT / "data/reports/vfu_12_sigma_pattern_tribunal_summary.json"
SUMMARY_MD     = ROOT / "data/reports/vfu_12_sigma_pattern_tribunal_summary.md"

# VFU-11 inputs (must exist)
LEDGER_JSONL   = ROOT / "data/reports/vfu_11_sigma_master_ledger.jsonl"
PATTERNS_JSON  = ROOT / "data/reports/vfu_11_sigma_pattern_candidates.json"
REVIEW_JSON    = ROOT / "data/reports/vfu_11_sigma_human_review_queue.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_verdicts() -> list[dict]:
    return json.loads(VERDICTS_JSON.read_text(encoding="utf-8"))


def load_top25() -> list[dict]:
    return json.loads(TOP25_JSON.read_text(encoding="utf-8"))


def load_ranked() -> list[dict]:
    return json.loads(RANKED_JSON.read_text(encoding="utf-8"))


def load_summary() -> dict:
    return json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))


# ── Test 01: Script exists and imports cleanly ─────────────────────────────────

def test_01_script_exists_and_imports():
    """VFU-12 tribunal script must exist with required functions."""
    assert SCRIPT.exists(), f"Script missing: {SCRIPT}"
    import importlib.util
    spec = importlib.util.spec_from_file_location("vfu_sigma_pattern_tribunal", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "main"), "Script must define main()"
    assert hasattr(mod, "prosecute_pattern"), "Script must define prosecute_pattern()"
    assert hasattr(mod, "triage_review_queue"), "Script must define triage_review_queue()"
    assert mod.VP_THRESHOLD == 0.40, f"VP_THRESHOLD must be 0.40, got {mod.VP_THRESHOLD}"


# ── Test 02: Reads VFU-11 master ledger ───────────────────────────────────────

def test_02_reads_vfu11_master_ledger():
    """VFU-11 master ledger must exist and be readable."""
    assert LEDGER_JSONL.exists(), f"VFU-11 ledger missing: {LEDGER_JSONL}"
    rows = [json.loads(ln) for ln in LEDGER_JSONL.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) > 5000, f"Expected >5000 ledger rows, got {len(rows)}"


# ── Test 03: Reads VFU-11 pattern candidates ──────────────────────────────────

def test_03_reads_vfu11_pattern_candidates():
    """VFU-11 pattern candidates must exist and contain 7 patterns."""
    assert PATTERNS_JSON.exists(), f"VFU-11 pattern candidates missing: {PATTERNS_JSON}"
    patterns = json.loads(PATTERNS_JSON.read_text(encoding="utf-8"))
    assert len(patterns) == 7, f"Expected 7 pattern candidates, got {len(patterns)}"
    flags = {p["pattern_flag"] for p in patterns}
    expected = {
        "VP_SUPPRESSION_CANDIDATE", "FALSE_GREEN_CANDIDATE", "SP_SHORTENING_CANDIDATE",
        "PASSPORT_OVERRIDE_CANDIDATE", "ERA_CONTAMINATION_CANDIDATE",
        "DATA_QUALITY_DEBT_CANDIDATE", "IDENTITY_RESOLUTION_NEEDED",
    }
    assert flags == expected, f"Pattern flag mismatch: {flags ^ expected}"


# ── Test 04: Reads VFU-11 human review queue ──────────────────────────────────

def test_04_reads_vfu11_human_review_queue():
    """VFU-11 human review queue must exist and contain 200 entries."""
    assert REVIEW_JSON.exists(), f"VFU-11 review queue missing: {REVIEW_JSON}"
    queue = json.loads(REVIEW_JSON.read_text(encoding="utf-8"))
    assert len(queue) == 200, f"Expected 200 review queue entries, got {len(queue)}"


# ── Test 05: Tribunal verdicts assigned to all 7 patterns ────────────────────

def test_05_tribunal_verdicts_assigned():
    """Every pattern must receive a tribunal verdict."""
    verdicts = load_verdicts()
    assert len(verdicts) == 7, f"Expected 7 verdicts, got {len(verdicts)}"
    valid_verdicts = {
        "PROMOTE_TO_DRY_RUN_WATCHLIST",
        "KEEP_QUARANTINED",
        "NEEDS_TIME_SAFE_VALIDATION",
        "DATA_BLOCKED",
        "REJECT_FOR_NOW",
        "HUMAN_REVIEW_REQUIRED",
    }
    for v in verdicts:
        assert v.get("verdict") in valid_verdicts, (
            f"Pattern '{v.get('pattern_label')}' has invalid verdict: {v.get('verdict')}"
        )
        assert v.get("pattern_label"), "Every verdict must have a pattern_label"
        assert v.get("reason"), f"Verdict for '{v.get('pattern_label')}' missing reason"
        assert v.get("next_required_evidence"), f"Verdict for '{v.get('pattern_label')}' missing next_required_evidence"


# ── Test 06: All patterns blocked_from_live_use=True ─────────────────────────

def test_06_all_patterns_blocked_from_live_use():
    """Every pattern verdict must have blocked_from_live_use=True."""
    verdicts = load_verdicts()
    for v in verdicts:
        assert v.get("blocked_from_live_use") is True, (
            f"Pattern '{v.get('pattern_label')}' is not blocked_from_live_use"
        )


# ── Test 07: All patterns human_approval_required=True ───────────────────────

def test_07_all_patterns_human_approval_required():
    """Every pattern verdict must have human_approval_required=True."""
    verdicts = load_verdicts()
    for v in verdicts:
        assert v.get("human_approval_required") is True, (
            f"Pattern '{v.get('pattern_label')}' is not human_approval_required"
        )
        assert v.get("do_not_promote") is True, (
            f"Pattern '{v.get('pattern_label')}' is not do_not_promote"
        )


# ── Test 08: Mar–Apr findings remain quarantine-only ─────────────────────────

def test_08_mar_apr_quarantine_maintained():
    """ERA_CONTAMINATION_CANDIDATE must be KEEP_QUARANTINED — no doctrine pathway."""
    verdicts = load_verdicts()
    era_v = next((v for v in verdicts if v["pattern_label"] == "ERA_CONTAMINATION_CANDIDATE"), None)
    assert era_v is not None, "ERA_CONTAMINATION_CANDIDATE verdict missing"
    assert era_v["verdict"] == "KEEP_QUARANTINED", (
        f"ERA_CONTAMINATION_CANDIDATE must be KEEP_QUARANTINED, got {era_v['verdict']}"
    )
    assert era_v.get("blocked_from_live_use") is True
    assert "quarantine" in era_v.get("reason", "").lower(), "Reason must reference quarantine"

    # Also check quarantine findings output
    if QUARANTINE_JSON.exists():
        q = json.loads(QUARANTINE_JSON.read_text(encoding="utf-8"))
        assert q.get("quarantine_status") == "QUARANTINE_ONLY — no doctrine, no Passport mutation, no live scoring"


# ── Test 09: No live doctrine promotion ──────────────────────────────────────

def test_09_no_live_doctrine_promotion():
    """Summary must confirm no doctrine promotion."""
    summary = load_summary()
    assert summary.get("vp_threshold_unchanged") is True
    assert summary.get("canonical_passport_mutated") is False
    assert summary.get("supabase_written") is False
    assert summary.get("live_scoring_changed") is False
    assert summary.get("model_promoted") is False
    assert summary.get("mar_apr_quarantine_only") is True
    assert "NO_LIVE_DOCTRINE_PROMOTION" in summary.get("final_classifications", [])


# ── Test 10: VP threshold unchanged ──────────────────────────────────────────

def test_10_vp_threshold_unchanged():
    """VP threshold must be 0.40 in script constants and summary."""
    from scripts.ops.vfu_sigma_pattern_tribunal import VP_THRESHOLD
    assert VP_THRESHOLD == 0.40

    summary = load_summary()
    assert summary.get("vp_threshold") == 0.40
    assert summary.get("vp_threshold_unchanged") is True
    assert "NO_VP_THRESHOLD_CHANGE" in summary.get("final_classifications", [])


# ── Test 11: Top 25 human review queue generated ─────────────────────────────

def test_11_top25_generated():
    """Top 25 human review queue must be created with all required fields."""
    top25 = load_top25()
    assert len(top25) > 0, "Top 25 queue must not be empty"
    assert len(top25) <= 25, f"Top 25 must have at most 25 entries, got {len(top25)}"

    required_fields = [
        "entry_id", "priority_band", "era_bucket", "time_safety_status",
        "pattern_flags", "required_human_decision",
        "blocked_from_live_use", "human_approval_required",
    ]
    for i, entry in enumerate(top25):
        for field in required_fields:
            assert field in entry, f"Top 25 entry {i} missing field '{field}'"
        assert entry.get("blocked_from_live_use") is True, f"Top 25 entry {i} not blocked"
        assert entry.get("human_approval_required") is True, f"Top 25 entry {i} not human_approval_required"
        assert entry["priority_band"] in ("P0_CRITICAL", "P1_HIGH", "P2_MEDIUM"), (
            f"Top 25 entry {i} unexpected band: {entry['priority_band']}"
        )


# ── Test 12: Supabase not required / canonical Passport not mutated ───────────

def test_12_no_supabase_no_passport_mutation():
    """Script must not write Supabase and must not mutate canonical Passport."""
    code = SCRIPT.read_text(encoding="utf-8")
    # Supabase write patterns (context-aware)
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
        assert not bad, f"Script has Supabase write '{pat}': {bad[:3]}"

    # No parquet writes (would mutate Passport)
    parquet_writes = [
        ln for ln in code.splitlines()
        if "to_parquet" in ln and not ln.strip().startswith("#")
    ]
    assert not parquet_writes, f"Script must not write parquet: {parquet_writes}"

    # Summary confirms
    summary = load_summary()
    assert summary.get("canonical_passport_mutated") is False
    assert summary.get("supabase_written") is False


# ── Test 13: Summary report generated with final classifications ───────────────

def test_13_summary_report_generated():
    """VFU-12 summary JSON and MD must exist with all required classifications."""
    assert SUMMARY_JSON.exists(), f"Summary JSON missing: {SUMMARY_JSON}"
    assert SUMMARY_MD.exists(),   f"Summary MD missing: {SUMMARY_MD}"

    summary = load_summary()
    required_classifications = [
        "VFU_12_SIGMA_PATTERN_TRIBUNAL_COMPLETE",
        "PATTERN_VERDICTS_CREATED",
        "HUMAN_REVIEW_TOP25_CREATED",
        "MAR_APR_QUARANTINE_MAINTAINED",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "NO_VP_THRESHOLD_CHANGE",
        "PATTERN_CANDIDATES_DRY_RUN_ONLY",
        "HUMAN_APPROVAL_REQUIRED_FOR_ALL_PATTERNS",
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

    # MD must reference key content
    md = SUMMARY_MD.read_text(encoding="utf-8")
    assert "VFU-12" in md
    assert "0.40" in md  # VP threshold mentioned
    assert "VFU-10 Law" in md or "VFU-10 law" in md.lower()
