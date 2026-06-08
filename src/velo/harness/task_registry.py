"""
VÉLØ Agent Harness — task_registry.py
=======================================
Registry of all approved TaskContracts.

Only tasks registered here may be executed by the HarnessExecutor.
No contract means no execution.

Current registered tasks (Phase 1 — shadow mode):
  - SIGMA_CLOSE          : Post-race Sigma close
  - COUNCIL_AUDIT        : Daily Council evidence audit
  - DAILY_LEARNING_AUDIT : Daily learning eligibility audit
  - DAILY_MORNING_PRIME  : Morning scoring pipeline (read-only observation)
  - PREFLIGHT_CHECK      : Pre-race preflight validation

Architectural boundary:
  No Media Ops, Spotify, or podcast tasks may be registered here.
  Those belong to the Media Ops Engine task registry.
"""

from __future__ import annotations

from typing import Dict

from .contracts import (
    ApprovalRequirement,
    DeploymentTier,
    GLOBAL_FORBIDDEN_PATHS,
    TaskContract,
)

# ── Shared forbidden path set ─────────────────────────────────────────────────

_FORBIDDEN = GLOBAL_FORBIDDEN_PATHS + [
    "data/sentient_state.json",
    "data/sentient_state_shadow.json",  # Only authorized shadow-learning tasks may touch
]

# ── Registered contracts ──────────────────────────────────────────────────────

TASK_REGISTRY: Dict[str, TaskContract] = {

    "SIGMA_CLOSE": TaskContract(
        mission_id="SIGMA_CLOSE",
        objective="Run post-race Sigma close for the given race date. "
                  "Produces sigma artifact and updates Council evidence packet.",
        task_type="SIGMA",
        deployment_tier=DeploymentTier.SHADOW,
        allowed_commands=[
            "python scripts/ops/run_results_sigma.py --date {date}",
        ],
        allowed_read_paths=[
            "data/",
            "scripts/ops/run_results_sigma.py",
            "src/velo/",
        ],
        allowed_write_paths=[
            "sigma/",
            "data/sigma_latest.json",
            "data/harness_returns/",
        ],
        forbidden_paths=_FORBIDDEN,
        expected_artifacts=[
            "data/sigma_latest.json",
        ],
        required_tests=[],
        max_runtime_seconds=300,
        approval_required=ApprovalRequirement.NONE,
        council_required=False,
        operator_required=False,
        stop_conditions=[
            "source_truth == SOURCE_UNKNOWN_BLOCK",
            "exit_code != 0",
        ],
        notes="Shadow mode: Sentinel observes but does not block.",
    ),

    "COUNCIL_AUDIT": TaskContract(
        mission_id="COUNCIL_AUDIT",
        objective="Run daily Council evidence audit. Reads sigma and observability "
                  "artifacts and produces a Council evidence packet.",
        task_type="COUNCIL",
        deployment_tier=DeploymentTier.SHADOW,
        allowed_commands=[
            "python scripts/audit/build_unified_evidence_corpus.py --date {date}",
        ],
        allowed_read_paths=[
            "data/",
            "sigma/",
            "scripts/audit/",
            "src/velo/council/",
        ],
        allowed_write_paths=[
            "data/council_evidence_latest.json",
            "data/harness_returns/",
        ],
        forbidden_paths=_FORBIDDEN,
        expected_artifacts=[
            "data/council_evidence_latest.json",
        ],
        required_tests=[],
        max_runtime_seconds=300,
        approval_required=ApprovalRequirement.NONE,
        council_required=False,
        operator_required=False,
        stop_conditions=[
            "sigma_complete == False",
        ],
        notes="Shadow mode. Council reads this artifact — Council never controls execution.",
    ),

    "DAILY_LEARNING_AUDIT": TaskContract(
        mission_id="DAILY_LEARNING_AUDIT",
        objective="Run daily learning eligibility audit. Checks source truth, "
                  "Sigma completion, and Council sign-off before any learning is permitted.",
        task_type="LEARNING_AUDIT",
        deployment_tier=DeploymentTier.SHADOW,
        allowed_commands=[
            "python scripts/ops/nightly_eod_learning_runner.py --date {date} --dry-run",
        ],
        allowed_read_paths=[
            "data/",
            "sigma/",
            "scripts/ops/",
            "src/velo/",
        ],
        allowed_write_paths=[
            "data/learning_audit_latest.json",
            "data/harness_returns/",
        ],
        forbidden_paths=_FORBIDDEN + [
            "data/sentient_state_shadow.json",  # Dry-run only — no shadow state writes
        ],
        expected_artifacts=[
            "data/learning_audit_latest.json",
        ],
        required_tests=[],
        max_runtime_seconds=300,
        approval_required=ApprovalRequirement.COUNCIL_AND_OPERATOR,
        council_required=True,
        operator_required=True,
        stop_conditions=[
            "source_truth in {RP_SCRAPER_DEGRADED, RP_MERGED_DEGRADED, SOURCE_UNKNOWN_BLOCK}",
            "sigma_complete == False",
            "council_complete == False",
        ],
        notes="Dry-run only in shadow mode. No sentient state writes permitted.",
    ),

    "DAILY_MORNING_PRIME": TaskContract(
        mission_id="DAILY_MORNING_PRIME",
        objective="Observe the morning scoring pipeline. Shadow mode only — "
                  "records execution but does not block or modify scoring.",
        task_type="SCORING_OBSERVATION",
        deployment_tier=DeploymentTier.SHADOW,
        allowed_commands=[
            "python scripts/ops/run_prime_today.py --date {date}",
        ],
        allowed_read_paths=[
            "data/",
            "scripts/ops/",
            "src/velo/",
            "models/",
        ],
        allowed_write_paths=[
            "data/harness_returns/",
            "data/velo_prime_observability_latest.json",
        ],
        forbidden_paths=_FORBIDDEN,
        expected_artifacts=[
            "data/velo_prime_observability_latest.json",
        ],
        required_tests=[],
        max_runtime_seconds=600,
        approval_required=ApprovalRequirement.NONE,
        council_required=False,
        operator_required=False,
        stop_conditions=[
            "source_truth == SOURCE_UNKNOWN_BLOCK",
        ],
        notes="Shadow observation only. Scoring pipeline is not controlled by harness in this tier.",
    ),

    "PREFLIGHT_CHECK": TaskContract(
        mission_id="PREFLIGHT_CHECK",
        objective="Run pre-race preflight validation. Checks source truth, "
                  "credentials, and pipeline health before scoring begins.",
        task_type="PREFLIGHT",
        deployment_tier=DeploymentTier.SHADOW,
        allowed_commands=[
            "python scripts/ops/preflight_10am_check.py",
        ],
        allowed_read_paths=[
            "data/",
            "scripts/ops/",
            "src/velo/",
        ],
        allowed_write_paths=[
            "data/harness_returns/",
            "data/preflight_latest.json",
        ],
        forbidden_paths=_FORBIDDEN,
        expected_artifacts=[
            "data/preflight_latest.json",
        ],
        required_tests=[],
        max_runtime_seconds=120,
        approval_required=ApprovalRequirement.NONE,
        council_required=False,
        operator_required=False,
        stop_conditions=[],
        notes="Shadow mode preflight check.",
    ),
}


def get_contract(task_id: str) -> TaskContract:
    """Retrieve a registered contract by task ID. Raises KeyError if not found."""
    if task_id not in TASK_REGISTRY:
        raise KeyError(
            f"Task '{task_id}' is not registered in TASK_REGISTRY. "
            f"Available tasks: {sorted(TASK_REGISTRY.keys())}. "
            "No contract means no execution."
        )
    return TASK_REGISTRY[task_id]
