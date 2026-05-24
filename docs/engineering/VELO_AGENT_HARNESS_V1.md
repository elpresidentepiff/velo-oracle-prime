# VÉLØ Agent Harness V1

**Status:** DESIGN ONLY  
**Phase:** 3 — Agent Operations  
**Classification:** `AGENT_HARNESS_SHADOW_ONLY` / `NO_LIVE_MUTATION` / `DESIGN_ONLY`

---

## Purpose

Define the governance boundary for all automated agent activity within VÉLØ. Agents execute only approved jobs. No agent can unilaterally access live state, consume learning, promote models, or mutate the prediction pipeline.

---

## Ownership Model

| Role | Owner | Can |
|---|---|---|
| Task queue | Mission Control | Create, prioritise, cancel tasks |
| Approval gate | Council | Approve or veto agent actions above threshold |
| Blocking gate | Sentinel | Veto any action that violates hard rules |
| Execution | Workers / Claude Code | Execute only approved, scoped jobs |
| Audit trail | Evidence corpus | Read every artifact written by agents |

**No agent can approve its own tasks.** Every agent action that is live-adjacent requires a gate above it.

---

## Approved Agent Actions (no additional gate)

- Reading files and reports
- Writing design documents and analysis artifacts
- Running read-only audit scripts
- Querying Supabase read-only views
- Building feature parquets from historical data
- Running shadow arena tests
- Generating Council evidence packets

## Actions Requiring Council Gate

- Committing changes to `src/intelligence/` or `src/velo/weight_policy_registry.py`
- Updating model files in `models/`
- Applying database migrations
- Modifying any LIVE_RUNTIME script
- Activating any worker process

## Actions That Are Hard-Blocked (no gate can override)

- Writing `consumed_live=true`
- Modifying `models/sqpe_v17/sqpe_v17.pkl`
- Placing bets or orders (any path through `place_order()` or `place_bet()`)
- Setting `VELO_EXECUTION_MODE=LIVE` or `BETFAIR_MODE=LIVE`
- Pushing force to `main`
- Triggering Railway worker activation without explicit operator sign-off

---

## Harness Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Mission Control                    │
│           (task queue + command dispatch)            │
└────────────────────┬────────────────────────────────┘
                     │ approved tasks only
┌────────────────────▼────────────────────────────────┐
│                    Sentinel                          │
│           (hard-rule enforcement gate)               │
└────────────────────┬────────────────────────────────┘
                     │ passes if no hard rules violated
┌────────────────────▼────────────────────────────────┐
│              Agent / Claude Code                     │
│   (executes scoped task, writes artifact, reports)   │
└────────────────────┬────────────────────────────────┘
                     │ artifact written
┌────────────────────▼────────────────────────────────┐
│               Evidence Corpus                        │
│         (immutable audit trail of all outputs)       │
└─────────────────────────────────────────────────────┘
```

For live-adjacent tasks, Council approval is inserted between Mission Control and Sentinel.

---

## Artifact Contract

Every agent execution must produce an artifact:
- What was the task
- What was done
- What files were written
- What was NOT touched
- Commit hash(es)
- Classification label

An agent that produces no artifact has not completed the task.

---

## Sandbox Boundary

See `VELO_SANDBOX_RUNNER_V1.md` for disposable sandbox environments.

```
AGENT_HARNESS_V1_STATUS: DEFINED
ENFORCEMENT: DESIGN — implementation in Phase 3
```
