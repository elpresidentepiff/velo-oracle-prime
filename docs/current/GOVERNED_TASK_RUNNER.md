# VÉLØ Governed Task Runner

**Date:** 2026-06-11
**Status:** ACTIVE
**Classification:** OPS_ORCHESTRATION

## 1. Purpose

The Governed Task Runner is the unified orchestration layer for VÉLØ operations. It chains the Worktree Safety Runner, the Task Contract Runner, and the Side-Effect Sentinel into a single mandatory command. This ensures that every agent task is automatically audited against repository state, mission scope, and production risks.

## 2. Governed Workflow

1. **Worktree Safety Check:** Verifies the repo is clean and on the correct branch/commit.
2. **Task Contract Preflight:** Validates the task manifest before work begins.
3. **Side-Effect Sentinel Audit:** Inspects the intended command for production risks.
4. **Command Execution:** Runs the task command through the Side-Effect Sentinel in `run` mode.
5. **Final Task Contract Audit:** Verifies that the work performed stayed within the declared scope.

## 3. Mandatory Usage

Raw agent commands are now **DEPRECATED**. All tasks must be executed via the Governed Task Runner:

```bash
python scripts/ops/governed_task_runner.py \
  --expected-branch stabilization/prime-hardening-v1 \
  --contract ops/task_contracts/MISSION_ID.json \
  -- [COMMAND]
```

## 4. Artifacts

The runner writes its full execution trace to:
`data/current/governed_task_latest.json`

This artifact provides the definitive record of the mission's safety and scope compliance.

---
*NO NEW LOOP BUILD APPROVED YET — INVENTORY FIRST.*
