# VCP-03 — VÉLØ Coherence Burn-In Protocol

**Started:** 2026-06-29 | **Target:** 10 passing days | **Status:** IN PROGRESS

## Daily command pair (run every operating day)

```bash
PYTHONPATH=. venv/bin/python scripts/ops/build_velo_living_state.py
PYTHONPATH=. venv/bin/python scripts/ops/build_velo_heartbeat.py
PYTHONPATH=. venv/bin/python scripts/ops/build_vcp03_burn_in_log.py
```

## What counts as a passing day

A day passes VCP-03 if ALL of the following are true:

| Check | Required value |
|---|---|
| Living state generated | Yes |
| Heartbeat generated | Yes |
| Truth lock | LOCKED |
| A-3 going_code | FIXED |
| VFU-20 signed off | True |
| VFU-21 gate | CLOSED |
| Memory capture | OPEN |
| Failure learning | OPEN |
| Promotion learning | GATED or ELIGIBLE (not UNKNOWN, not blank) |
| Contradictions counted | Yes (even if 0) |
| Missing artifacts resolve to | UNKNOWN (not CLEAN) |
| Forbidden actions present | Yes |

Promotion can be GATED and the day still passes. The burn-in proves honesty, not clean lights.

## What fails a day

- Living state or heartbeat not generated
- Truth lock not LOCKED
- Any value defaulting to CLEAN when it should be UNKNOWN
- Promotion learning left blank or UNKNOWN
- Contradictions not counted
- VFU-21 gate opened without operator approval
- Any forbidden action removed from the list

## Hard rules for the burn-in period

```
NO_VFU_21_START
NO_CASE_MEMORY_BUILD
NO_DEEPSEARCHER_BUILD
NO_RANDOM_FOREST_SCOUT
NO_AGENT_BROWSER_BUILD
NO_MODEL_PROMOTION
NO_LIVE_SCORING_CHANGE
NO_VP_THRESHOLD_CHANGE
NO_SUPABASE_WRITES
NO_TELEGRAM_SEND
REPORT_ONLY
```

## After 10 passing days

Operator reviews `data/reports/vcp_03_burn_in_log.md`.  
If 10/10 days pass: VCP-04 Shadow Judgment authorised.  
If any day fails: investigate cause, fix, restart the count.

## Tracker

`data/reports/vcp_03_burn_in_log.json` — machine-readable append-only log  
`data/reports/vcp_03_burn_in_log.md` — operator-facing daily summary
