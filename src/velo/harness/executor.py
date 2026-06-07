"""
VÉLØ Agent Harness — executor.py
==================================
Harness Controller — the only entry point for agent command execution.

The HarnessExecutor:
  1. Validates the TaskContract.
  2. Runs Sentinel hard-rule evaluation.
  3. In SHADOW tier: records but does not block.
  4. In ENFORCED tiers: blocks on any Sentinel violation.
  5. Launches only registered, whitelisted commands.
  6. Records every subprocess, exit code, file change, and artifact.
  7. Runs the ArtifactVerifier after execution.
  8. Produces an immutable ExecutionReturn artifact.

The executor never:
  - Runs arbitrary shell commands not in the contract whitelist.
  - Imports or calls Spotify, podcast, or media_ops modules.
  - Modifies forbidden paths.
  - Approves its own work.
"""

from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .artifact_verifier import ArtifactVerifier
from .contracts import TaskContract, DeploymentTier
from .execution_return import (
    CommandRecord,
    ExecutionReturn,
    TestRecord,
    Verdict,
    get_git_head,
)
from .sentinel import Sentinel, SentinelViolation


class HarnessExecutor:
    """
    The controlled execution controller for all VELO agent tasks.

    Usage:
        executor = HarnessExecutor(repo_root="/path/to/velo-oracle-prime")
        ret = executor.run(
            contract=contract,
            source_truth="RP_SCRAPER_CLEAN",
            sigma_complete=True,
            council_complete=True,
        )
        ret.write("data/harness_returns")
    """

    def __init__(self, repo_root: Optional[str] = None) -> None:
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
        self.sentinel = Sentinel(repo_root=str(self.repo_root))
        self.verifier = ArtifactVerifier(repo_root=str(self.repo_root))

    def run(
        self,
        contract: TaskContract,
        source_truth: str = "SOURCE_UNKNOWN_BLOCK",
        sigma_complete: bool = False,
        council_complete: bool = False,
        learning_requested: bool = False,
        current_branch: Optional[str] = None,
        env_overrides: Optional[Dict[str, str]] = None,
    ) -> ExecutionReturn:
        """
        Execute the task defined by `contract` under full harness control.

        Returns an ExecutionReturn regardless of outcome. The caller is
        responsible for writing it to disk via ret.write().
        """
        git_head_before = get_git_head(str(self.repo_root))

        ret = ExecutionReturn(
            mission_id=contract.mission_id,
            verdict=Verdict.BLOCKED,  # default; updated on success
            source_truth=source_truth,
            deployment_tier=contract.deployment_tier.value,
            git_head_before=git_head_before,
        )

        # ── Step 1: Sentinel evaluation ───────────────────────────────────────
        sentinel_result = self.sentinel.evaluate(
            contract=contract,
            source_truth=source_truth,
            sigma_complete=sigma_complete,
            council_complete=council_complete,
            learning_requested=learning_requested,
            current_branch=current_branch,
        )
        ret.sentinel_violations = sentinel_result.violations
        ret.sentinel_warnings = sentinel_result.warnings

        if not sentinel_result.passed:
            if contract.deployment_tier != DeploymentTier.SHADOW:
                # Enforced tiers: hard block
                ret.close(Verdict.BLOCKED)
                return ret
            else:
                # Shadow tier: record but continue
                print(
                    f"[HARNESS SHADOW] Sentinel violations recorded (not blocking):\n"
                    + "\n".join(f"  - {v}" for v in sentinel_result.violations)
                )

        # ── Step 2: Execute whitelisted commands ──────────────────────────────
        all_passed = True
        for cmd in contract.allowed_commands:
            cmd_record = self._run_command(
                cmd=cmd,
                contract=contract,
                env_overrides=env_overrides,
            )
            ret.commands_run.append(cmd_record)
            if cmd_record.exit_code != 0:
                all_passed = False
                if contract.deployment_tier != DeploymentTier.SHADOW:
                    # Stop on first failure in enforced tiers
                    ret.error_message = (
                        f"Command failed: {cmd} (exit {cmd_record.exit_code})"
                    )
                    break

        # ── Step 3: Run required tests ────────────────────────────────────────
        test_records: List[TestRecord] = []
        for test_cmd in contract.required_tests:
            test_record = self._run_test(test_cmd)
            test_records.append(test_record)
            ret.tests.append(test_record)

        # ── Step 4: Artifact verification ─────────────────────────────────────
        verification = self.verifier.verify(contract, test_records)
        ret.safety_gates = {
            "all_artifacts_present": verification.all_artifacts_present,
            "forbidden_files_dirty": verification.forbidden_files_dirty,
            "all_tests_passed": verification.all_tests_passed,
            "overall_clean": verification.overall_clean,
        }
        ret.what_was_not_touched = list(contract.forbidden_paths)

        # Collect changed files (non-forbidden)
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            ret.files_changed = [
                f for f in result.stdout.strip().splitlines()
                if f not in verification.forbidden_files_dirty
            ]
        except Exception:
            pass

        # Collect created artifacts
        ret.artifacts_created = [
            a for a in contract.expected_artifacts
            if (self.repo_root / a).exists()
        ]

        # ── Step 5: Final git HEAD ────────────────────────────────────────────
        ret.git_head_after = get_git_head(str(self.repo_root))

        # ── Step 6: Determine verdict ─────────────────────────────────────────
        if verification.forbidden_files_dirty:
            verdict = Verdict.FAILED
        elif not verification.all_artifacts_present or not verification.all_tests_passed:
            verdict = Verdict.PARTIAL if all_passed else Verdict.FAILED
        elif all_passed and verification.overall_clean:
            verdict = Verdict.PASS
        else:
            verdict = Verdict.PARTIAL

        ret.close(verdict)
        return ret

    # ── Private helpers ───────────────────────────────────────────────────────

    def _run_command(
        self,
        cmd: str,
        contract: TaskContract,
        env_overrides: Optional[Dict[str, str]] = None,
    ) -> CommandRecord:
        """
        Run a single whitelisted command and return a CommandRecord.
        Arbitrary commands not in the contract are rejected.
        """
        import os

        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=contract.max_runtime_seconds,
                env=env,
            )
            duration = time.monotonic() - start
            return CommandRecord(
                command=cmd,
                exit_code=proc.returncode,
                stdout_tail=proc.stdout[-2000:] if proc.stdout else "",
                stderr_tail=proc.stderr[-2000:] if proc.stderr else "",
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            return CommandRecord(
                command=cmd,
                exit_code=-1,
                stderr_tail=f"TIMEOUT after {contract.max_runtime_seconds}s",
                duration_seconds=duration,
            )
        except Exception as exc:
            duration = time.monotonic() - start
            return CommandRecord(
                command=cmd,
                exit_code=-1,
                stderr_tail=f"EXCEPTION: {exc}",
                duration_seconds=duration,
            )

    def _run_test(self, test_cmd: str) -> TestRecord:
        """Run a single test command and return a TestRecord."""
        try:
            proc = subprocess.run(
                test_cmd,
                shell=True,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            passed = proc.returncode == 0
            output = (proc.stdout + proc.stderr)[-2000:]
            return TestRecord(
                test_command=test_cmd,
                passed=passed,
                output_tail=output,
            )
        except Exception as exc:
            return TestRecord(
                test_command=test_cmd,
                passed=False,
                output_tail=f"EXCEPTION: {exc}",
            )
