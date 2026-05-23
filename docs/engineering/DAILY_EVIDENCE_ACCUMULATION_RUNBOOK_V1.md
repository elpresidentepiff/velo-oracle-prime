# Daily Evidence Accumulation Runbook V1

**Date:** 2026-05-23  
**Status:** ACTIVE — evidence accumulation phase  
**Scope:** Post-Phase D clean operating protocol. No scoring, routing, staking, or model changes.

---

## Purpose

This runbook governs the daily operating sequence for VÉLØ during the evidence accumulation phase. The system is in a stable state. The task is not to build more features — it is to let evidence compound cleanly under governance.

**Current targets:**
- CPU Decision Policy Gate: 150 top-pick decisions (currently 87/150 — 63 needed)
- Race Shape V2 precision: 150 races minimum (currently 36/150)
- Innovation protocol corpus: accumulate without May 20 contamination

---

## Daily Operating Sequence

Run in order after results close each day.

### Step 0 — Prerequisites

```bash
cd /mnt/c/Users/puror/velo-oracle-prime
source venv/bin/activate
```

All scripts run with `PYTHONPATH=.` prefix.

---

### Step 1 — Sigma Artifact (Results Close)

```bash
PYTHONPATH=. python scripts/run_results_sigma.py --date YYYY-MM-DD
```

**What it does:** Downloads results, computes SR/frame/win metrics, writes `data/sigma_results/sigma_results_YYYY_MM_DD.json` and `data/results_YYYY_MM_DD.json`.

**Gate:** Must complete before any learning eligibility steps.

**Governance:**
- ALWAYS use `scripts/run_results_sigma.py`. NEVER use `close_sigma_loops.py`.
- Telegram format is locked — never change it.

---

### Step 2 — Ingest Results

```bash
PYTHONPATH=. python scripts/ops/ingest_results_to_horse_runs.py --date YYYY-MM-DD
```

**What it does:** Upserts results into `racing_horse_runs` Supabase table. Feeds tomorrow's RPDC.

---

### Step 3 — Identity + Flatline Audit (Learning Gate Check)

```bash
PYTHONPATH=. python scripts/audit_20260522_learning_eligibility.py --date YYYY-MM-DD
```

**What it does:** Classifies every verdict race as eligible or excluded. Checks all hard-stop conditions.

**Gate:** If `audit_status != ELIGIBLE`, do not proceed to Steps 4–7.

**Hard stops (exit 1 if any fire):**
- `flatline_count > 0`
- `identity_failures > 0`
- `council_verdict != PASS_TO_LEARNING`
- `consumed_live > 0`
- Any row unresolved

**Output:** `data/reports/YYYY-MM-DD_learning_eligibility.json/.md`

---

### Step 4 — Build Shadow Events (Phase 3A)

```bash
PYTHONPATH=. python workers/velo_ops_worker.py learn-shadow --date YYYY-MM-DD --execute --target-state shadow_full_train_v2
```

**What it does (Phase 3A):** Builds learning events in `velo_learning_events`. Sets `consumed_shadow=False`. Does NOT touch the shadow brain.

**Check:** Verify `sentient_state_touched=False` in ops artifact.

**Output:** `data/ops_worker_dry_run/YYYY-MM-DD_learn-shadow_*.json`

---

### Step 5 — Shadow Consume (Phase 3B) — OPERATOR DECISION REQUIRED

Phase 3B must be explicitly approved before running. Check the ops artifact from Step 4 confirms `build_events_only=True` and all gates pass.

**Approval command (after operator confirmation):**

```bash
PYTHONPATH=. python workers/velo_ops_worker.py learn-shadow --date YYYY-MM-DD --execute --target-state shadow_full_train_v2
```

**What it does (Phase 3B):** Reads unconsumed events, feeds them into `sentient_state_shadow_full_train_v2.json`, sets `consumed_shadow=True`.

**Hard constraints:**
- `consumed_live` must remain 0 on all rows
- `sentient_state.json` (live scoring) must not be touched
- May 20 events must never be consumed — they carry `SCORING_FLATLINE_CONTAMINATED` classification

---

### Step 6 — Innovation Protocol Corpus Append

```bash
PYTHONPATH=. python scripts/ops/build_innovation_protocol.py --date YYYY-MM-DD
```

**What it does:** Appends new verdict rows to `data/velo_innovation_protocol_1k_deduped.csv`.

**Hard constraint:** Never run for 2026-05-20. May 20 rows must remain 0 in the corpus.

---

### Step 7 — RPDC Tags (Next Morning)

Run the morning after results ingest, before the next scoring run:

```bash
PYTHONPATH=. python scripts/build_rpdc_daily.py --date YYYY-MM-DD
```

---

### Step 8 — Race Shape Features + Shadow Ledger

```bash
PYTHONPATH=. python scripts/build_race_shape_features.py --date YYYY-MM-DD
PYTHONPATH=. python scripts/build_race_shape_shadow_ledger.py --date YYYY-MM-DD
```

**Output:** `data/features/race_shape_features_latest.json`, `data/reports/race_shape_shadow_ledger_latest.json/.md`

**Note:** `data/features/*.json` is gitignored. The MD report is committable.

---

### Step 9 — CPU Gate V2 Refresh

```bash
PYTHONPATH=. python scripts/build_cpu_shadow_gate_v2.py
```

**Output:** `data/reports/cpu_shadow_gate_v2_latest.json`

**Watch:** `top_pick_decisions` count toward 87 → 150 (first gate).

---

### Step 10 — Race Shape Precision Tracker

```bash
PYTHONPATH=. python scripts/track_race_shape_precision.py --date YYYY-MM-DD
```

**Output:** `data/reports/race_shape_precision_tracker_latest.json/.md`

**Watch:** FAV_VULN_ULTRA_COMPRESSED and MIDPRICE_TRAP counts toward 150.

---

### Step 11 — CPU Decision Policy Tracker

```bash
PYTHONPATH=. python scripts/track_cpu_gate_v2_decision_policy.py
```

**Output:** `data/reports/cpu_gate_v2_decision_policy_tracker_latest.json/.md`

---

### Step 12 — Mission Control Refresh

```bash
PYTHONPATH=. python scripts/ops/update_mission_control.py --date YYYY-MM-DD
```

**Output:** `data/mission_control/YYYY-MM-DD_mission_control.json`, `data/mission_control/latest.json`

**Review:** Confirm `next_safe_command = "Green — safe to proceed with daily evidence accumulation."` before closing.

---

## Evidence Accumulation Targets

| Target | Current | Gate 1 | Gate 2 | Status |
|---|---|---|---|---|
| CPU Decision Policy — top picks | 87 | 150 | 300 | NEEDS_MORE_DAYS |
| Race Shape corpus | 36 | 150 | 300 | ACCUMULATING |
| FAV_VULN_ULTRA_COMPRESSED | 16 | 50 | 150 | PROVISIONAL |
| MIDPRICE_TRAP | 5 | 20 | 50 | PROVISIONAL |
| Innovation Protocol | 1,018 | — | — | ACTIVE |

---

## Gate Promotion Rules (PERMANENT)

```
CPU Decision Policy Gate:
  At n=150:     First review — SR, Brier, top-decile analysis. NOT automatic promotion.
  At n=300:     Full policy review. NOT automatic promotion.
  Promotion:    Operator decision required at every gate. Evidence is presented, not actioned.

Race Shape V2:
  At n=150:     First precision review — SR per subset, stability check.
  At n=300:     Quartile SR analysis + V2 warn criteria discussion.
  Actionable:   Only after 300+ corpus AND operator decision.

Model Promotion:
  NOT APPROVED until all gates met and operator explicitly approves.
  No gate passage is automatic.
```

---

## Hard Governance Constraints (PERMANENT — never modify)

```
No scoring changes applied to live pipeline
No VP model changes
No candidate_route() changes
No router rule changes
No staking changes
No Telegram runtime changes (format locked)
No Playbook G promotion
No live-state mutation (sentient_state.json hash must remain 1016d89dceb28da5)
No consumed_live=true on any learning event row
May 20 (2026-05-20): SCORING_FLATLINE_CONTAMINATED — quarantine/forensic only
  - Must not enter innovation protocol
  - Must not enter shadow learning
  - Must not enter CPU gate evidence
  - May 20 rows in corpus must remain 0
All credentials in .env — never hardcode, never commit
Sigma: ALWAYS run_results_sigma.py. NEVER close_sigma_loops.py.
```

---

## Quick Status Check

Read current system state without running anything:

```bash
cat data/mission_control/latest.json | python3 -c "
import json, sys
mc = json.load(sys.stdin)
print('date:', mc.get('date'))
print('learning_gate:', mc.get('learning_gate_status'))
print('shadow_v2_races:', mc.get('shadow_consume_idempotency', {}).get('shadow_train_v2_race_count'))
print('cpu_decisions:', mc.get('decision_policy_gate_top_picks'))
print('next:', mc.get('next_safe_command'))
"
```
