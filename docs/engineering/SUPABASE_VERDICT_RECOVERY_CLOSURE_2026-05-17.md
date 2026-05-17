# SUPABASE VERDICT RECOVERY — CLOSURE DECISION

**Classification:** CATEGORY_A_RECOVERY_EXHAUSTED | SUPABASE_VERDICT_RECOVERY_NOT_USEFUL | 1310_SAFE_TRAINING_SLICE_ACCEPTED | GROWTH_PATH_DAILY_ACCUMULATION | NO_PHASE_B_EXECUTION
**Date:** 2026-05-17
**Script:** `scripts/recover_supabase_verdicts_to_local.py` (commit 19893ed)
**Operator decision:** Dry-run accepted. Phase B rejected. Closure locked.

---

## What We Found

The exclusion audit (commit 5cc1fd0) documented a 2051 → 1310 training-safe gap,
identifying Category A as "sigma rows from dates where no local verdict JSON exists —
these days were scored on Railway but verdicts live in Supabase."

The dry-run recovery script (19893ed) tested that assumption directly against the live
Supabase database.

**Reality discovered:**

| Layer | Finding |
|---|---|
| Supabase `velo_verdicts` | Only holds **2026-04-22 to 2026-05-17** (21 dates) |
| All 21 velo_verdicts dates | Already have local verdict JSONs — zero new data |
| Phase A only candidate | 2026-04-26: 22 races, FULL signal fidelity, **no local results file** → 0 training-safe |
| Pre-April-22 Railway data | **Not in Supabase velo_verdicts** — was never written there |

The core assumption was wrong. The Railway scoring did not persist full-analysis verdict
data to Supabase velo_verdicts for early race days. The early Railway rows (Jan–April 21)
exist in sigma_audits as post-race audit records but not as recoverable prediction
feature rows.

---

## Phase B — Why It Is Rejected

Phase B (sigma_audits notes reconstruction) would extract `velo_prime_prob` from text
summaries in the sigma_audits `notes` field for 10 dates / 301 races.

**What Phase B would produce:**

| Field | Status |
|---|---|
| velo_prime_prob | Available (parsed from text) |
| market_deception_score | **null** — not in sigma_audits |
| improvement_score | **null** — not in sigma_audits |
| place_prob | **null** — not in sigma_audits |
| decision_tier | Available |
| result_matched | Available (local results exist for these dates) |

**Why Phase B fails the training standard:**

Category G exclusion filter: "Rows missing 3+ of 4 key signal fields (VP, MDS, improvement, place_prob)"
→ 3 of 4 are null → 301 rows would be **Category G'd from training**

**Net training-safe lift from Phase B:** 0 rows.

VÉLØ does not need a bigger number. It needs clean signal truth. Polluting the corpus
with 301 rows that inflate the count but never reach the training slice is noise, not evidence.

**Decision: NO_PHASE_B_EXECUTION. Final.**

---

## What Is Unrecoverable

| Category | Rows | Root Cause |
|---|---|---|
| Pre-2026-04-22 Railway dates | ~319 rows | velo_verdicts not active/instrumented in early Railway phase |
| 2026-03-19, 2026-03-25 sigma rows | 56 rows | Early sigma format — no structured notes, prob not stored |
| Total unrecoverable | ~375+ rows | Data was never persisted with full feature fidelity |

These rows cannot be recovered without re-running the VÉLØ ensemble on those
historical race cards and re-fetching results. That requires Racing API historical
data and a full re-score pipeline — outside scope.

---

## Accepted Baseline

```
SIGMA_2K_SAFE_TRAINING_SLICE_V1

Unified corpus:      1521 rows  (all sigma + verdict + results joins)
Training-safe rows:  1310 rows  (result_matched=True, not Category G/F)
Dates covered:       38 dates
Signal validity:     CONFIRMED — all PROVEN signals held at doubled sample (721→1310)
```

This is not a failure. This is the correct name for what we built.
The 1310-row corpus produced stable, validated findings:
- VP monotonicity confirmed
- MDS_HIGH_LANE SR=69.2% held at n=39
- IMPROVER_LANE SR=42.1% held at n=92
- Midprice suppression advisory: 3/4 gates passed
- Router lanes: V1 SR=34.4%, V2 SR=36.4%, V6 SR=40.0%

---

## Path to 2K Training-Safe Rows

```
Current: 1310 training-safe rows
Target:  2000 training-safe rows
Gap:     690 rows

At 30–50 clean rows per race day:
   30/day → ~23 race days (~4.5 weeks)
   50/day → ~14 race days (~3 weeks)

Expected milestone date: ~2026-06-07 to 2026-06-14 (daily accumulation only)
```

No dirty backfill. No partial data. Clean signal truth only.

Every new race day that runs through the full pipeline
(sigma → results → corpus rebuild → training dataset) adds clean rows.

The 2K milestone is earned by evidence accumulation, not by padding numbers.

---

## What Stays Unchanged

```
NO scoring change
NO model change
NO router change
NO staking change
NO Telegram change
NO Playbook G promotion
NO live state mutation
```

This is a governance decision only. The corpus is declared closed at 1310 training-safe rows.
Future builds (named lane tracking, weekly evidence packets) read from this baseline
without modifying it.

---

## Governance Classification

```
CATEGORY_A_RECOVERY_EXHAUSTED           — full investigation done, data not in Supabase
SUPABASE_VERDICT_RECOVERY_NOT_USEFUL    — velo_verdicts only April 22+, already covered
1310_SAFE_TRAINING_SLICE_ACCEPTED       — locked as the validated baseline
GROWTH_PATH_DAILY_ACCUMULATION          — only clean scoring adds new rows
NO_PHASE_B_EXECUTION                    — 301 VP-only rows rejected (0 training-safe lift)
NO_SCORING_CHANGE                       — ensemble weights unchanged
```

---

*SUPABASE_VERDICT_RECOVERY_CLOSURE_2026-05-17 — locked 2026-05-17*
*recovery_dry_run commit: 19893ed | corpus build commit: 5cc1fd0*
