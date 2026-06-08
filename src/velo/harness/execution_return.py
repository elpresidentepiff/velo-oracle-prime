"""
VÉLØ Agent Harness — execution_return.py
==========================================
Immutable execution return schema.

Every harness run writes one ExecutionReturn artifact.
Council reads this return. Council never controls execution itself.

Schema matches VELO_AGENT_HARNESS_V1.md §5:
{
  "mission_id": "...",
  "verdict": "PASS | BLOCKED | FAILED | PARTIAL",
  "commands_run": [],
  "files_changed": [],
  "artifacts_created": [],
  "tests": [],
  "safety_gates": {},
  "git_head_before": "...",
  "git_head_after": "...",
  "what_was_not_touched": []
}
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class Verdict(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass
class CommandRecord:
    command: str
    exit_code: int
    stdout_tail: str = ""
    stderr_tail: str = ""
    duration_seconds: float = 0.0

    def as_dict(self) -> dict:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "duration_seconds": round(self.duration_seconds, 3),
        }


@dataclass
class TestRecord:
    test_command: str
    passed: bool
    output_tail: str = ""

    def as_dict(self) -> dict:
        return {
            "test_command": self.test_command,
            "passed": self.passed,
            "output_tail": self.output_tail,
        }


@dataclass
class ExecutionReturn:
    """
    The complete, immutable record of a single harness execution.

    This is the artifact that Council reads. It is written to
    data/harness_returns/{mission_id}_{timestamp}.json
    """
    mission_id: str
    verdict: Verdict
    commands_run: List[CommandRecord] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    artifacts_created: List[str] = field(default_factory=list)
    tests: List[TestRecord] = field(default_factory=list)
    safety_gates: Dict[str, Any] = field(default_factory=dict)
    git_head_before: str = "unknown"
    git_head_after: str = "unknown"
    what_was_not_touched: List[str] = field(default_factory=list)
    sentinel_violations: List[str] = field(default_factory=list)
    sentinel_warnings: List[str] = field(default_factory=list)
    source_truth: str = "SOURCE_UNKNOWN_BLOCK"
    deployment_tier: str = "SHADOW"
    started_at: str = ""
    completed_at: str = ""
    error_message: str = ""

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()

    def close(self, verdict: Optional[Verdict] = None) -> None:
        """Finalise the return — set completed_at and optionally override verdict."""
        self.completed_at = datetime.now(timezone.utc).isoformat()
        if verdict is not None:
            self.verdict = verdict

    def as_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "verdict": self.verdict.value,
            "source_truth": self.source_truth,
            "deployment_tier": self.deployment_tier,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "git_head_before": self.git_head_before,
            "git_head_after": self.git_head_after,
            "commands_run": [c.as_dict() for c in self.commands_run],
            "files_changed": self.files_changed,
            "artifacts_created": self.artifacts_created,
            "tests": [t.as_dict() for t in self.tests],
            "safety_gates": self.safety_gates,
            "sentinel_violations": self.sentinel_violations,
            "sentinel_warnings": self.sentinel_warnings,
            "what_was_not_touched": self.what_was_not_touched,
            "error_message": self.error_message,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.as_dict(), indent=indent, default=str)

    def write(self, output_dir: str = "data/harness_returns") -> Path:
        """Write the return artifact to disk and return the path."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{self.mission_id}_{ts}.json"
        path = out / filename
        path.write_text(self.to_json(), encoding="utf-8")
        # Also write a latest pointer
        latest = out / f"{self.mission_id}_latest.json"
        latest.write_text(self.to_json(), encoding="utf-8")
        return path

    @classmethod
    def blocked(
        cls,
        mission_id: str,
        violations: List[str],
        deployment_tier: str = "SHADOW",
    ) -> "ExecutionReturn":
        """Convenience constructor for a BLOCKED return."""
        r = cls(
            mission_id=mission_id,
            verdict=Verdict.BLOCKED,
            sentinel_violations=violations,
            deployment_tier=deployment_tier,
        )
        r.close()
        return r


def get_git_head(repo_root: Optional[str] = None) -> str:
    """Return the current git HEAD SHA (short)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root or ".",
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"
