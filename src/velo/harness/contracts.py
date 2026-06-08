"""
VÉLØ Agent Harness — contracts.py
==================================
Immutable task contract schema.

Every agent task receives a TaskContract before execution begins.
No contract means no execution.

The contract defines:
  - Mission identity and objective
  - Allowed shell commands (whitelist only)
  - Allowed read/write filesystem paths
  - Forbidden paths (hard block)
  - Expected output artifacts
  - Required test commands
  - Maximum runtime in seconds
  - Required approvals (operator / council)
  - Stop conditions
  - Deployment tier (SHADOW | ENFORCED_READ_ONLY | ENFORCED_CODE | LIVE_ADJACENT)

Architectural boundary:
  Contracts must never reference Spotify, podcasts, media generation,
  or publishing. Those are Media Ops Engine concerns.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class DeploymentTier(str, Enum):
    """Graduated enforcement tiers — see VELO_AGENT_HARNESS_V1.md §6."""
    SHADOW = "SHADOW"                          # Observes but cannot block
    ENFORCED_READ_ONLY = "ENFORCED_READ_ONLY"  # Controls audits, reports, Sigma, Council packets
    ENFORCED_CODE = "ENFORCED_CODE"            # May modify approved non-live files in scoped branches
    LIVE_ADJACENT = "LIVE_ADJACENT"            # Requires Sentinel + Council + explicit operator approval


class ApprovalRequirement(str, Enum):
    NONE = "NONE"
    COUNCIL = "COUNCIL"
    OPERATOR = "OPERATOR"
    COUNCIL_AND_OPERATOR = "COUNCIL_AND_OPERATOR"


@dataclass(frozen=True)
class TaskContract:
    """
    Immutable execution contract for a single agent task.

    All fields are frozen after construction. The harness executor
    validates this contract against Sentinel hard rules before any
    subprocess is launched.
    """
    mission_id: str
    objective: str
    allowed_commands: List[str]
    allowed_read_paths: List[str]
    allowed_write_paths: List[str]
    forbidden_paths: List[str]
    expected_artifacts: List[str]
    required_tests: List[str]
    max_runtime_seconds: int
    approval_required: ApprovalRequirement
    stop_conditions: List[str]
    deployment_tier: DeploymentTier

    # Optional metadata
    task_type: str = "GENERAL"
    council_required: bool = False
    operator_required: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        # Validate no media/Spotify contamination in contract paths
        _FORBIDDEN_KEYWORDS = {"spotify", "podcast", "media_ops", "audio_publish"}
        all_paths = (
            list(self.allowed_write_paths)
            + list(self.forbidden_paths)
            + list(self.expected_artifacts)
        )
        for path in all_paths:
            for kw in _FORBIDDEN_KEYWORDS:
                if kw in path.lower():
                    raise ValueError(
                        f"TaskContract '{self.mission_id}' contains a Media Ops path "
                        f"'{path}' — harness contracts must be VELO-only. "
                        f"Media Ops Engine is a separate lane."
                    )

    def as_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "task_type": self.task_type,
            "deployment_tier": self.deployment_tier.value,
            "allowed_commands": list(self.allowed_commands),
            "allowed_read_paths": list(self.allowed_read_paths),
            "allowed_write_paths": list(self.allowed_write_paths),
            "forbidden_paths": list(self.forbidden_paths),
            "expected_artifacts": list(self.expected_artifacts),
            "required_tests": list(self.required_tests),
            "max_runtime_seconds": self.max_runtime_seconds,
            "approval_required": self.approval_required.value,
            "council_required": self.council_required,
            "operator_required": self.operator_required,
            "stop_conditions": list(self.stop_conditions),
            "notes": self.notes,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.as_dict(), indent=indent)


# ── Forbidden path constants (shared across all contracts) ────────────────────

GLOBAL_FORBIDDEN_PATHS: List[str] = [
    "app/agents/betfair_execution_agent.py",
    "app/agents/betfair_trading_agents.py",
    "src/velo/execution_bridge.py",          # Contains LIVE RuntimeError guard
    "data/sentient_state.json",              # Live sentient state — never touch
    "models/sqpe_v17/sqpe_v17.pkl",          # Live model — read-only
    "models/specialist/",                    # All specialist models — read-only
    ".env",                                  # Credentials — never modify
]

# ── Source truth labels ───────────────────────────────────────────────────────

VALID_SOURCE_TRUTH_LABELS = frozenset({
    "RP_SCRAPER_CLEAN",
    "RP_SCRAPER_DEGRADED",
    "RP_MERGED_CLEAN",
    "RP_MERGED_DEGRADED",
    "LOCAL_VERIFIED_ARTIFACT",
    "SOURCE_UNKNOWN_BLOCK",   # Always blocked — listed for completeness
})

BLOCKED_SOURCE_TRUTH_LABELS = frozenset({
    "SOURCE_UNKNOWN_BLOCK",
    "RACING_API",             # Racing API path removed from doctrine
    "API_CLEAN",              # Legacy label — no longer valid
    "LOCAL_JSON_FALLBACK",    # Legacy label — replaced by LOCAL_VERIFIED_ARTIFACT
})


def load_contract(path: str) -> TaskContract:
    """Load a TaskContract from a JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return TaskContract(
        mission_id=data["mission_id"],
        objective=data["objective"],
        task_type=data.get("task_type", "GENERAL"),
        deployment_tier=DeploymentTier(data["deployment_tier"]),
        allowed_commands=data["allowed_commands"],
        allowed_read_paths=data["allowed_read_paths"],
        allowed_write_paths=data["allowed_write_paths"],
        forbidden_paths=data.get("forbidden_paths", []) + GLOBAL_FORBIDDEN_PATHS,
        expected_artifacts=data["expected_artifacts"],
        required_tests=data.get("required_tests", []),
        max_runtime_seconds=data.get("max_runtime_seconds", 600),
        approval_required=ApprovalRequirement(data.get("approval_required", "NONE")),
        council_required=data.get("council_required", False),
        operator_required=data.get("operator_required", False),
        stop_conditions=data.get("stop_conditions", []),
        notes=data.get("notes", ""),
    )
