# RPDC Gate Implementation — First Slice Closure

**Classification:** `IMPLEMENTATION_CLOSURE`  
**Status:** FIRST_SLICE_COMPLETE  
**Date:** 2026-05-24  
**Authority:** El Presidente  
**Reference:** `docs/engineering/RPDC_SUPABASE_GATE_IMPLEMENTATION_PLAN.md`  
**Reference:** `docs/engineering/RPDC_DEGRADATION_SCOPE_AUDIT_2026_05_08_TO_2026_05_24.md`

---

## What Was Implemented

Three gates and one bug fix were implemented in the first approved slice. Code commits are in order below. No scoring changes, no model changes, no tier thresholds, no router/staking changes, no live-state mutation.

---

### Gate 6 — LEARNING_ELIGIBILITY_BLOCK
**Commit:** `1c3e07a`  
**File:** `scripts/ops/eod_shadow_learning_bridge.py`

Hard block on shadow learning consumption when a day's scoring run was degraded. The check runs before any sigma row is consumed into Playbook G shadow state.

**Three block conditions:**

| Condition | Reason code | Example date |
|---|---|---|
| improvement_score constant across all top picks | `IMPROVEMENT_SCORE_CONSTANT_AND_EXCLUDED` | May 20-24 |
| Any live-weighted component excluded on >80% of races | `LIVE_WEIGHTED_FEATURE_EXCLUDED` | — |
| Any individual race was SQPE-only (both live-weighted absent) | `SQPE_ONLY_ANOMALY_PARTIAL_DAY` | May 17 |
| All races were SQPE-only (>80% both excluded) | `SQPE_ONLY_DAY_MULTIPLE_LIVE_COMPONENTS_EXCLUDED` | — |

On block: writes `data/eod_flags_shadow_{date}.json` with block_reason, eligibility_details, and bridge_version. Returns without touching shadow state or outcome ledger.

Operator override: `--force-consume` flag logs at WARNING level and proceeds. Requires explicit operator approval.

**Test results (all BLOCK, all correct):**
```
2026-05-17  BLOCK  SQPE_ONLY_ANOMALY_PARTIAL_DAY          (6/30 races sqpe_only)
2026-05-20  BLOCK  IMPROVEMENT_SCORE_CONSTANT_AND_EXCLUDED
2026-05-21  BLOCK  IMPROVEMENT_SCORE_CONSTANT_AND_EXCLUDED
2026-05-24  BLOCK  IMPROVEMENT_SCORE_CONSTANT_AND_EXCLUDED
```

---

### Gate 5 — RPDC_COVERAGE_WARN
**Commit:** `7512875`  
**File:** `scripts/ops/build_rpdc_daily.py`

Pre-flight check at start of `build_rpdc_for_date()`. Queries `runner_release_candidates?order=run_date.desc&limit=1&select=run_date` and compares to scoring date.

- Stale >1 day: prints staleness count, repair command, logs WARNING
- Empty table: loud warn that RPDC has never been built

This gate would have fired every day from 2026-05-09 through 2026-05-24 — the 16-day chain break would have been visible from day 2.

**Implementation note:** Threshold set to >1 day (tighter than the plan's >3 days) to catch same-day staleness. The chain should never be more than 1 day behind — >1 day means a repair is needed.

---

### Task 4 — Dead Fallback Fix
**Commit:** `7512875`  
**File:** `scripts/ops/build_rpdc_daily.py`

The old fallback path (triggered when no `results_{date}.json` exists) queried `velo_verdicts.top_rank_horse_id` — a column that does not exist in the live schema. This has been silently returning 0 runners and the "No runners to score" message since the column was removed.

**Replaced with runner_snapshots JSONL loader:**
- Scans for `data/runner_snapshots_{date_tag}_*.jsonl` files
- Uses most-recent file if multiple exist for same date
- Deduplicates by `horse_id:race_id` key
- If no snapshots found: prints `RPDC_SOURCE_UNAVAILABLE` with exact paths checked, exits cleanly (no silent zero, no misleading "no runners" message)

The runner_snapshots JSONL files are written by `run_prime_today.py` on scoring day, so they are available same day after scoring completes. This means `build_rpdc_daily.py` can now be run on the same day after scoring, not just after results close.

---

### Gate 2 — FEATURE_DEGRADED_BANNER
**Commit:** `2af37d1`  
**File:** `scripts/ops/run_prime_today.py`

Post-scoring check in the Telegram delivery section. After the persist block and before race-by-race output, inspects `active_components` on all scored races.

If any live-weighted component (`improvement_score`, `market_deception_score`) was excluded on >80% of races, sends:

```
⚠ VÉLØ FEATURE_DEGRADED — <date>
──────────────────────────────────
  EXCLUDED: <component_name>
  Formula: <remaining active components> only
  Denominator used: <actual denom> (expected: 0.67)
  VP confidence inflated. Rankings within each race unchanged.
  B-tier: treat with reduced conviction.
  Learning from today BLOCKED until reconciliation closes.
```

Banner is sent immediately after pre-flight report as a separate Telegram message with label `FEATURE_DEGRADED_BANNER`.

This gate would have fired on every day from 2026-05-20 to 2026-05-24.

---

## What These Gates Do NOT Do

- They do not fix the improvement model feature gap (12 features still None — separate engineering task)
- They do not change scoring behavior or VP formula weights
- They do not change tier thresholds
- They do not affect sigma format
- They do not introduce new models or components
- They do not touch router, staking, Playbook G doctrine, or live state
- They do not retroactively repair any degraded day

---

## Gates Still Pending

| Gate | Name | Status | Reason pending |
|---|---|---|---|
| Gate 1 | `RPDC_ZERO_BLOCK_OR_WARN` | PENDING | Requires Telegram pre-flight write — Council approval needed |
| Gate 3 | `SUPABASE_PUBLISH_FALLBACK_WARN` | PENDING | Depends on Gate 4 investigation of decision_tier NULL |
| Gate 4 | `SUPABASE_WRITE_PROOF_REQUIRED` | PENDING | Requires investigation of decision_tier NULL root cause first |

---

## Historical Date Behavior — After These Gates

| Date | RPDC_COVERAGE_WARN | FEATURE_DEGRADED_BANNER | LEARNING_ELIGIBLE | Block reason |
|---|---|---|---|---|
| 2026-05-08 | Would fire (chain started here) | No | BLOCKED_PENDING_REVIEW | Predates active_components tracking |
| 2026-05-11 to 2026-05-16 | Would fire daily | No | CONDITIONALLY_ELIGIBLE | rpdc_tag_count=0 only |
| 2026-05-17 | Would fire | No | BLOCKED | SQPE_ONLY_ANOMALY_PARTIAL_DAY |
| 2026-05-18 to 2026-05-19 | Would fire | No | CONDITIONALLY_ELIGIBLE | rpdc_tag_count=0 only |
| 2026-05-20 | Would fire | YES — improvement excluded | BLOCKED | IMPROVEMENT_SCORE_CONSTANT_AND_EXCLUDED |
| 2026-05-21 | Would fire | YES — improvement excluded | BLOCKED | IMPROVEMENT_SCORE_CONSTANT_AND_EXCLUDED |
| 2026-05-22 | Would fire | YES — improvement excluded | BLOCKED | IMPROVEMENT_SCORE_CONSTANT_AND_EXCLUDED |
| 2026-05-23 | Would fire | YES — improvement excluded | BLOCKED | IMPROVEMENT_SCORE_CONSTANT_AND_EXCLUDED |
| 2026-05-24 | Would fire | YES — improvement excluded | BLOCKED | IMPROVEMENT_SCORE_CONSTANT_AND_EXCLUDED |
| 2026-05-25+ | PASS (chain repaired) | No (if improvement restored) | ELIGIBLE | Chain repaired 2026-05-24 |

---

## Open Items After This Slice

1. **Improvement model feature gap**: 12 input features (`mark_compression_score`, `or_vs_field`, `rpr_vs_field`, etc.) are all None since ~2026-05-20 because the RP PDF pipeline does not populate them. The Racing API was the source and was decommissioned 2026-05-14. No timeline set. Blocks full-formula VP from resuming.

2. **decision_tier NULL in velo_verdicts**: Root cause of Supabase dashboard publish fallback on May 24. Investigate persist mapping in `persist_race_predictions()` before implementing Gate 4.

3. **git_commit_sha NULL in velo_verdicts**: Audit traceability gap. Low priority.

4. **May 8-19 learning eligibility**: CONDITIONALLY_ELIGIBLE days require Council review. VP signal was intact (improvement_score varied) but RPDC tag context absent. Council decision required before any consumption.

---

```
CLOSURE_STATUS:                    FIRST_SLICE_COMPLETE
GATES_LIVE:                        Gate 2, Gate 5, Gate 6, Task 4 fallback fix
GATES_PENDING:                     Gate 1, Gate 3, Gate 4
COMMITS:                           1c3e07a, 7512875, 2af37d1
SCORING_CHANGES:                   NONE
MODEL_CHANGES:                     NONE
TELEGRAM_CHANGES:                  Gate 2 banner (approved)
RUNTIME_CHANGES:                   Active from next run (2026-05-25 morning)
NO_RESCORE:                        CONFIRMED
NO_LEARNING_CONSUMED:              CONFIRMED
NO_ROUTER_STAKING_CHANGES:         CONFIRMED
NO_LIVE_STATE_MUTATION:            CONFIRMED
```
