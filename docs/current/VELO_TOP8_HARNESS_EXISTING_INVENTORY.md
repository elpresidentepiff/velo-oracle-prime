# VÉLØ TOP 8 LOOP / HARNESS INVENTORY AUDIT

**Date:** 2026-06-10
**Status:** AUDIT_COMPLETE
**Target:** stabilization/prime-hardening-v1

## 1. Executive Summary

The VÉLØ ORACLE PRIME repository contains a significant amount of "harness" and "loop" infrastructure, but it is currently fragmented across three generations: 
1. **The Legacy API Era** (abandoned but still present in `app/agents/`).
2. **The Post-API Script Era** (live-active, high-level orchestrators like `run_velo_closed_loop_daily.py`).
3. **The New Harness Era** (partially implemented in `src/velo/harness/`, defining the `TaskContract` and `Sentinel` standards).

**Existing:** A world-class `Sentinel` and `TaskContract` system exists but is currently "unplugged" from the daily run. Worktree safety checks are enforced via `assert_canonical_worktree.py`.
**Partial:** Playwright capture exists but lacks automated "proof" artifacts (screenshots/DOM dumps) in the standard pipeline. ML hygiene is present in `new_build/` but not yet universal.
**Missing:** A dedicated "Autonomous Coding Loop" (agent worktree isolation for code changes) and formal "eval suites" for agent behavior beyond unit tests.
**Duplicated:** There are multiple "harness" runners (`run_harness.py`, `run_agent_harness.py`, `velo_daily_harness.py`) with overlapping responsibilities.
**Dangerous:** Commit history contains credentials; Railway env dumps at root remain a high risk.
**Next:** Consolidate orchestrators into the `src/velo/harness` standard and implement the "Autonomous Coding Loop" safety manifest.

## 2. League Table

Upgrade| Existing status| Evidence files| Current strength| Current weakness| Action
---|---|---|---|---|---
1. Self-Harness / RHO | EXISTS_PARTIAL | `docs/current/VELO_RHO_PROTOCOL.md`, `hackathon/amd_harnessguard/` | Strong theoretical framework | Not wired to live failure events | Consolidate RHO mining into `sigma_results`
2. Autonomous Coding Loop | MISSING | — | `TaskContract` supports it | No runner exists | Build isolated worktree runner
3. Design the loop, not prompt | EXISTS_PARTIAL | `scripts/ops/velo_daily_harness.py`, `TaskContract` | Multi-stage script orchestration | Fragments across scripts/docs | Unified `loop_registry.json` migration
4. Closed loops vs open loops | EXISTS_LIVE | `scripts/ops/run_velo_closed_loop_daily.py` | Order of execution enforced | Manual trigger only | Wire to Railway healthz
5. Six agent reliability techniques | EXISTS_PARTIAL | `src/velo/harness/sentinel.py`, `tests/test_agent_harness.py` | `Sentinel` hard rules | `Reflection` is doc-only | Implement on-runner reflection gate
6. Playwright capture hardening | EXISTS_PARTIAL | `scripts/ops/racing_post_account_collector.py` | Bypasses anti-bot | No automated visual proof | Add screenshot/DOM artifact write
7. Worktree safety standard | EXISTS_LIVE | `scripts/ops/assert_canonical_worktree.py`, `docs/engineering/VELO_NEXUS_WORKTREE_REGISTRY.md` | Strict canonical enforcement | No rollback automation | Add "Worktree Cleanup" script
8. ML production hygiene | EXISTS_PARTIAL | `new_build_velo/evaluator.py`, `data/new_build/` | Clean train/val/test splits | sqpe_v17 has high leakage risk | Deprecate v17 for Core_V0

## 3. Existing Assets Found

- `src/velo/harness/sentinel.py` — Final permission gate enforcing hard rules (branch, mode, forbidden cmds).
- `src/velo/harness/contracts.py` — `TaskContract` definition for agent missions.
- `src/velo/harness/executor.py` — Harness executor that validates contracts and runs steps.
- `src/velo/harness/artifact_verifier.py` — Post-run check for expected files.
- `scripts/ops/assert_canonical_worktree.py` — Hard-stop script if running from OneDrive/stale worktrees.
- `scripts/ops/velo_daily_harness.py` — High-level daily orchestrator (morning/close/full).
- `scripts/ops/run_velo_closed_loop_daily.py` — Daily closure orchestrator with error detection and MD reporting.
- `scripts/ops/update_mission_control.py` — Refreshes `data/mission_control/latest.json` gates.
- `data/current/loop_registry.json` — Machine-readable status of active loops.
- `docs/current/VELO_RHO_PROTOCOL.md` — Law governing Retrospective Harness Optimization.
- `docs/engineering/VELO_NEXUS_WORKTREE_REGISTRY.md` — Definitive list of allowed worktree paths.
- `new_build_velo/evaluator.py` — Sandbox evaluator for new model versions.

## 4. Duplication Map

- **Harness Runners:** `scripts/ops/velo_daily_harness.py`, `scripts/run_harness.py`, `scripts/run_agent_harness.py`. (Consolidate into `velo_daily_harness.py` using `TaskContract`).
- **Loop Orchestrators:** `run_velo_closed_loop_daily.py` vs `velo_daily_harness.py --mode close`. (Consolidate into a single daily OS runner).
- **Proof/Check scripts:** `scripts/ops/velo_session_start_check.py`, `scripts/ops/assert_canonical_worktree.py`, `scripts/ops/check_loop_health.py`. (Consolidate into `velo-prime-preflight`).

## 5. Missing Pieces

- **Missing:** Isolated Worktree Safety Runner.
  - **Smallest addition:** A `scripts/harness/init_worktree_task.sh` that creates a temporary git worktree, copies `.env`, and writes a `task_manifest.json` before handing over to the agent.
- **Missing:** Playwright Visual Proof.
  - **Smallest addition:** Update `racing_post_account_collector.py` to optionally save `page.screenshot()` and `page.content()` to `data/capture_proof/` on every run.
- **Missing:** Agent Reflection Gate.
  - **Smallest addition:** A `src/velo/harness/reflection.py` that asks the agent to review its own `execution_return.py` output against the `TaskContract` before committing.

## 6. Risk Register

Risk | Why it matters | Current protection | Missing protection | Priority
---|---|---|---|---
Silent Capture Failure | Morning scoring runs on stale or empty data | Human review of logs | Automated DOM/Screenshot verification | P0
Dirty Worktree Contamination | Experiments leak into main/production | `assert_canonical_worktree.py` | Automated rollback on failure | P0
Credential Exposure | Public repo contains API keys in history | `.env` is ignored | Repository history cleaning (BFG/Filter-repo) | P1
ML Leakage (sqpe_v17) | System overestimates confidence | None (frozen model) | Core_V0 promotion | P1

## 7. Recommended Build Order

### P0: Operational Stability
1. **Hardened Capture Proof:** Save screenshots/DOM on every RP capture to prevent "blind scoring".
2. **Worktree Safety Runner:** Automate the creation of clean worktrees for agent coding tasks.
3. **Consolidate Preflight:** Merge canonical checks, session starts, and loop health into one "Preflight" command.

### P1: Reliability & Hygiene
4. **Agent Reflection Loop:** Implement the final "did I fulfill the contract?" gate in the `Executor`.
5. **RHO Mining Pipeline:** Automate the extraction of failure patterns from `sigma_results` into `rho_candidate_failures.json`.
6. **Core_V0 Promotion:** Replace sqpe_v17 with a validated, hygiene-compliant model.

### P2: Autonomy
7. **Autonomous Coding Loop:** Full schedule-to-PR workflow using isolated worktrees.
8. **Layered Memory:** Integrate vector-based episodic memory (KNN) into the live prediction path.

---

NO NEW LOOP BUILD APPROVED YET — INVENTORY FIRST.
