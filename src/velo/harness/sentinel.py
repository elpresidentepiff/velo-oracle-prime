"""
VÉLØ Agent Harness — sentinel.py
==================================
Sentinel hard-rule evaluator.

The Sentinel is the last gate before any agent command is executed.
It applies a fixed set of hard rules that cannot be overridden by
any agent, operator instruction, or council verdict.

Hard blocks (any one of these fires → BLOCKED, no execution):
  1. Live betting / execution mode active
  2. Unapproved scoring or model modification
  3. Learning when source truth is degraded
  4. Learning when Sigma or Council is incomplete
  5. Writing outside contract-defined paths
  6. Running from a non-canonical repository or branch
  7. Task attempting to approve itself
  8. Racing API usage
  9. Spotify / podcast / media_ops dependency in harness path
  10. Autonomous model self-modification

Architectural boundary:
  Sentinel must never import from Spotify, podcast, or media_ops modules.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .contracts import (
    TaskContract,
    DeploymentTier,
    BLOCKED_SOURCE_TRUTH_LABELS,
)


class SentinelViolation(RuntimeError):
    """Raised when a Sentinel hard rule is violated."""
    pass


@dataclass
class SentinelResult:
    passed: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "violations": self.violations,
            "warnings": self.warnings,
        }


class Sentinel:
    """
    Applies all hard rules before any agent execution begins.

    Usage:
        sentinel = Sentinel(repo_root="/path/to/velo-oracle-prime")
        result = sentinel.evaluate(contract, source_truth="RP_SCRAPER_CLEAN")
        if not result.passed:
            raise SentinelViolation(result.violations)
    """

    # Commands that are unconditionally forbidden in any contract
    FORBIDDEN_COMMANDS: frozenset = frozenset({
        "place_order",
        "place_bet",
        "betfair_execution_agent",
        "betfair_trading_agents",
        "VELO_EXECUTION_MODE=LIVE",
    })

    # Modules that must never appear in harness imports
    FORBIDDEN_IMPORT_KEYWORDS: frozenset = frozenset({
        "spotify",
        "podcast",
        "media_ops",
        "audio_publish",
        "media_engine",
    })

    # Canonical branch for live-adjacent work
    CANONICAL_BRANCH = "main"

    def __init__(self, repo_root: Optional[str] = None) -> None:
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()

    # ── Public API ────────────────────────────────────────────────────────────

    def evaluate(
        self,
        contract: TaskContract,
        source_truth: str = "SOURCE_UNKNOWN_BLOCK",
        sigma_complete: bool = False,
        council_complete: bool = False,
        learning_requested: bool = False,
        current_branch: Optional[str] = None,
    ) -> SentinelResult:
        """
        Evaluate all hard rules for the given contract and runtime state.

        Returns a SentinelResult. If any violation is found, the result
        has passed=False and the executor must not proceed.
        """
        violations: List[str] = []
        warnings: List[str] = []

        # Rule 1: No live execution mode
        self._check_live_execution_mode(violations)

        # Rule 2: No Racing API usage
        self._check_racing_api_usage(contract, violations)

        # Rule 3: No Spotify / media_ops contamination
        self._check_media_ops_contamination(contract, violations)

        # Rule 4: Source truth must be valid and not blocked
        self._check_source_truth(source_truth, violations)

        # Rule 5: Learning gates
        if learning_requested:
            self._check_learning_gates(
                source_truth, sigma_complete, council_complete, violations
            )

        # Rule 6: Forbidden commands in contract
        self._check_forbidden_commands(contract, violations)

        # Rule 7: Forbidden paths not in write list
        self._check_forbidden_write_paths(contract, violations)

        # Rule 8: Self-approval check
        self._check_self_approval(contract, violations)

        # Rule 9: Canonical repository / branch (live-adjacent only)
        if contract.deployment_tier == DeploymentTier.LIVE_ADJACENT:
            branch = current_branch or self._get_current_branch()
            self._check_canonical_branch(branch, violations)

        # Rule 10: No model self-modification
        self._check_model_self_modification(contract, violations)

        # Warnings (non-blocking)
        if contract.deployment_tier == DeploymentTier.SHADOW:
            warnings.append(
                "SHADOW mode: Sentinel observed violations but cannot block execution."
            )

        passed = len(violations) == 0
        return SentinelResult(passed=passed, violations=violations, warnings=warnings)

    def enforce(
        self,
        contract: TaskContract,
        source_truth: str = "SOURCE_UNKNOWN_BLOCK",
        sigma_complete: bool = False,
        council_complete: bool = False,
        learning_requested: bool = False,
        current_branch: Optional[str] = None,
    ) -> SentinelResult:
        """
        Like evaluate() but raises SentinelViolation if any rule fails.
        Use this in ENFORCED tiers.
        """
        result = self.evaluate(
            contract=contract,
            source_truth=source_truth,
            sigma_complete=sigma_complete,
            council_complete=council_complete,
            learning_requested=learning_requested,
            current_branch=current_branch,
        )
        if not result.passed:
            raise SentinelViolation(
                f"Sentinel blocked execution of '{contract.mission_id}': "
                + "; ".join(result.violations)
            )
        return result

    # ── Private rule implementations ─────────────────────────────────────────

    def _check_live_execution_mode(self, violations: List[str]) -> None:
        mode = os.environ.get("VELO_EXECUTION_MODE", "SIM").upper()
        if mode == "LIVE":
            violations.append(
                "RULE_1_LIVE_EXECUTION: VELO_EXECUTION_MODE=LIVE is active. "
                "No agent execution is permitted in live mode."
            )

    def _check_racing_api_usage(
        self, contract: TaskContract, violations: List[str]
    ) -> None:
        for cmd in contract.allowed_commands:
            if "racing_api" in cmd.lower():
                violations.append(
                    f"RULE_2_RACING_API: Command '{cmd}' references Racing API. "
                    "Racing API paths are removed from doctrine. "
                    "Use RP_SCRAPER_CLEAN or LOCAL_VERIFIED_ARTIFACT only."
                )

    def _check_media_ops_contamination(
        self, contract: TaskContract, violations: List[str]
    ) -> None:
        all_items = (
            list(contract.allowed_commands)
            + list(contract.allowed_write_paths)
            + list(contract.expected_artifacts)
        )
        for item in all_items:
            for kw in self.FORBIDDEN_IMPORT_KEYWORDS:
                if kw in item.lower():
                    violations.append(
                        f"RULE_3_MEDIA_OPS: Item '{item}' contains Media Ops keyword "
                        f"'{kw}'. Agent Harness must have zero dependency on Spotify, "
                        f"podcasts, or media publishing. Move to Media Ops Engine."
                    )

    def _check_source_truth(
        self, source_truth: str, violations: List[str]
    ) -> None:
        if source_truth in BLOCKED_SOURCE_TRUTH_LABELS:
            violations.append(
                f"RULE_4_SOURCE_TRUTH: Source truth '{source_truth}' is blocked. "
                "Valid labels: RP_SCRAPER_CLEAN, RP_SCRAPER_DEGRADED, "
                "RP_MERGED_CLEAN, RP_MERGED_DEGRADED, LOCAL_VERIFIED_ARTIFACT."
            )

    def _check_learning_gates(
        self,
        source_truth: str,
        sigma_complete: bool,
        council_complete: bool,
        violations: List[str],
    ) -> None:
        degraded_labels = {"RP_SCRAPER_DEGRADED", "RP_MERGED_DEGRADED"}
        if source_truth in degraded_labels:
            violations.append(
                f"RULE_5a_LEARNING_DEGRADED: Learning is blocked when source truth "
                f"is '{source_truth}'. Source must be CLEAN before learning is eligible."
            )
        if not sigma_complete:
            violations.append(
                "RULE_5b_LEARNING_SIGMA: Learning is blocked because Sigma close "
                "has not been completed for this race day."
            )
        if not council_complete:
            violations.append(
                "RULE_5c_LEARNING_COUNCIL: Learning is blocked because Council audit "
                "has not been completed for this race day."
            )

    def _check_forbidden_commands(
        self, contract: TaskContract, violations: List[str]
    ) -> None:
        for cmd in contract.allowed_commands:
            for forbidden in self.FORBIDDEN_COMMANDS:
                if forbidden.lower() in cmd.lower():
                    violations.append(
                        f"RULE_6_FORBIDDEN_CMD: Command '{cmd}' contains forbidden "
                        f"keyword '{forbidden}'. This command is permanently blocked."
                    )

    def _check_forbidden_write_paths(
        self, contract: TaskContract, violations: List[str]
    ) -> None:
        for write_path in contract.allowed_write_paths:
            for forbidden in contract.forbidden_paths:
                if write_path.startswith(forbidden) or write_path == forbidden:
                    violations.append(
                        f"RULE_7_FORBIDDEN_WRITE: Write path '{write_path}' overlaps "
                        f"with forbidden path '{forbidden}'."
                    )

    def _check_self_approval(
        self, contract: TaskContract, violations: List[str]
    ) -> None:
        # A task cannot approve itself: if council_required is True, the task
        # must not also be listed as the council approver in its own contract.
        if contract.council_required and "self_approve" in contract.notes.lower():
            violations.append(
                "RULE_8_SELF_APPROVAL: Contract notes contain 'self_approve'. "
                "Tasks are forbidden from approving themselves."
            )

    def _check_canonical_branch(
        self, branch: str, violations: List[str]
    ) -> None:
        if branch != self.CANONICAL_BRANCH:
            violations.append(
                f"RULE_9_BRANCH: Live-adjacent tasks must run from '{self.CANONICAL_BRANCH}' "
                f"branch. Current branch is '{branch}'."
            )

    def _check_model_self_modification(
        self, contract: TaskContract, violations: List[str]
    ) -> None:
        model_paths = [
            "models/sqpe_v17",
            "models/specialist",
            "models/sqpe_v18",
            "src/velo/source_truth_enforcer.py",
            "src/velo/harness/sentinel.py",
            "src/velo/harness/contracts.py",
        ]
        for write_path in contract.allowed_write_paths:
            for model_path in model_paths:
                if model_path in write_path:
                    violations.append(
                        f"RULE_10_MODEL_SELF_MOD: Write path '{write_path}' targets "
                        f"a protected model or harness file '{model_path}'. "
                        "Autonomous model/harness self-modification is permanently forbidden."
                    )

    def _get_current_branch(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() or "unknown"
        except Exception:
            return "unknown"
