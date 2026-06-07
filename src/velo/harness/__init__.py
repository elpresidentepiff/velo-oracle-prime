"""
VÉLØ Agent Harness — src/velo/harness/
======================================
This package is the controlled execution envelope for VÉLØ.

Scope: VELO protection only.
  - Source truth and pipeline health
  - Scoring safety
  - Learning eligibility
  - Data contamination and recovery
  - Mission Control and Council evidence

Hard boundary: This package has NO dependency on Spotify, podcasts,
media generation, or publishing infrastructure. Those concerns belong
exclusively to the Media Ops Engine, which may read final approved
VELO truth artifacts but must never invoke, modify, or become part of
this harness.

Architecture:
  Mission Control creates task
        ↓
  Harness validates task and permissions  (contracts.py)
        ↓
  Sentinel applies hard rules             (sentinel.py)
        ↓
  Agent executes inside strict scope      (executor.py)
        ↓
  Harness verifies files, tests, artifacts (artifact_verifier.py)
        ↓
  Council judges completed execution      (execution_return.py)
        ↓
  Operator approves any live-adjacent action

Public API:
  from src.velo.harness.contracts import TaskContract, load_contract
  from src.velo.harness.sentinel import Sentinel
  from src.velo.harness.executor import HarnessExecutor
  from src.velo.harness.artifact_verifier import ArtifactVerifier
  from src.velo.harness.execution_return import ExecutionReturn
  from src.velo.harness.task_registry import TASK_REGISTRY
"""

from .contracts import TaskContract, load_contract
from .sentinel import Sentinel, SentinelViolation
from .executor import HarnessExecutor
from .artifact_verifier import ArtifactVerifier
from .execution_return import ExecutionReturn, Verdict
from .task_registry import TASK_REGISTRY

__all__ = [
    "TaskContract",
    "load_contract",
    "Sentinel",
    "SentinelViolation",
    "HarnessExecutor",
    "ArtifactVerifier",
    "ExecutionReturn",
    "Verdict",
    "TASK_REGISTRY",
]
