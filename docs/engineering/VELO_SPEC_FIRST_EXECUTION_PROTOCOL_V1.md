# VÉLØ Spec-First Execution Protocol V1

**Status:** DESIGN ONLY  
**Phase:** 1 — Governance Culture  
**Classification:** `SPEC_FIRST_PROTOCOL_REQUIRED` / `NO_RUNTIME_CHANGES_AUTHORISED`

---

## Purpose

Every build in VÉLØ must start with a spec. Not a plan. A spec.

A plan describes what you will do.  
A spec defines the conditions under which you must NOT do it.

The no-go conditions are more valuable than the implementation steps. They prevent half-finished builds, silent regressions, and live-state contamination before any code is written.

---

## Protocol Definition

### Step 1 — UNDERSTAND

Before writing a line of code, Claude/agent must demonstrate understanding by producing:
- What this change does
- What it touches in the live pipeline
- What it cannot touch
- What the rollback is
- What a contaminated result looks like

This is not optional. If an agent cannot answer these questions, it must ask the operator before proceeding.

### Step 2 — SPEC

Every task gets a spec block before execution:

```
TASK: <one-line description>
TOUCHES: <list of scripts, tables, models, pipelines affected>
CANNOT_TOUCH: <explicit list of protected components>
ROLLBACK: <how to undo this change>
NO_GO_CONDITIONS:
  - <condition that must stop execution>
  - <condition that must stop execution>
LIVE_ADJACENT: yes/no
SENTINEL_PREFLIGHT_REQUIRED: yes/no
```

### Step 3 — GATE

Before executing any live-adjacent task:
- Check `execution_guard.py` conditions
- Run preflight checks (`scripts/app/preflight_10am_check.py`)
- Confirm no dirty repo state (`scripts/maintenance/assert_canonical_worktree.py`)
- Confirm no SCORING_FLATLINE dates in scope

### Step 4 — EXECUTE

Execute the task as specified. No scope creep. No opportunistic refactors. No "while I'm in here" changes.

If execution reveals unexpected state (unfamiliar files, schema drift, unexpected values), STOP and report before continuing.

### Step 5 — VERIFY

After execution:
- Confirm the artifact was written
- Confirm no unintended files were modified (`git status --short`)
- Confirm no live scoring path was touched
- Run smoke test if applicable

### Step 6 — REPORT

Every task ends with:
- What was done
- Commit hash(es)
- Anything unexpected found
- Final classification (e.g., `AUDIT_EVIDENCE / READ_ONLY / NO_LIVE_MUTATION`)

---

## No-Go Condition Catalogue

These conditions must stop execution immediately:

| Condition | Stop Reason |
|---|---|
| Task touches `scripts/app/run_prime_today.py` | Live scoring path — operator approval required |
| Task modifies `src/intelligence/velo_prime_ensemble.py` weights | Live scoring — no changes without Council sign-off |
| Task reads or writes `models/sqpe_v17/sqpe_v17.pkl` | Live model — do not modify under any circumstance |
| Task touches Telegram delivery scripts | Format locked — operator sign-off required |
| Task writes to `data/mission_control/latest.json` manually | Should only be written by update_mission_control.py |
| Task contains `consumed_live=true` | HARD STOP — never set this without operator instruction |
| Task modifies `src/velo/weight_policy_registry.py` weights | Scoring change — no modifications without evidence gate |
| Date in scope is 2026-05-20 | SCORING_FLATLINE_CONTAMINATED — do not ingest, train, or promote |
| International migration SQL applied without sign-off | Gate violation — do not apply `intl_schemas_v1.sql` without approval |
| Model file written without versioning | Must increment version and preserve old file |

---

## Live-Adjacent Classification

Any task that could affect live prediction output must be classified before execution:

| Class | Definition | Required Gate |
|---|---|---|
| `LIVE_RUNTIME` | Directly executed in Railway scoring pipeline | Operator sign-off required |
| `LIVE_SUPPORT` | Imported by LIVE_RUNTIME | Impact analysis required |
| `SHADOW_ONLY` | Evidence accumulation, no scoring side-effects | Standard spec |
| `PAPER_EXECUTION` | Paper ledger / simulation — hard LIVE guard must be present | Verify guard before commit |
| `AUDIT_EVIDENCE` | Read-only audit scripts | Standard spec |
| `DESIGN_ONLY` | Documentation and design artifacts | No gate required |

---

## Sentinel Preflight

All `LIVE_RUNTIME` tasks require a Sentinel preflight pass:

```bash
# Before any live-adjacent execution:
source venv/bin/activate && PYTHONPATH=. python scripts/app/preflight_10am_check.py
source venv/bin/activate && PYTHONPATH=. python scripts/maintenance/assert_canonical_worktree.py
```

If either fails, do not proceed.

---

## Commitment to This Protocol

This protocol is not aspirational. It is mandatory.

If an agent (Claude Code or otherwise) executes a live-adjacent task without completing Steps 1–3 first, that is a protocol violation and must be flagged in the next report.

```
SPEC_FIRST_PROTOCOL_V1_STATUS: DEFINED
ENFORCEMENT: MANDATORY for all LIVE_RUNTIME and LIVE_SUPPORT tasks
DESIGN_ONLY_TASKS: Standard spec only
NO_EXCEPTIONS
```
