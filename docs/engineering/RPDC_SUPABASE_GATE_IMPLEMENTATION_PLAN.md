# RPDC and Supabase Gate Implementation Plan

**Classification:** `IMPLEMENTATION_PLAN_PARTIAL_COMPLETE`  
**Status:** FIRST_SLICE_IMPLEMENTED — Gates 2, 5, 6 + Task 4 live. Gates 1, 3, 4 pending.  
**Date:** 2026-05-24  
**Updated:** 2026-05-24 (first implementation slice committed)  
**Authority:** El Presidente  
**Reference:** `docs/engineering/MAY24_SUPABASE_RPDC_INCIDENT_AUDIT.md`  
**Reference:** `docs/engineering/RPDC_DEGRADATION_SCOPE_AUDIT_2026_05_08_TO_2026_05_24.md`  
**Council queue:** Priority 0 — `docs/engineering/V14_COUNCIL_ACTION_QUEUE.md`

---

## Purpose

This document proposes implementation for the six safety gates identified in the May 24 degraded-run incident. Gates 2, 5, 6 and the Task 4 dead-fallback fix were implemented in the first approved slice (2026-05-24). Gates 1, 3, 4 remain pending Council approval before implementation.

---

## Background

The 2026-05-24 scoring run was classified `OFFICIAL_VALID_FEATURE_DEGRADED`. Seven conditions that should have produced operator warnings or blocks fired silently. This is not a scoring failure — it is a Mission Control silence failure. The system did not scream when it should have.

The six gates below address the seven silence failures identified in the audit.

---

## Proposed Gate Specifications

### Gate 1 — `RPDC_ZERO_BLOCK_OR_WARN`

**Trigger:** `build_rpdc_daily.py` returns 0 runners for today's date  
**File to modify:** `scripts/ops/build_rpdc_daily.py`  
**Proposed action:**
```python
if not runners_to_score:
    # Existing: print("  No runners to score.")
    # Add:
    warn_text = (
        f"⚠ RPDC PRE-FLIGHT WARN — {date_str}\n"
        f"build_rpdc_daily returned 0 runners. RPDC unavailable.\n"
        f"If improvement_score becomes constant across field, it will be excluded from VP.\n"
        f"Operator review required before scoring."
    )
    # Log to mission_control.json
    # Send to Telegram pre-flight channel
```
**Does NOT block scoring** — improvement_score exclusion is correct ensemble behavior. The gate warns the operator before the run so they can choose to investigate.  
**Operator approval required:** YES (Telegram write + mission_control write)

---

### Gate 2 — `FEATURE_DEGRADED_BANNER` ✓ IMPLEMENTED (commit 2af37d1, 2026-05-24)

**Trigger:** Any live-weighted component (`improvement_score`, `market_deception_score`, `sqpe_v17`) excluded from active_components across more than 80% of races in a day  
**File to modify:** `scripts/ops/run_prime_today.py` — post-scoring summary section  
**Proposed action:**
```python
# After scoring, before Telegram send:
degraded_components = []
for comp in ['improvement_score', 'market_deception_score']:
    excluded_count = sum(1 for r in race_results if comp in r.get('excluded_from_ensemble', []))
    if excluded_count / len(race_results) > 0.80:
        degraded_components.append(comp)

if degraded_components:
    banner = (
        f"⚠ FEATURE_DEGRADED: {', '.join(degraded_components)} excluded from ensemble "
        f"on {excluded_count}/{len(race_results)} races. VP formula operating on reduced components."
    )
    # Prepend to day posture Telegram message
    # Log to mission_control.json with FEATURE_DEGRADED classification
```
**This gate would have fired on 2026-05-20 to 2026-05-24.**  
**Operator approval required:** YES (Telegram format change)

---

### Gate 3 — `SUPABASE_PUBLISH_FALLBACK_WARN`

**Trigger:** `publish_daily_predictions_to_dashboard.py` logs `SOURCE USED: local_json_top_only`  
**File to modify:** `scripts/ops/publish_daily_predictions_to_dashboard.py`  
**Proposed action:**
```python
if source_used == "local_json_top_only":
    warn_text = (
        f"⚠ DASHBOARD FALLBACK — {date_str}\n"
        f"Dashboard publisher used local JSON fallback (Supabase read unavailable).\n"
        f"Dashboard reflects local artifact, not live DB state.\n"
        f"Root cause: check decision_tier NULL in velo_verdicts."
    )
    # Log to mission_control.json
    # Send Telegram warning to ops channel
```
**Does NOT affect predictions** — content is the same either way. Gate ensures operator knows the dashboard is in fallback state.  
**Operator approval required:** YES

---

### Gate 4 — `SUPABASE_WRITE_PROOF_REQUIRED`

**Trigger:** After every `persist_race_predictions` call  
**File to modify:** `app/services/velo_prime_service.py` or `scripts/ops/run_prime_today.py` — persistence reporting section  
**Proposed action:**
```python
# After persist batch:
verify_count = sb_get(f"/velo_verdicts?generated_at=gte.{date_str}T00:00:00&select=id,decision_tier")
written_count = len(verify_count)
null_tier_count = sum(1 for r in verify_count if r.get('decision_tier') is None)

# Log to mission_control.json:
{
    "supabase_write_proof": {
        "date": date_str,
        "expected": races_scored,
        "actual": written_count,
        "null_decision_tier": null_tier_count,
        "status": "WARN" if null_tier_count > 0 else "PASS"
    }
}

if null_tier_count > 0:
    # Secondary warn in Telegram persistence report
    # "⚠ PERSIST_SECONDARY_WARN: {null_tier_count} rows have decision_tier=NULL"
```
**Secondary issue** — null decision_tier is the root cause of the Supabase read fallback on the dashboard. This gate would have identified it immediately after persist.  
**Operator approval required:** YES

---

### Gate 5 — `RPDC_COVERAGE_WARN` ✓ IMPLEMENTED (commit 7512875, 2026-05-24)

**Trigger:** `runner_release_candidates` latest `run_date` is more than 1 day behind scoring date (implemented threshold: >1 day; plan said 3, tightened on implementation)  
**File to modify:** `scripts/ops/build_rpdc_daily.py` — pre-flight section  
**Proposed action:**
```python
# Before scoring loop:
latest = sb_get("/runner_release_candidates?order=run_date.desc&limit=1&select=run_date")
if latest:
    latest_date = date.fromisoformat(latest[0]['run_date'])
    days_stale = (date.fromisoformat(date_str) - latest_date).days
    if days_stale > 3:
        warn_text = (
            f"⚠ RPDC COVERAGE WARN — {date_str}\n"
            f"runner_release_candidates last updated {latest_date} ({days_stale} days stale).\n"
            f"RPDC history may be incomplete. Run ingest_results_to_horse_runs to repair chain."
        )
        # Log to mission_control.json daily
        # This gate would have fired every day since 2026-05-08
```
**This gate would have caught the 16-day drift.** Daily warn accumulation would have made the chain break visible.  
**Operator approval required:** YES

---

### Gate 6 — `LEARNING_ELIGIBILITY_BLOCK` ✓ IMPLEMENTED (commit 1c3e07a, 2026-05-24)

**Trigger:** sigma day where `improvement_score` was constant, OR any live-weighted component excluded on >80% of races, OR any individual race fired SQPE-only (partial contamination anomaly)  
**File to modify:** `scripts/ops/eod_shadow_learning_bridge.py`  
**Proposed action:**
```python
# Before consuming sigma rows:
sigma_rows = load_sigma_csv(date_str)
imp_vals = set(r.get('improvement_score') for r in sigma_rows if r.get('improvement_score'))
is_constant = len(imp_vals) <= 1

if is_constant:
    raise ValueError(
        f"LEARNING_BLOCKED — {date_str}: improvement_score was constant ({imp_vals}). "
        f"This sigma day used a degraded VP formula. "
        f"Learning consumption blocked until improvement model features are restored and "
        f"Council approves consumption from this window."
    )
```
**Hard block** — prevents any degraded sigma day from entering the learning bridge without explicit operator override.  
**Currently the only gate that is a BLOCK rather than a WARN.**  
**Operator approval required:** YES

---

## Additional Fix Required (not a gate)

### `build_rpdc_daily.py` — fix velo_verdicts fallback ✓ IMPLEMENTED (commit 7512875, 2026-05-24)

The fallback path when no results file exists queried `velo_verdicts.top_rank_horse_id` — a column that does not exist in the live schema. This meant the fallback had never worked.

**Implemented fix:** Replaced with runner_snapshots JSONL loader. The JSONL files are written by `run_prime_today.py` on scoring day and contain all runners from that day's scoring run. Deduplication by `horse_id:race_id` key. If no snapshots exist either, the script now prints `RPDC_SOURCE_UNAVAILABLE` with the exact paths checked and exits cleanly (no silent zero).

---

## Implementation Priority Order

1. **Gate 6** (LEARNING_ELIGIBILITY_BLOCK) — hard block, protects evidence integrity. Lowest risk.
2. **Gate 5** (RPDC_COVERAGE_WARN) — prevents silent drift. Read-only check added to build_rpdc_daily.
3. **Gate 2** (FEATURE_DEGRADED_BANNER) — most visible operator impact. Telegram format change.
4. **Gate 1** (RPDC_ZERO_BLOCK_OR_WARN) — companion to Gate 5 at run time.
5. **Gate 4** (SUPABASE_WRITE_PROOF_REQUIRED) — resolve decision_tier NULL puzzle first.
6. **Gate 3** (SUPABASE_PUBLISH_FALLBACK_WARN) — lowest urgency, depends on Gate 4 resolution.

---

## What These Gates Do NOT Do

- They do not fix the improvement model feature gap (separate engineering task)
- They do not change scoring behavior
- They do not change tier thresholds or weights
- They do not affect sigma format
- They do not introduce new models or components
- They do not touch router, staking, Playbook G, or live state

---

## Council Approval Required For

All six gates require Council approval before any implementation begins (per V14 Standing Rules). The gates modify Telegram output and mission_control.json writes, both of which are protected under the Council action queue standing rules.

```
PLAN_STATUS:          FIRST_SLICE_IMPLEMENTED
GATES_IMPLEMENTED:    Gate 2 (FEATURE_DEGRADED_BANNER), Gate 5 (RPDC_COVERAGE_WARN),
                      Gate 6 (LEARNING_ELIGIBILITY_BLOCK), Task 4 (dead fallback fix)
GATES_PENDING:        Gate 1 (RPDC_ZERO_BLOCK_OR_WARN), Gate 3 (SUPABASE_PUBLISH_FALLBACK_WARN),
                      Gate 4 (SUPABASE_WRITE_PROOF_REQUIRED)
COMMITS:              1c3e07a (Gate 6), 7512875 (Gate 5 + Task 4), 2af37d1 (Gate 2)
CODE_CHANGES:         eod_shadow_learning_bridge.py, build_rpdc_daily.py, run_prime_today.py
SCORING_CHANGES:      NONE
MODEL_CHANGES:        NONE
TELEGRAM_CHANGES:     Gate 2 banner added (approved)
RUNTIME_CHANGES:      Gates active from next run
```
