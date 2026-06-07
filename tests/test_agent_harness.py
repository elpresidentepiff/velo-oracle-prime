"""
VÉLØ Agent Harness — tests/test_agent_harness.py
==================================================
Unit tests for the Agent Harness controller.

Tests cover:
  - TaskContract construction and validation
  - Media Ops contamination rejection
  - Sentinel hard rules
  - ExecutionReturn schema
  - Task registry completeness
  - Architectural boundary enforcement
"""

from __future__ import annotations

import pytest

from src.velo.harness.contracts import (
    ApprovalRequirement,
    DeploymentTier,
    GLOBAL_FORBIDDEN_PATHS,
    TaskContract,
    BLOCKED_SOURCE_TRUTH_LABELS,
    VALID_SOURCE_TRUTH_LABELS,
)
from src.velo.harness.sentinel import Sentinel, SentinelResult, SentinelViolation
from src.velo.harness.execution_return import ExecutionReturn, Verdict
from src.velo.harness.task_registry import TASK_REGISTRY, get_contract


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_clean_contract(**overrides) -> TaskContract:
    """Return a minimal valid TaskContract for testing."""
    defaults = dict(
        mission_id="TEST_TASK",
        objective="Test objective",
        task_type="TEST",
        deployment_tier=DeploymentTier.SHADOW,
        allowed_commands=["python scripts/ops/preflight_10am_check.py"],
        allowed_read_paths=["data/"],
        allowed_write_paths=["data/harness_returns/"],
        forbidden_paths=GLOBAL_FORBIDDEN_PATHS,
        expected_artifacts=["data/harness_returns/TEST_TASK_latest.json"],
        required_tests=[],
        max_runtime_seconds=60,
        approval_required=ApprovalRequirement.NONE,
        stop_conditions=[],
    )
    defaults.update(overrides)
    return TaskContract(**defaults)


# ── TaskContract tests ────────────────────────────────────────────────────────

class TestTaskContract:

    def test_clean_contract_constructs(self):
        contract = _make_clean_contract()
        assert contract.mission_id == "TEST_TASK"
        assert contract.deployment_tier == DeploymentTier.SHADOW

    def test_contract_rejects_spotify_in_write_paths(self):
        with pytest.raises(ValueError, match="Media Ops path"):
            _make_clean_contract(
                allowed_write_paths=["data/spotify_output/episode.mp3"]
            )

    def test_contract_rejects_podcast_in_artifacts(self):
        with pytest.raises(ValueError, match="Media Ops path"):
            _make_clean_contract(
                expected_artifacts=["data/podcast_feed.rss"]
            )

    def test_contract_rejects_media_ops_in_forbidden(self):
        with pytest.raises(ValueError, match="Media Ops path"):
            _make_clean_contract(
                forbidden_paths=GLOBAL_FORBIDDEN_PATHS + ["media_ops/publish.py"]
            )

    def test_contract_as_dict_has_required_keys(self):
        contract = _make_clean_contract()
        d = contract.as_dict()
        required_keys = {
            "mission_id", "objective", "task_type", "deployment_tier",
            "allowed_commands", "allowed_read_paths", "allowed_write_paths",
            "forbidden_paths", "expected_artifacts", "required_tests",
            "max_runtime_seconds", "approval_required", "stop_conditions",
        }
        assert required_keys.issubset(d.keys())

    def test_source_truth_blocked_labels_do_not_include_valid_labels(self):
        assert not BLOCKED_SOURCE_TRUTH_LABELS.intersection(
            VALID_SOURCE_TRUTH_LABELS - {"SOURCE_UNKNOWN_BLOCK"}
        )


# ── Sentinel tests ────────────────────────────────────────────────────────────

class TestSentinel:

    def setup_method(self):
        self.sentinel = Sentinel()

    def test_clean_run_passes(self):
        contract = _make_clean_contract()
        result = self.sentinel.evaluate(
            contract=contract,
            source_truth="RP_SCRAPER_CLEAN",
        )
        assert result.passed

    def test_source_unknown_block_fails(self):
        contract = _make_clean_contract()
        result = self.sentinel.evaluate(
            contract=contract,
            source_truth="SOURCE_UNKNOWN_BLOCK",
        )
        assert not result.passed
        assert any("RULE_4_SOURCE_TRUTH" in v for v in result.violations)

    def test_racing_api_source_fails(self):
        contract = _make_clean_contract()
        result = self.sentinel.evaluate(
            contract=contract,
            source_truth="RACING_API",
        )
        assert not result.passed
        assert any("RULE_4_SOURCE_TRUTH" in v for v in result.violations)

    def test_racing_api_in_command_fails(self):
        contract = _make_clean_contract(
            allowed_commands=["python workers/racing_api_fetcher.py"]
        )
        result = self.sentinel.evaluate(
            contract=contract,
            source_truth="RP_SCRAPER_CLEAN",
        )
        assert not result.passed
        assert any("RULE_2_RACING_API" in v for v in result.violations)

    def test_spotify_in_command_fails(self):
        contract = _make_clean_contract(
            allowed_commands=["python media_ops/spotify_publisher.py"]
        )
        result = self.sentinel.evaluate(
            contract=contract,
            source_truth="RP_SCRAPER_CLEAN",
        )
        assert not result.passed
        assert any("RULE_3_MEDIA_OPS" in v for v in result.violations)

    def test_learning_blocked_when_degraded(self):
        contract = _make_clean_contract()
        result = self.sentinel.evaluate(
            contract=contract,
            source_truth="RP_SCRAPER_DEGRADED",
            learning_requested=True,
            sigma_complete=True,
            council_complete=True,
        )
        assert not result.passed
        assert any("RULE_5a_LEARNING_DEGRADED" in v for v in result.violations)

    def test_learning_blocked_when_sigma_incomplete(self):
        contract = _make_clean_contract()
        result = self.sentinel.evaluate(
            contract=contract,
            source_truth="RP_SCRAPER_CLEAN",
            learning_requested=True,
            sigma_complete=False,
            council_complete=True,
        )
        assert not result.passed
        assert any("RULE_5b_LEARNING_SIGMA" in v for v in result.violations)

    def test_learning_blocked_when_council_incomplete(self):
        contract = _make_clean_contract()
        result = self.sentinel.evaluate(
            contract=contract,
            source_truth="RP_SCRAPER_CLEAN",
            learning_requested=True,
            sigma_complete=True,
            council_complete=False,
        )
        assert not result.passed
        assert any("RULE_5c_LEARNING_COUNCIL" in v for v in result.violations)

    def test_learning_passes_when_all_gates_met(self):
        contract = _make_clean_contract()
        result = self.sentinel.evaluate(
            contract=contract,
            source_truth="RP_SCRAPER_CLEAN",
            learning_requested=True,
            sigma_complete=True,
            council_complete=True,
        )
        assert result.passed

    def test_enforce_raises_on_violation(self):
        contract = _make_clean_contract()
        with pytest.raises(SentinelViolation):
            self.sentinel.enforce(
                contract=contract,
                source_truth="SOURCE_UNKNOWN_BLOCK",
            )

    def test_shadow_tier_does_not_raise_on_violation(self):
        """Shadow tier records violations but evaluate() never raises."""
        contract = _make_clean_contract(deployment_tier=DeploymentTier.SHADOW)
        # evaluate() should not raise even with violations
        result = self.sentinel.evaluate(
            contract=contract,
            source_truth="SOURCE_UNKNOWN_BLOCK",
        )
        assert not result.passed  # violations recorded
        assert any("SHADOW" in w for w in result.warnings)

    def test_model_self_modification_blocked(self):
        contract = _make_clean_contract(
            allowed_write_paths=["models/sqpe_v17/sqpe_v17.pkl"]
        )
        result = self.sentinel.evaluate(
            contract=contract,
            source_truth="RP_SCRAPER_CLEAN",
        )
        assert not result.passed
        assert any("RULE_10_MODEL_SELF_MOD" in v for v in result.violations)


# ── ExecutionReturn tests ─────────────────────────────────────────────────────

class TestExecutionReturn:

    def test_blocked_constructor(self):
        ret = ExecutionReturn.blocked(
            mission_id="TEST",
            violations=["RULE_4: blocked"],
        )
        assert ret.verdict == Verdict.BLOCKED
        assert ret.sentinel_violations == ["RULE_4: blocked"]
        assert ret.completed_at != ""

    def test_as_dict_has_all_required_keys(self):
        ret = ExecutionReturn.blocked("TEST", ["v1"])
        d = ret.as_dict()
        required = {
            "mission_id", "verdict", "commands_run", "files_changed",
            "artifacts_created", "tests", "safety_gates",
            "git_head_before", "git_head_after", "what_was_not_touched",
        }
        assert required.issubset(d.keys())

    def test_verdict_values_are_valid(self):
        for v in Verdict:
            assert v.value in ("PASS", "PARTIAL", "BLOCKED", "FAILED")


# ── Task registry tests ───────────────────────────────────────────────────────

class TestTaskRegistry:

    def test_required_tasks_registered(self):
        required = {"SIGMA_CLOSE", "COUNCIL_AUDIT", "DAILY_LEARNING_AUDIT"}
        assert required.issubset(TASK_REGISTRY.keys())

    def test_all_contracts_are_valid_task_contracts(self):
        for task_id, contract in TASK_REGISTRY.items():
            assert isinstance(contract, TaskContract), f"{task_id} is not a TaskContract"

    def test_no_media_ops_in_any_contract(self):
        media_keywords = {"spotify", "podcast", "media_ops", "audio_publish"}
        for task_id, contract in TASK_REGISTRY.items():
            all_items = (
                list(contract.allowed_commands)
                + list(contract.allowed_write_paths)
                + list(contract.expected_artifacts)
            )
            for item in all_items:
                for kw in media_keywords:
                    assert kw not in item.lower(), (
                        f"Task '{task_id}' contains Media Ops keyword '{kw}' in '{item}'. "
                        "Agent Harness must be VELO-only."
                    )

    def test_get_contract_raises_for_unknown_task(self):
        with pytest.raises(KeyError, match="not registered"):
            get_contract("SPOTIFY_PUBLISH")

    def test_all_contracts_have_forbidden_paths(self):
        for task_id, contract in TASK_REGISTRY.items():
            assert len(contract.forbidden_paths) > 0, (
                f"Task '{task_id}' has no forbidden_paths — "
                "every contract must protect at least the global forbidden set."
            )

    def test_learning_audit_requires_council_and_operator(self):
        contract = get_contract("DAILY_LEARNING_AUDIT")
        assert contract.council_required
        assert contract.operator_required
