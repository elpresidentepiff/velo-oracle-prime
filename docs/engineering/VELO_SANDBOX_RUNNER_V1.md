# VÉLØ Sandbox Runner V1

**Status:** DESIGN ONLY  
**Phase:** 3 — Agent Operations  
**Classification:** `SANDBOX_SHADOW_ONLY` / `NO_LIVE_STATE_ACCESS` / `DESIGN_ONLY`

---

## Purpose

Disposable environments that can run audits, arena tests, feature builds, and reports without touching live state. Each sandbox is isolated, auditable, and destroyed after use.

---

## Sandbox Capabilities

A sandbox CAN:
- Read historical parquets and feature files
- Run arena tests and audit scripts
- Write report artifacts to `data/reports/` (read-only for live pipeline)
- Query Supabase read-only views
- Generate Council evidence packets
- Run LightGBM training on historical data (shadow only)
- Produce feature safety audits

A sandbox CANNOT:
- Touch `data/mission_control/latest.json`
- Write to `models/sqpe_v17/` or any live model path
- Set `consumed_live=true`
- Modify Telegram delivery scripts
- Access `scripts/app/run_prime_today.py` write paths
- Apply database migrations
- Promote models
- Mutate router/staking/Playbook G configuration

---

## Sandbox Types

### Type 1 — Arena Sandbox
Runs feature builds + LightGBM arena tests. Reads historical parquets. Writes arena reports. No Supabase access required.

```bash
# Example invocation pattern (future):
VELO_SANDBOX=true VELO_SANDBOX_TYPE=ARENA PYTHONPATH=. python scripts/audit_international_prerace_arena_v2.py
```

### Type 2 — Evidence Sandbox
Reads Supabase evidence corpus (read-only views). Produces signal analysis reports. Writes to `data/reports/` only.

### Type 3 — Replay Sandbox
Replays historical race days through policy world simulations. Reads from evidence corpus. Produces comparison reports. No live state access.

### Type 4 — Audit Sandbox
Reads codebase, model metadata, feature parquets. Produces governance documents. Cannot write to any runtime path.

---

## Isolation Contract

Every sandbox run must:
1. Start from a clean git worktree state (no uncommitted live-pipeline changes)
2. Write all outputs to a timestamped artifact directory
3. Produce an isolation audit log confirming no live paths were touched
4. Be destroyable without affecting live state

---

## Hard Invariants

```
SANDBOX_CANNOT_TOUCH_LIVE_STATE: enforced
SANDBOX_CANNOT_CONSUME_LEARNING: enforced
SANDBOX_CANNOT_PROMOTE_MODELS: enforced
SANDBOX_CANNOT_MUTATE_TELEGRAM: enforced
SANDBOX_CANNOT_MUTATE_ROUTER: enforced
SANDBOX_CANNOT_MUTATE_PLAYBOOK_G: enforced
SANDBOX_CANNOT_ACTIVATE_WORKERS: enforced
```

```
SANDBOX_RUNNER_V1_STATUS: DEFINED
ENFORCEMENT: DESIGN — implementation in Phase 3
```
