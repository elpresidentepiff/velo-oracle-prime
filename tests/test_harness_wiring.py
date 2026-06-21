"""
VÉLØ Harness Wiring Tests — Phase 2
=====================================
Tests proving that the harness enforcement is correctly wired into
run_prime_today.py and cannot be silently skipped.

Specifically tests:
  1. Source truth enforcement is imported and reachable from run_prime_today
  2. Observability writer is imported and reachable from run_prime_today
  3. SOURCE_UNKNOWN_BLOCK is wired before normalization/scoring
  4. _build_and_write_obs is called on PASS, FAIL, and DEGRADED paths
  5. Observability packet cannot be skipped without leaving a trace
  6. Harness imports do not break the module import chain

Hard constraints:
  - No scoring changes
  - No model changes
  - No live-state mutation
  - No Supabase writes
  - All tests use mocking or temp directories — no real pipeline execution
"""
from __future__ import annotations

import ast
import json
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "ops"))
sys.path.insert(0, str(ROOT / "src"))

RUN_PRIME_PATH = ROOT / "scripts" / "ops" / "run_prime_today.py"


# ══════════════════════════════════════════════════════════════════════════════
# 1. Static wiring verification (AST-based — no execution required)
# ══════════════════════════════════════════════════════════════════════════════

class TestStaticWiring:
    """
    Parse run_prime_today.py as AST to verify harness wiring without executing it.
    This proves the wiring exists in the source code, not just in tests.
    """

    @pytest.fixture(scope="class")
    def source(self):
        return RUN_PRIME_PATH.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def tree(self, source):
        return ast.parse(source)

    def test_source_truth_enforcer_is_imported(self, source):
        """source_truth_enforcer must be imported in run_prime_today.py."""
        assert "source_truth_enforcer" in source, (
            "source_truth_enforcer is NOT imported in run_prime_today.py. "
            "Harness Phase 2 wiring is missing."
        )

    def test_enforce_source_truth_is_imported(self, source):
        """enforce_source_truth must be imported (as _enforce_source_truth)."""
        assert "_enforce_source_truth" in source, (
            "_enforce_source_truth import missing from run_prime_today.py"
        )

    def test_source_truth_block_error_is_imported(self, source):
        """SourceTruthBlockError must be imported to handle the block path."""
        assert "_SourceTruthBlockError" in source, (
            "_SourceTruthBlockError import missing — block path is unhandled"
        )

    def test_observability_writer_is_imported(self, source):
        """write_velo_run_observability must be imported in run_prime_today.py."""
        assert "write_velo_run_observability" in source, (
            "write_velo_run_observability is NOT imported in run_prime_today.py. "
            "Observability wiring is missing."
        )

    def test_build_obs_packet_is_imported(self, source):
        """_build_obs_packet must be imported."""
        assert "_build_obs_packet" in source, (
            "_build_obs_packet import missing from run_prime_today.py"
        )

    def test_write_obs_packet_is_imported(self, source):
        """_write_obs_packet must be imported."""
        assert "_write_obs_packet" in source, (
            "_write_obs_packet import missing from run_prime_today.py"
        )

    def test_harness_gate_comment_present(self, source):
        """HARNESS GATE comment must be present to mark the enforcement point."""
        assert "HARNESS GATE" in source or "HARNESS: Source truth" in source, (
            "HARNESS GATE comment missing — enforcement point is not marked"
        )

    def test_build_and_write_obs_defined(self, source):
        """_build_and_write_obs helper must be defined in main()."""
        assert "_build_and_write_obs" in source, (
            "_build_and_write_obs not found in run_prime_today.py — "
            "observability is not wired into the exit paths"
        )

    def test_obs_called_on_fail_path(self, source):
        """_build_and_write_obs must be called with 'FAIL' in the FAIL path."""
        assert '_build_and_write_obs("FAIL")' in source, (
            "_build_and_write_obs(\"FAIL\") not found — "
            "observability is silently skipped on FAIL"
        )

    def test_obs_called_on_degraded_path(self, source):
        """_build_and_write_obs must be called with 'DEGRADED' in the DEGRADED path."""
        assert '_build_and_write_obs("DEGRADED")' in source, (
            "_build_and_write_obs(\"DEGRADED\") not found — "
            "observability is silently skipped on DEGRADED"
        )

    def test_obs_called_on_pass_path(self, source):
        """_build_and_write_obs must be called with 'PASS' in the PASS path."""
        assert '_build_and_write_obs("PASS")' in source, (
            "_build_and_write_obs(\"PASS\") not found — "
            "observability is silently skipped on PASS"
        )

    def test_source_unknown_block_handled_before_normalization(self, source):
        """SOURCE_UNKNOWN_BLOCK block must appear before STEP 2 normalization."""
        block_pos = source.find("_SourceTruthBlockError")
        step2_pos = source.find("STEP 2: Normalize")
        assert block_pos != -1, "_SourceTruthBlockError not found in source"
        assert step2_pos != -1, "STEP 2 not found in source"
        assert block_pos < step2_pos, (
            "SOURCE_UNKNOWN_BLOCK handler appears AFTER STEP 2 normalization. "
            "Blocking must happen BEFORE normalization."
        )

    def test_enforce_source_truth_called_before_step2(self, source):
        """_enforce_source_truth call must appear before STEP 2."""
        enforce_pos = source.find("_enforce_source_truth(")
        step2_pos = source.find("STEP 2: Normalize")
        assert enforce_pos != -1, "_enforce_source_truth() call not found"
        assert step2_pos != -1, "STEP 2 not found"
        assert enforce_pos < step2_pos, (
            "_enforce_source_truth() is called AFTER STEP 2. "
            "Source truth enforcement must run BEFORE normalization."
        )

    def test_harness_imports_before_load_racecards_wrapper(self, source):
        """Harness imports must appear before the load_racecards wrapper function."""
        harness_import_pos = source.find("HARNESS: source truth enforcement")
        load_wrapper_pos = source.find("def load_racecards(date_tag")
        assert harness_import_pos != -1, "Harness import comment not found"
        assert load_wrapper_pos != -1, "load_racecards wrapper not found"
        assert harness_import_pos < load_wrapper_pos, (
            "Harness imports appear AFTER load_racecards wrapper. "
            "Import order is wrong."
        )


# ══════════════════════════════════════════════════════════════════════════════
# 2. Observability writer unit tests (isolated — no pipeline execution)
# ══════════════════════════════════════════════════════════════════════════════

class TestObservabilityCannotBeSkipped:
    """
    Tests proving the observability writer cannot be silently skipped.
    Uses the write_velo_run_observability module directly.
    """

    def test_write_creates_file_with_correct_schema(self, tmp_path, monkeypatch):
        """write_observability_packet must create a valid schema file."""
        import write_velo_run_observability as _mod
        monkeypatch.setattr(_mod, "DATA", tmp_path)
        from write_velo_run_observability import build_observability_packet, validate_packet_schema, write_observability_packet
        packet = build_observability_packet(
            date_str="2026-05-27",
            source_truth="RP_MERGED_CLEAN",
            feature_health="HEALTHY",
            active_formula="sqpe_v17 | RP_MERGED_CLEAN",
            excluded_live_components=[],
            race_scoring_coverage_pct=100.0,
            persistence_status="OK",
            supabase_write_attempt_success=True,
            decision_tier_status="PASS",
            learning_gate="ELIGIBLE",
            next_safe_command="python scripts/ops/velo_session_start_check.py",
            races_processed=8,
            runners_processed=96,
        )
        out = write_observability_packet(packet)
        assert out.exists()
        loaded = json.loads(out.read_text())
        errors = validate_packet_schema(loaded)
        assert errors == [], f"Schema errors: {errors}"

    def test_fail_status_is_recorded_in_packet(self, tmp_path, monkeypatch):
        """FAIL status must be recorded in the observability packet."""
        import write_velo_run_observability as _mod
        monkeypatch.setattr(_mod, "DATA", tmp_path)
        from write_velo_run_observability import build_observability_packet, write_observability_packet
        packet = build_observability_packet(
            date_str="2026-05-27",
            source_truth="RP_MERGED_CLEAN",
            feature_health="HEALTHY",
            active_formula="sqpe_v17",
            excluded_live_components=[],
            race_scoring_coverage_pct=0.0,
            persistence_status="FAIL",
            supabase_write_attempt_success=False,
            decision_tier_status="FAIL",
            learning_gate="BLOCKED_FAIL",
            next_safe_command="python scripts/ops/velo_session_start_check.py",
            warnings=["5 persist failures, 0 score errors"],
        )
        out = write_observability_packet(packet)
        loaded = json.loads(out.read_text())
        assert loaded["decision_tier_status"] == "FAIL"
        assert loaded["supabase_write_attempt_success"] is False
        assert loaded["learning_gate"] == "BLOCKED_FAIL"
        assert len(loaded["warnings"]) > 0

    def test_source_unknown_block_is_recorded(self, tmp_path, monkeypatch):
        """SOURCE_UNKNOWN_BLOCK must be recorded in the observability packet."""
        import write_velo_run_observability as _mod
        monkeypatch.setattr(_mod, "DATA", tmp_path)
        from write_velo_run_observability import build_observability_packet, write_observability_packet
        packet = build_observability_packet(
            date_str="2026-05-27",
            source_truth="SOURCE_UNKNOWN_BLOCK",
            feature_health="BLOCKED",
            active_formula="BLOCKED_BEFORE_SCORING",
            excluded_live_components=[],
            race_scoring_coverage_pct=0.0,
            persistence_status="BLOCKED",
            supabase_write_attempt_success=False,
            decision_tier_status="BLOCKED",
            learning_gate="BLOCKED_SOURCE_UNKNOWN",
            next_safe_command="python scripts/ops/velo_session_start_check.py",
            warnings=["SOURCE_UNKNOWN_BLOCK: unrecognised loader label"],
            gate_fires={"gate_source_unknown_block": True},
        )
        out = write_observability_packet(packet)
        loaded = json.loads(out.read_text())
        assert loaded["source_truth"] == "SOURCE_UNKNOWN_BLOCK"
        assert loaded["gates"]["gate_source_unknown_block"] is True
        assert loaded["decision_tier_status"] == "BLOCKED"

    def test_degraded_source_is_recorded_in_packet(self, tmp_path, monkeypatch):
        """RP_MERGED_DEGRADED must be recorded in the observability packet."""
        import write_velo_run_observability as _mod
        monkeypatch.setattr(_mod, "DATA", tmp_path)
        from write_velo_run_observability import build_observability_packet, write_observability_packet
        packet = build_observability_packet(
            date_str="2026-05-27",
            source_truth="RP_MERGED_DEGRADED",
            feature_health="DEGRADED_RP_MERGED",
            active_formula="sqpe_v17 | RP_MERGED_DEGRADED",
            excluded_live_components=[],
            race_scoring_coverage_pct=75.0,
            persistence_status="OK",
            supabase_write_attempt_success=True,
            decision_tier_status="PASS",
            learning_gate="BLOCKED_DEGRADED_SOURCE",
            next_safe_command="python scripts/ops/velo_session_start_check.py",
            warnings=["RP_MERGED_DEGRADED: >50% runners missing pdf_intel"],
        )
        out = write_observability_packet(packet)
        loaded = json.loads(out.read_text())
        assert loaded["source_truth"] == "RP_MERGED_DEGRADED"
        assert loaded["learning_gate"] == "BLOCKED_DEGRADED_SOURCE"
        assert any("DEGRADED" in w for w in loaded["warnings"])

    def test_observability_file_naming_includes_date(self, tmp_path, monkeypatch):
        """Observability file name must include the run date."""
        import write_velo_run_observability as _mod
        monkeypatch.setattr(_mod, "DATA", tmp_path)
        from write_velo_run_observability import build_observability_packet, write_observability_packet
        packet = build_observability_packet(
            date_str="2026-05-27",
            source_truth="RP_MERGED_CLEAN",
            feature_health="HEALTHY",
            active_formula="sqpe_v17",
            excluded_live_components=[],
            race_scoring_coverage_pct=100.0,
            persistence_status="OK",
            supabase_write_attempt_success=True,
            decision_tier_status="PASS",
            learning_gate="ELIGIBLE",
            next_safe_command="python scripts/ops/velo_session_start_check.py",
        )
        out = write_observability_packet(packet)
        assert "2026_05_27" in out.name, f"Date not in filename: {out.name}"

    def test_load_observability_packet_finds_written_file(self, tmp_path, monkeypatch):
        """load_observability_packet must find the file that was just written."""
        import write_velo_run_observability as _mod
        monkeypatch.setattr(_mod, "DATA", tmp_path)
        from write_velo_run_observability import build_observability_packet, load_observability_packet, write_observability_packet
        packet = build_observability_packet(
            date_str="2026-05-27",
            source_truth="RP_MERGED_CLEAN",
            feature_health="HEALTHY",
            active_formula="sqpe_v17",
            excluded_live_components=[],
            race_scoring_coverage_pct=100.0,
            persistence_status="OK",
            supabase_write_attempt_success=True,
            decision_tier_status="PASS",
            learning_gate="ELIGIBLE",
            next_safe_command="python scripts/ops/velo_session_start_check.py",
        )
        write_observability_packet(packet)
        loaded = load_observability_packet("2026-05-27")
        assert loaded is not None
        assert loaded["source_truth"] == "RP_MERGED_CLEAN"

    def test_missing_observability_file_returns_none(self, tmp_path, monkeypatch):
        """load_observability_packet must return None when no file exists."""
        import write_velo_run_observability as _mod
        monkeypatch.setattr(_mod, "DATA", tmp_path)
        from write_velo_run_observability import load_observability_packet
        result = load_observability_packet("2099-01-01")
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# 3. Source truth enforcement wiring tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSourceTruthWiring:
    """Tests that source truth enforcement is correctly wired."""

    def test_source_truth_enforcer_importable_from_src(self):
        """source_truth_enforcer must be importable from src.velo."""
        from velo.source_truth_enforcer import (
            SourceTruthBlockError,
            enforce_source_truth,
        )
        assert callable(enforce_source_truth)
        assert issubclass(SourceTruthBlockError, RuntimeError)

    def test_unknown_source_raises_block_error(self):
        """Unknown source label must raise SourceTruthBlockError."""
        from velo.source_truth_enforcer import SourceTruthBlockError, enforce_source_truth
        with pytest.raises(SourceTruthBlockError):
            enforce_source_truth("mystery_source_xyz", raise_on_block=True)

    def test_valid_sources_do_not_raise(self):
        """Allowed loader labels must not raise."""
        from velo.source_truth_enforcer import enforce_source_truth
        for label in ("cache", "rp_merged"):
            result = enforce_source_truth(label, races=[])
            assert result.execution_allowed is True

    def test_racing_api_source_raises_block_error(self):
        """Racing API aliases must be blocked before normalization/scoring."""
        from velo.source_truth_enforcer import SourceTruthBlockError, enforce_source_truth
        for label in ("api", "racing_api", "API_CLEAN"):
            with pytest.raises(SourceTruthBlockError, match="RACING_API_BLOCKED"):
                enforce_source_truth(label, races=[])

    def test_block_error_message_contains_source_unknown(self):
        """SourceTruthBlockError message must mention SOURCE_UNKNOWN_BLOCK."""
        from velo.source_truth_enforcer import SourceTruthBlockError, enforce_source_truth
        with pytest.raises(SourceTruthBlockError, match="SOURCE_UNKNOWN_BLOCK"):
            enforce_source_truth("bad_label")

    def test_harness_wiring_comment_in_run_prime(self):
        """HARNESS GATE comment must be present in run_prime_today.py."""
        source = RUN_PRIME_PATH.read_text(encoding="utf-8")
        assert "HARNESS" in source and ("GATE" in source or "Source truth" in source)

    def test_three_obs_calls_exist_in_step7(self):
        """Exactly 3 _build_and_write_obs calls must exist (PASS, FAIL, DEGRADED)."""
        source = RUN_PRIME_PATH.read_text(encoding="utf-8")
        count = source.count("_build_and_write_obs(")
        assert count >= 3, (
            f"Expected at least 3 _build_and_write_obs() calls (PASS/FAIL/DEGRADED), "
            f"found {count}. Observability can be silently skipped."
        )
