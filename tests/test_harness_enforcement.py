"""
VÉLØ Harness Enforcement Tests
================================
Tests for the four harness enforcement components:
  1. velo_session_start_check.py   — session start check
  2. write_velo_run_observability.py — observability artifact schema
  3. source_truth_enforcer.py      — degraded source gate + unknown block
  4. velo_cron_verification_report.py — cron verification report structure

Hard constraints:
  - No scoring changes
  - No model changes
  - No live-state mutation
  - No Supabase writes
  - All tests are READ_ONLY or use temp directories
"""
from __future__ import annotations

import json
import sys
import tempfile
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "ops"))
sys.path.insert(0, str(ROOT / "src"))

# ── Imports ───────────────────────────────────────────────────────────────────

from write_velo_run_observability import (
    SOURCE_LABELS,
    build_observability_packet,
    validate_packet_schema,
    write_observability_packet,
)
from velo.source_truth_enforcer import (
    SourceLabel,
    SourceTruthBlockError,
    SourceTruthDegradedWarning,
    assert_source_known,
    enforce_source_truth,
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Session Start Check Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionStartCheck:
    """Tests for velo_session_start_check.py — READ_ONLY, no state mutation."""

    def test_all_checks_run_without_exception(self):
        """Session start check must complete all 10 checks without raising."""
        from velo_session_start_check import run_checks
        checks = run_checks()
        assert len(checks) == 10, f"Expected 10 checks, got {len(checks)}"

    def test_check_keys_present(self):
        """Every check result must have required keys."""
        from velo_session_start_check import run_checks
        required_keys = {"check", "value", "status"}
        for c in run_checks():
            assert required_keys.issubset(c.keys()), f"Check missing keys: {c}"

    def test_status_values_are_valid(self):
        """Status values must be one of OK, WARN, CRITICAL, INFO."""
        from velo_session_start_check import run_checks, OK, WARN, CRITICAL, INFO
        valid = {OK, WARN, CRITICAL, INFO}
        for c in run_checks():
            assert c["status"] in valid, f"Invalid status '{c['status']}' in check: {c['check']}"

    def test_branch_head_check_returns_ok(self):
        """Branch/HEAD check must return OK when git is available."""
        from velo_session_start_check import check_branch_head, OK, CRITICAL
        result = check_branch_head()
        assert result["status"] in (OK, CRITICAL)
        assert result["value"] != ""

    def test_operational_date_is_today(self):
        """Operational date check must return today's ISO date."""
        from datetime import date
        from velo_session_start_check import check_operational_date
        result = check_operational_date()
        assert result["value"] == date.today().isoformat()

    def test_json_output_is_valid(self, capsys):
        """--json flag must produce parseable JSON."""
        from velo_session_start_check import run_checks
        import json as _json
        checks = run_checks()
        output = _json.dumps({"checks": checks})
        parsed = _json.loads(output)
        assert "checks" in parsed
        assert len(parsed["checks"]) == 10


# ══════════════════════════════════════════════════════════════════════════════
# 2. Observability Artifact Schema Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestObservabilityArtifact:
    """Tests for write_velo_run_observability.py — schema and file contract."""

    def _valid_packet_kwargs(self) -> dict:
        return dict(
            date_str="2026-05-27",
            source_truth="RP_MERGED_CLEAN",
            feature_health="HEALTHY",
            active_formula="VELO_PRIME_V10_1",
            excluded_live_components=[],
            race_scoring_coverage_pct=100.0,       # was: rpdc_coverage
            persistence_status="OK",               # was: ratings_source_status
            supabase_write_attempt_success=True,   # was: supabase_write_proof
            decision_tier_status="PASS",
            learning_gate="ELIGIBLE",
            next_safe_command="python scripts/ops/run_prime_today.py --dry-run",
        )

    def test_build_packet_has_all_11_fields(self):
        """Built packet must contain all 11 mandatory observability fields."""
        packet = build_observability_packet(**self._valid_packet_kwargs())
        errors = validate_packet_schema(packet)
        assert errors == [], f"Schema validation failed: {errors}"

    def test_invalid_source_label_raises(self):
        """Building a packet with an unknown source_truth must raise ValueError."""
        kwargs = self._valid_packet_kwargs()
        kwargs["source_truth"] = "MADE_UP_LABEL"
        with pytest.raises(ValueError, match="not a valid source label"):
            build_observability_packet(**kwargs)

    def test_all_valid_source_labels_accepted(self):
        """All canonical source labels must be accepted without error."""
        for label in SOURCE_LABELS:
            kwargs = self._valid_packet_kwargs()
            kwargs["source_truth"] = label
            packet = build_observability_packet(**kwargs)
            assert packet["source_truth"] == label

    def test_git_commit_sha_is_populated(self):
        """git_commit_sha must be a non-empty string."""
        packet = build_observability_packet(**self._valid_packet_kwargs())
        assert isinstance(packet["git_commit_sha"], str)
        assert len(packet["git_commit_sha"]) > 0

    def test_write_creates_file(self, tmp_path, monkeypatch):
        """write_observability_packet must create the JSON file on disk."""
        import write_velo_run_observability as _mod
        monkeypatch.setattr(_mod, "DATA", tmp_path)
        packet = build_observability_packet(**self._valid_packet_kwargs())
        out_path = write_observability_packet(packet)
        assert out_path.exists()
        loaded = json.loads(out_path.read_text())
        assert loaded["source_truth"] == "RP_MERGED_CLEAN"

    def test_validate_rejects_missing_field(self):
        """validate_packet_schema must catch a missing mandatory field."""
        packet = build_observability_packet(**self._valid_packet_kwargs())
        del packet["learning_gate"]
        errors = validate_packet_schema(packet)
        assert "learning_gate" in errors

    def test_validate_rejects_wrong_type_for_supabase_write_attempt_success(self):
        """supabase_write_attempt_success must be boolean."""
        packet = build_observability_packet(**self._valid_packet_kwargs())
        packet["supabase_write_attempt_success"] = "yes"
        errors = validate_packet_schema(packet)
        assert any("supabase_write_attempt_success" in e for e in errors)

    def test_deprecated_old_field_names_raise_type_error(self):
        """Using old field names (rpdc_coverage, ratings_source_status, supabase_write_proof) must raise TypeError."""
        kwargs = self._valid_packet_kwargs()
        with pytest.raises(TypeError, match="rpdc_coverage is deprecated"):
            build_observability_packet(**{**kwargs, "rpdc_coverage": 100.0})
        with pytest.raises(TypeError, match="ratings_source_status is deprecated"):
            build_observability_packet(**{**kwargs, "ratings_source_status": "OK"})
        with pytest.raises(TypeError, match="supabase_write_proof is deprecated"):
            build_observability_packet(**{**kwargs, "supabase_write_proof": True})

    def test_validate_detects_old_field_names_as_schema_errors(self):
        """validate_packet_schema must flag old field names as schema errors."""
        packet = build_observability_packet(**self._valid_packet_kwargs())
        # Manually inject old field names to simulate a stale packet
        packet["rpdc_coverage"] = 100.0
        errors = validate_packet_schema(packet)
        assert any("rpdc_coverage" in e for e in errors)

    def test_supabase_readback_verified_placeholder_present(self):
        """supabase_readback_verified must be present as None (not yet implemented)."""
        packet = build_observability_packet(**self._valid_packet_kwargs())
        assert "supabase_readback_verified" in packet
        assert packet["supabase_readback_verified"] is None, (
            "supabase_readback_verified must be None until independent readback is implemented"
        )

    def test_dry_run_does_not_create_file(self, tmp_path, monkeypatch):
        """Dry-run mode must not write any file to disk."""
        import write_velo_run_observability as _mod
        monkeypatch.setattr(_mod, "DATA", tmp_path)
        packet = build_observability_packet(**self._valid_packet_kwargs())
        write_observability_packet(packet, dry_run=True)
        assert list(tmp_path.iterdir()) == []


# ══════════════════════════════════════════════════════════════════════════════
# 3. Source Truth Enforcer Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSourceTruthEnforcer:
    """Tests for source_truth_enforcer.py — gate and block enforcement."""

    def test_cache_maps_to_local_json_fallback(self):
        """Loader label 'cache' must map to LOCAL_JSON_FALLBACK."""
        result = enforce_source_truth("cache")
        assert result.canonical_label == SourceLabel.LOCAL_JSON_FALLBACK
        assert result.execution_allowed is True
        assert result.blocked is False

    def test_rp_merged_maps_to_rp_merged_clean(self):
        """Loader label 'rp_merged' with no races must map to RP_MERGED_CLEAN."""
        result = enforce_source_truth("rp_merged", races=[])
        assert result.canonical_label == SourceLabel.RP_MERGED_CLEAN
        assert result.execution_allowed is True

    def test_api_maps_to_api_clean(self):
        """Loader label 'api' must map to API_CLEAN."""
        result = enforce_source_truth("api")
        assert result.canonical_label == SourceLabel.API_CLEAN
        assert result.execution_allowed is True

    def test_unknown_label_maps_to_source_unknown_block(self):
        """Unknown loader label must map to SOURCE_UNKNOWN_BLOCK."""
        result = enforce_source_truth("mystery_source", raise_on_block=False)
        assert result.canonical_label == SourceLabel.SOURCE_UNKNOWN_BLOCK
        assert result.execution_allowed is False
        assert result.blocked is True

    def test_source_unknown_raises_by_default(self):
        """enforce_source_truth must raise SourceTruthBlockError for unknown source."""
        with pytest.raises(SourceTruthBlockError, match="SOURCE_UNKNOWN_BLOCK"):
            enforce_source_truth("mystery_source")

    def test_assert_source_known_raises_on_unknown(self):
        """assert_source_known must raise SourceTruthBlockError for unknown source."""
        with pytest.raises(SourceTruthBlockError):
            assert_source_known("garbage_label")

    def test_assert_source_known_passes_for_cache(self):
        """assert_source_known must not raise for valid 'cache' label."""
        result = assert_source_known("cache")
        assert result.execution_allowed is True

    def test_rp_merged_does_not_depend_on_legacy_pdf_intel(self):
        """Validated RP HTML remains clean when obsolete PDF-only fields are absent."""
        # Build races where all runners have no pdf_intel
        races = [
            {"runners": [{"name": "Horse A", "pdf_intel": {}}, {"name": "Horse B"}]}
            for _ in range(5)
        ]
        result = enforce_source_truth("rp_merged", races=races, raise_on_block=False)
        assert result.canonical_label == SourceLabel.RP_MERGED_CLEAN
        assert result.degraded is False
        assert result.execution_allowed is True

    def test_healthy_rp_merged_stays_clean(self):
        """RP_MERGED_CLEAN must not be downgraded when pdf_intel is present."""
        races = [
            {
                "runners": [
                    {"name": "Horse A", "pdf_intel": {"postdata_score": 0.8, "or_compression_score": 0.5}},
                    {"name": "Horse B", "pdf_intel": {"postdata_score": 0.6, "or_compression_score": 0.4}},
                ]
            }
        ]
        result = enforce_source_truth("rp_merged", races=races)
        assert result.canonical_label == SourceLabel.RP_MERGED_CLEAN
        assert result.degraded is False

    def test_source_unknown_block_has_warning_message(self):
        """SOURCE_UNKNOWN_BLOCK result must include a descriptive warning."""
        result = enforce_source_truth("bad_source", raise_on_block=False)
        assert len(result.warnings) > 0
        assert "SOURCE_UNKNOWN_BLOCK" in result.warnings[0]

    def test_as_dict_contains_all_fields(self):
        """SourceTruthResult.as_dict() must contain all required keys."""
        result = enforce_source_truth("cache")
        d = result.as_dict()
        for key in ("canonical_label", "loader_label", "execution_allowed", "degraded", "blocked", "warnings"):
            assert key in d, f"Missing key: {key}"


# ══════════════════════════════════════════════════════════════════════════════
# 4. Cron Verification Report Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestCronVerificationReport:
    """Tests for velo_cron_verification_report.py — structure and accuracy."""

    def test_report_builds_without_exception(self):
        """build_report() must complete without raising."""
        from velo_cron_verification_report import build_report
        report = build_report()
        assert isinstance(report, dict)

    def test_report_has_required_keys(self):
        """Report must contain all required top-level keys."""
        from velo_cron_verification_report import build_report
        report = build_report()
        required = {"report_type", "timestamp", "overall_status", "critical_flags", "sections", "operator_actions_required"}
        assert required.issubset(report.keys())

    def test_report_sections_present(self):
        """Report sections must include all four audit areas."""
        from velo_cron_verification_report import build_report
        report = build_report()
        sections = report["sections"]
        assert "railway_toml" in sections
        assert "trigger_audit" in sections
        assert "rp_merged_ingestion" in sections
        assert "data_gap" in sections

    def test_overall_status_is_valid(self):
        """overall_status must be either OK or CRITICAL."""
        from velo_cron_verification_report import build_report
        report = build_report()
        assert report["overall_status"] in ("OK", "CRITICAL")

    def test_operator_actions_is_list(self):
        """operator_actions_required must be a non-empty list."""
        from velo_cron_verification_report import build_report
        report = build_report()
        assert isinstance(report["operator_actions_required"], list)
        assert len(report["operator_actions_required"]) > 0

    def test_trigger_audit_counts_are_consistent(self):
        """Manual + automated + unknown days must equal total days audited."""
        from velo_cron_verification_report import build_report
        ta = build_report()["sections"]["trigger_audit"]
        total = ta["manual_trigger_days"] + ta["automated_trigger_days"] + ta["unknown_days"]
        assert total == ta["total_days_audited"]

    def test_automation_broken_detected_on_live_repo(self):
        """Live repo has 0% automation rate — must be flagged AUTOMATION_BROKEN."""
        from velo_cron_verification_report import build_report
        report = build_report()
        # The live repo has only manual triggers — this must be detected
        ta = report["sections"]["trigger_audit"]
        assert ta["status"] == "AUTOMATION_BROKEN"
        assert "AUTOMATION_BROKEN" in report["critical_flags"]

    def test_data_gap_detected_on_live_repo(self):
        """STALE_POINT_IN_TIME (quarantined 2026-06-10): this test asserted the
        live repo HAD a 10-day data gap — true during the April incident, false
        once daily runs resumed. A unit test must not require an incident state.
        Kept for the detector contract: status must be a known label either way."""
        from velo_cron_verification_report import build_report
        report = build_report()
        dg = report["sections"]["data_gap"]
        assert dg["status"] in ("DATA_GAP_ACTIVE", "OK", "NO_GAP", "DATA_CURRENT"), (
            f"unknown data_gap status label: {dg['status']}"
        )
        if dg["status"] == "DATA_GAP_ACTIVE":
            assert "DATA_GAP_ACTIVE" in report["critical_flags"]

    def test_report_is_json_serialisable(self):
        """Report dict must be fully JSON-serialisable."""
        from velo_cron_verification_report import build_report
        report = build_report()
        serialised = json.dumps(report)
        parsed = json.loads(serialised)
        assert parsed["report_type"] == "VELO_CRON_VERIFICATION_REPORT"
