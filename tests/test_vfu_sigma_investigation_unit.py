"""
tests/test_vfu_sigma_investigation_unit.py
==========================================
VFU-11 — 2K Sigma Investigation Unit test suite.
15 required tests.

Run via WSL:
  wsl -e bash -c "cd /mnt/c/Users/puror/velo-oracle-prime && PYTHONPATH=. venv/bin/python -m pytest tests/test_vfu_sigma_investigation_unit.py -v"
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ops/vfu_sigma_investigation_unit.py"

# Output paths (must exist after running the script)
SUMMARY_JSON  = ROOT / "data/reports/vfu_11_sigma_investigation_summary.json"
LEDGER_JSONL  = ROOT / "data/reports/vfu_11_sigma_master_ledger.jsonl"
ERA_Q_JSON    = ROOT / "data/reports/vfu_11_sigma_era_quality_report.json"
DQ_JSON       = ROOT / "data/reports/vfu_11_sigma_data_quality_debt.json"
TS_JSON       = ROOT / "data/reports/vfu_11_sigma_time_safety_report.json"
PATTERNS_JSON = ROOT / "data/reports/vfu_11_sigma_pattern_candidates.json"
REVIEW_JSON   = ROOT / "data/reports/vfu_11_sigma_human_review_queue.json"
SUMMARY_MD    = ROOT / "data/reports/vfu_11_sigma_investigation_summary.md"

# Canonical Passport — must never be mutated
CANONICAL_PASSPORT = ROOT / "data/new_build/training/passport_features.parquet"


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_summary() -> dict:
    return json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))


def load_ledger() -> list[dict]:
    return [json.loads(ln) for ln in LEDGER_JSONL.read_text(encoding="utf-8").splitlines() if ln.strip()]


def load_patterns() -> list[dict]:
    return json.loads(PATTERNS_JSON.read_text(encoding="utf-8"))


def load_review_queue() -> list[dict]:
    return json.loads(REVIEW_JSON.read_text(encoding="utf-8"))


def load_era_quality() -> dict:
    return json.loads(ERA_Q_JSON.read_text(encoding="utf-8"))


def load_time_safety() -> dict:
    return json.loads(TS_JSON.read_text(encoding="utf-8"))


# ── Test 01: Script exists and imports cleanly ─────────────────────────────────

def test_01_script_exists_and_imports():
    """VFU-11 script must exist and be syntactically valid."""
    assert SCRIPT.exists(), f"Script missing: {SCRIPT}"
    import importlib.util
    spec = importlib.util.spec_from_file_location("vfu_sigma_investigation_unit", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "main"), "Script must define a main() function"
    assert hasattr(mod, "assign_era_bucket"), "Script must define assign_era_bucket()"
    assert hasattr(mod, "build_ledger_row"), "Script must define build_ledger_row()"


# ── Test 02: Era boundary — CURRENT_ERA_VALIDATED = 2026-05-08+ ───────────────

def test_02_era_boundary_current_start():
    """Date 2026-05-08 must be CURRENT_ERA_VALIDATED."""
    from scripts.ops.vfu_sigma_investigation_unit import assign_era_bucket
    assert assign_era_bucket("2026-05-08") == "CURRENT_ERA_VALIDATED"
    assert assign_era_bucket("2026-06-14") == "CURRENT_ERA_VALIDATED"
    assert assign_era_bucket("2026-05-09") == "CURRENT_ERA_VALIDATED"


# ── Test 03: Era boundary — PRE_SURGERY_MAY_QUARANTINE ────────────────────────

def test_03_era_boundary_may_quarantine():
    """Dates 2026-05-01 through 2026-05-07 must be PRE_SURGERY_MAY_QUARANTINE."""
    from scripts.ops.vfu_sigma_investigation_unit import assign_era_bucket
    assert assign_era_bucket("2026-05-01") == "PRE_SURGERY_MAY_QUARANTINE"
    assert assign_era_bucket("2026-05-07") == "PRE_SURGERY_MAY_QUARANTINE"
    assert assign_era_bucket("2026-05-04") == "PRE_SURGERY_MAY_QUARANTINE"


# ── Test 04: Era boundary — PRE_SURGERY_ARCHIVE_QUARANTINE ────────────────────

def test_04_era_boundary_archive_quarantine():
    """March and April dates must be PRE_SURGERY_ARCHIVE_QUARANTINE."""
    from scripts.ops.vfu_sigma_investigation_unit import assign_era_bucket
    assert assign_era_bucket("2026-03-17") == "PRE_SURGERY_ARCHIVE_QUARANTINE"
    assert assign_era_bucket("2026-04-30") == "PRE_SURGERY_ARCHIVE_QUARANTINE"
    assert assign_era_bucket("2026-04-01") == "PRE_SURGERY_ARCHIVE_QUARANTINE"


# ── Test 05: Null / missing date → SKELETON_OR_NULL_DATE_EXCLUDED ─────────────

def test_05_null_date_excluded():
    """Null and malformed dates must be excluded as skeleton rows."""
    from scripts.ops.vfu_sigma_investigation_unit import assign_era_bucket
    assert assign_era_bucket(None) == "SKELETON_OR_NULL_DATE_EXCLUDED"
    assert assign_era_bucket("") == "SKELETON_OR_NULL_DATE_EXCLUDED"
    assert assign_era_bucket("not-a-date") == "SKELETON_OR_NULL_DATE_EXCLUDED"
    assert assign_era_bucket("2026-01-15") == "SKELETON_OR_NULL_DATE_EXCLUDED"  # Jan/Feb


# ── Test 06: VP threshold constant = 0.40 and unchanged ──────────────────────

def test_06_vp_threshold_unchanged():
    """VP_THRESHOLD must be 0.40 — UNCHANGED."""
    from scripts.ops.vfu_sigma_investigation_unit import VP_THRESHOLD
    assert VP_THRESHOLD == 0.40, f"VP_THRESHOLD must be 0.40, got {VP_THRESHOLD}"


# ── Test 07: No Supabase writes in script ─────────────────────────────────────

def test_07_no_supabase_writes_in_script():
    """Script must not write to Supabase — no table().insert, .upsert, .update, .delete calls."""
    code = SCRIPT.read_text(encoding="utf-8")
    # Patterns that indicate Supabase DB writes (requires supabase/table context, not sys.path)
    write_patterns = [
        r"\.table\(.*\)\.insert\(",         # supabase.table(...).insert(
        r"\.table\(.*\)\.upsert\(",         # supabase.table(...).upsert(
        r"\.table\(.*\)\.update\(",         # supabase.table(...).update(
        r"\.table\(.*\)\.delete\(",         # supabase.table(...).delete(
        r"supabase.*\.insert\(",            # supabase.insert(
        r"supabase.*\.upsert\(",            # supabase.upsert(
        r"supabase.*execute",               # supabase execute
        r"SUPABASE_URL.*insert",            # any supabase URL + insert
    ]
    for pat in write_patterns:
        non_comment = [
            ln for ln in code.splitlines()
            if re.search(pat, ln) and not ln.strip().startswith("#")
        ]
        assert not non_comment, (
            f"Script contains Supabase write pattern '{pat}': {non_comment[:3]}"
        )


# ── Test 08: Canonical Passport not mutated ────────────────────────────────────

def test_08_canonical_passport_not_mutated():
    """Script must carry canonical_passport_mutated=False and hard-code no parquet writes."""
    code = SCRIPT.read_text(encoding="utf-8")
    assert "canonical_passport_mutated" in code, "Must declare canonical_passport_mutated=False"
    # No .to_parquet writes (would mutate Passport)
    parquet_writes = [
        ln for ln in code.splitlines()
        if "to_parquet" in ln and not ln.strip().startswith("#")
    ]
    assert not parquet_writes, f"Script must not write parquet: {parquet_writes}"
    # Summary JSON must confirm it
    if SUMMARY_JSON.exists():
        summary = load_summary()
        assert summary.get("canonical_passport_mutated") is False


# ── Test 09: All output files created ─────────────────────────────────────────

def test_09_all_output_files_created():
    """All 8 VFU-11 output files must exist after running the script."""
    outputs = [
        SUMMARY_JSON, LEDGER_JSONL, ERA_Q_JSON, DQ_JSON,
        TS_JSON, PATTERNS_JSON, REVIEW_JSON, SUMMARY_MD,
    ]
    missing = [str(p) for p in outputs if not p.exists()]
    assert not missing, f"Missing output files: {missing}"


# ── Test 10: Master ledger rows have required fields ──────────────────────────

def test_10_master_ledger_has_required_fields():
    """Every ledger row must have the required VFU-11 fields."""
    ledger = load_ledger()
    assert len(ledger) > 0, "Master ledger must not be empty"

    required_fields = [
        "ledger_id", "validation_version", "era_bucket", "race_date",
        "identity_status", "time_safety_status", "blocked_from_live_use",
        "usable_for_doctrine", "pattern_candidate_flags", "data_gaps",
    ]
    for i, row in enumerate(ledger[:50]):  # check first 50
        for field in required_fields:
            assert field in row, f"Row {i} missing field '{field}'"
        assert row["validation_version"] == "VFU_11_2K_SIGMA_INVESTIGATION_UNIT_V1", (
            f"Row {i} has wrong validation_version: {row['validation_version']}"
        )


# ── Test 11: Mar–Apr rows are NOT usable_for_doctrine ────────────────────────

def test_11_mar_apr_not_usable_for_doctrine():
    """PRE_SURGERY_ARCHIVE_QUARANTINE rows must have usable_for_doctrine=False."""
    ledger = load_ledger()
    archive_rows = [r for r in ledger if r.get("era_bucket") == "PRE_SURGERY_ARCHIVE_QUARANTINE"]
    assert len(archive_rows) > 0, "Must have some archive quarantine rows"
    bad = [r for r in archive_rows if r.get("usable_for_doctrine") is True]
    assert not bad, (
        f"{len(bad)} PRE_SURGERY_ARCHIVE_QUARANTINE rows are incorrectly marked usable_for_doctrine=True"
    )


# ── Test 12: Current-era time-safety = TIME_SAFE ─────────────────────────────

def test_12_current_era_is_time_safe():
    """CURRENT_ERA_VALIDATED rows must have time_safety_status=TIME_SAFE."""
    ledger = load_ledger()
    current_rows = [r for r in ledger if r.get("era_bucket") == "CURRENT_ERA_VALIDATED"]
    assert len(current_rows) > 0, "Must have current-era rows"
    bad = [r for r in current_rows if r.get("time_safety_status") != "TIME_SAFE"]
    assert not bad, (
        f"{len(bad)} CURRENT_ERA_VALIDATED rows have non-TIME_SAFE time_safety_status: "
        f"{set(r['time_safety_status'] for r in bad)}"
    )


# ── Test 13: Archive quarantine rows have TEMPORAL_CONTAMINATION_RISK ─────────

def test_13_archive_quarantine_is_contamination_risk():
    """PRE_SURGERY_ARCHIVE_QUARANTINE rows must be TEMPORAL_CONTAMINATION_RISK."""
    ledger = load_ledger()
    archive_rows = [
        r for r in ledger
        if r.get("era_bucket") == "PRE_SURGERY_ARCHIVE_QUARANTINE"
        and r.get("horse_name")  # skip event-only rows
    ]
    assert len(archive_rows) > 0, "Must have archive quarantine rows with horse names"
    bad = [r for r in archive_rows if r.get("time_safety_status") != "TEMPORAL_CONTAMINATION_RISK"]
    assert not bad, (
        f"{len(bad)} PRE_SURGERY_ARCHIVE_QUARANTINE rows have unexpected time_safety_status: "
        f"{set(r['time_safety_status'] for r in bad)}"
    )


# ── Test 14: All pattern candidates are blocked_from_live_use ─────────────────

def test_14_pattern_candidates_blocked_from_live_use():
    """Every pattern candidate must have blocked_from_live_use=True and human_approval_required=True."""
    patterns = load_patterns()
    assert len(patterns) > 0, "Must have at least one pattern candidate"
    for p in patterns:
        assert p.get("blocked_from_live_use") is True, (
            f"Pattern '{p.get('pattern_flag')}' is not blocked_from_live_use"
        )
        assert p.get("human_approval_required") is True, (
            f"Pattern '{p.get('pattern_flag')}' is not human_approval_required"
        )
        assert p.get("do_not_promote") is True, (
            f"Pattern '{p.get('pattern_flag')}' is not do_not_promote"
        )


# ── Test 15: Human review queue entries carry all required safeguards ──────────

def test_15_human_review_queue_safeguards():
    """All human review queue entries must be blocked from live use with priority scores."""
    queue = load_review_queue()
    assert len(queue) > 0, "Human review queue must not be empty"

    for i, entry in enumerate(queue[:50]):
        assert entry.get("blocked_from_live_use") is True, (
            f"Review queue entry {i} missing blocked_from_live_use=True"
        )
        assert entry.get("human_approval_required") is True, (
            f"Review queue entry {i} missing human_approval_required=True"
        )
        assert "review_priority_score" in entry, (
            f"Review queue entry {i} missing review_priority_score"
        )
        assert "era_bucket" in entry, (
            f"Review queue entry {i} missing era_bucket"
        )

    # Queue must be sorted descending by priority
    scores = [e["review_priority_score"] for e in queue]
    assert scores == sorted(scores, reverse=True), "Review queue must be sorted by priority (descending)"


# ── Summary-level checks (bonus tests that validate summary JSON) ──────────────

def test_summary_hard_rules_confirmed():
    """Summary JSON must confirm all hard VFU-11 rules."""
    summary = load_summary()
    assert summary.get("vp_threshold") == 0.40
    assert summary.get("vp_threshold_unchanged") is True
    assert summary.get("canonical_passport_mutated") is False
    assert summary.get("supabase_written") is False
    assert summary.get("live_scoring_changed") is False
    assert summary.get("model_promoted") is False
    assert summary.get("telegram_sent") is False
    assert summary.get("racing_api_restored") is False
    assert summary.get("mar_apr_quarantine_only") is True
    assert summary.get("current_era_not_blended") is True


def test_summary_final_classifications_present():
    """Summary JSON must include all 15+ required final classifications."""
    summary = load_summary()
    classifications = summary.get("final_classifications", [])
    required = [
        "VFU_11_2K_SIGMA_INVESTIGATION_UNIT_COMPLETE",
        "SIGMA_MASTER_LEDGER_CREATED",
        "ERA_BUCKETS_ENFORCED",
        "MAR_APR_QUARANTINE_ONLY",
        "TIME_SAFETY_STATUS_ASSIGNED",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "NO_VP_THRESHOLD_CHANGE",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
        "TEMPORAL_CONTAMINATION_BLOCKS_DOCTRINE",
        "PATTERN_CANDIDATES_DRY_RUN_ONLY",
    ]
    missing = [c for c in required if c not in classifications]
    assert not missing, f"Missing required classifications: {missing}"
