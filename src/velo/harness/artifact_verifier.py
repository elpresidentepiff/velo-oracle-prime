"""
VÉLØ Agent Harness — artifact_verifier.py
==========================================
Post-execution artifact and file-change verifier.

After the executor completes, the ArtifactVerifier:
  1. Confirms all expected_artifacts exist on disk.
  2. Confirms no forbidden_paths were modified (via git diff).
  3. Confirms all required_tests passed.
  4. Produces a verification summary for the ExecutionReturn.

The verifier is read-only — it never modifies files.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .contracts import TaskContract
from .execution_return import TestRecord


@dataclass
class VerificationResult:
    all_artifacts_present: bool
    missing_artifacts: List[str]
    forbidden_files_dirty: List[str]
    tests_passed: List[str]
    tests_failed: List[str]
    all_tests_passed: bool
    overall_clean: bool

    def as_dict(self) -> dict:
        return {
            "all_artifacts_present": self.all_artifacts_present,
            "missing_artifacts": self.missing_artifacts,
            "forbidden_files_dirty": self.forbidden_files_dirty,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "all_tests_passed": self.all_tests_passed,
            "overall_clean": self.overall_clean,
        }


class ArtifactVerifier:
    """
    Verifies artifacts, forbidden-file cleanliness, and test results
    after a harness execution.
    """

    def __init__(self, repo_root: Optional[str] = None) -> None:
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()

    def verify(
        self,
        contract: TaskContract,
        test_records: Optional[List[TestRecord]] = None,
    ) -> VerificationResult:
        """Run all post-execution checks and return a VerificationResult."""
        missing_artifacts = self._check_artifacts(contract)
        forbidden_dirty = self._check_forbidden_files(contract)
        tests_passed, tests_failed = self._evaluate_tests(test_records or [])

        all_artifacts_present = len(missing_artifacts) == 0
        all_tests_passed = len(tests_failed) == 0
        overall_clean = (
            all_artifacts_present
            and len(forbidden_dirty) == 0
            and all_tests_passed
        )

        return VerificationResult(
            all_artifacts_present=all_artifacts_present,
            missing_artifacts=missing_artifacts,
            forbidden_files_dirty=forbidden_dirty,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            all_tests_passed=all_tests_passed,
            overall_clean=overall_clean,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _check_artifacts(self, contract: TaskContract) -> List[str]:
        """Return a list of expected artifacts that do not exist on disk."""
        missing = []
        for artifact in contract.expected_artifacts:
            path = self.repo_root / artifact
            if not path.exists():
                missing.append(artifact)
        return missing

    def _check_forbidden_files(self, contract: TaskContract) -> List[str]:
        """
        Return a list of forbidden paths that have been modified
        (according to git diff --name-only HEAD).
        """
        dirty = []
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            changed_files = set(result.stdout.strip().splitlines())
            for forbidden in contract.forbidden_paths:
                for changed in changed_files:
                    if changed.startswith(forbidden) or changed == forbidden:
                        dirty.append(changed)
        except Exception as exc:
            dirty.append(f"GIT_DIFF_ERROR: {exc}")
        return dirty

    def _evaluate_tests(
        self, test_records: List[TestRecord]
    ) -> tuple[List[str], List[str]]:
        passed = [t.test_command for t in test_records if t.passed]
        failed = [t.test_command for t in test_records if not t.passed]
        return passed, failed
