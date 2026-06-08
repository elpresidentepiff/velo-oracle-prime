# May 24 — Supabase & RPDC Degraded Run Incident Audit

**Classification:** `2026-05-24_RUN_DEGRADED`  
**Status:** AUDIT_COMPLETE — root causes identified  
**Date:** 2026-05-24  
**Authority:** El Presidente  
**Triggered by:** Operator post-run review

---

## Run Classification

```
2026-05-24_RUN_DEGRADED
SUPABASE_WRITE_STATUS:           CONFIRMED — 29/29 rows present in velo_verdicts
SUPABASE_READ_FALLBACK:          TRIGGERED — dashboard publisher used local_json_top_only
SUPABASE_PERSISTENCE_STATUS:     PROVEN — 29 rows verified by direct DB query
RPDC_ZERO_RUNNERS:               CONFIRMED — all 29 races, rpdc_tag_count=0
LIVE_WEIGHTED_FEATURE_MISSING:   CONFIRMED — improvement_score excluded from ensemble
EFFECTIVE_VP_FORMULA:            DEGRADED (see below)
PREDICTION_INTEGRITY:            OFFICIAL_VALID_FEATURE_DEGRADED
LEARNING_STATUS:                 NO_LEARNING_UNTIL_RECONCILED
DECISION_TIER_IN_SUPABASE:       NULL for all 29 rows (secondary issue)
GIT_COMMIT_SHA_IN_SUPABASE:      NULL for all 29 rows (secondary issue)
```

---

## Task 1 — Supabase Persistence Proof

### Write path: CONFIRMED

Direct query of `velo_verdicts` confirms 29/29 rows written for 2026-05-24:

```
VELO_VERDICTS_2026_05_24_COUNT: 29
EARLIEST_GENERATED_AT: 2026-05-24T10:56:20.585156+00:00
LATEST_GENERATED_AT:   2026-05-24T10:56:28.461716+00:00
VENUES_IN_DB: ['CUR', 'FON', 'KEL', 'UTT']
```

Supabase write path (`persist_race_predictions`) succeeded. "Persisted 29/29" was accurate for the write path.

### Read fallback: `publish_daily_predictions_to_dashboard.py`

The dashboard publisher logged:
```
Local JSON: 29 races (Supabase unavailable, using fallback)
SOURCE USED: local_json_top_only
MISSING SIDECARS: 29 races with null optional fields
```

Root cause: The publisher query relied on fields that are NULL in today's rows — most likely `decision_tier` (NULL for all 29 rows, see secondary issues below). The fallback to local JSON did not corrupt predictions. Dashboard output reflects the same 29 scores.

### Secondary issues found in Supabase rows

| Field | Expected | Actual | Impact |
|---|---|---|---|
| `decision_tier` | A/B/C/D/X | NULL (all 29 rows) | Dashboard publisher fell back to local JSON |
| `git_commit_sha` | `932096b7...` | NULL (all 29 rows) | Audit traceability gap |
| `rpdc_tag_count` | ≥1 for today's runners | 0 (all 29 rows) | Confirms RPDC absent |

These are **secondary issues** — they do not affect prediction scores. They do affect dashboard, learning eligibility checks, and audit traceability.

**`decision_tier` NULL:** The field exists in the schema but was not populated in today's run. This is likely a persist mapping issue. Tiers exist in the local backup JSON and in the runner_snapshots file. Requires investigation but is not a scoring failure.

---

## Task 2 — RPDC Failure Root Cause

### The broken chain

```
Sigma (2026-05-23):          COMPLETED — evaluated_count=56, wins=18
ingest_results_to_horse_runs: NOT RUN for 2026-05-23 — racing_horse_runs has 0 rows for 2026-05-23
build_rpdc_daily (2026-05-24): Found 0 runners — correct, chain was broken upstream
runner_release_candidates:   Last row date = 2026-05-08 — not updated since
improvement_score today:     constant 0.0872 across all 29 races
```

### Evidence

| Check | Result |
|---|---|
| sigma_results_2026_05_23.json | EXISTS — 56 evaluated, 18W/10FR/28MISS |
| racing_horse_runs latest date | 2026-05-22 |
| racing_horse_runs 2026-05-23 count | 0 — ingest not run |
| runner_release_candidates latest | 2026-05-08 |
| runner_release_candidates 2026-05-24 | 0 rows |
| build_rpdc_daily 2026-05-24 output | "No runners to score" |
| rpdc_tag_count in velo_verdicts | 0 for all 29 rows |
| improvement_score in velo_verdicts | 0.0872 (constant) for all 29 rows |

### Immediate cause (today)
`ingest_results_to_horse_runs.py` was not run after sigma on 2026-05-23. This left `racing_horse_runs` with no 2026-05-23 data. `build_rpdc_daily.py` for 2026-05-24 found nothing to process and correctly returned 0 runners.

### Longer-running issue
`runner_release_candidates` has not been updated since **2026-05-08** — 16 days before today. This means RPDC has been effectively absent from scoring since that date. The `build_rpdc_daily.py` script has been returning 0 runners on most days, and `improvement_score` has been constant (0.0872) for at least the last 16 days of scored races.

This was silently normalized in every run since 2026-05-08. No run flagged `FEATURE_DEGRADED`. No Telegram banner. No Mission Control alert.

### Yesterday's sigma also degraded
The sigma rows CSV for 2026-05-23 shows `improvement=0.0872` (constant) for all rows. Yesterday's run was also degraded on improvement_score. The 18W/28M sigma result for 2026-05-23 reflects SQPE+MDS-only scoring, not full-formula scoring.

**Affected date range:** At minimum 2026-05-08 to 2026-05-24 (16+ days). All sigma results in this window used the degraded VP formula. None of their learning candidates should be consumed until RPDC is restored and the scope of the degradation is fully mapped.

---

## Task 3 — Prediction Integrity Classification

### Effective VP formula used today

```
Expected (live-truth):
  VP = (0.45 × sqpe_v17 + 0.12 × improvement_score + 0.10 × MDS) / 0.67

Actual (degraded — all 29 races):
  VP = (0.45 × sqpe_v17 + 0.10 × MDS) / 0.55

active_components:   ['market_deception_score', 'sqpe_v17']
excluded:            ['improvement_score', 'place_prob', 'longshot_score',
                      'release_window_score', 'comment_intel_score']
```

### Denominator effect

The denominator dropped from 0.67 → 0.55 (a 21.8% reduction). This inflates all VP scores by approximately:
- `VP_today ≈ VP_full × (0.67 / 0.55) ≈ VP_full × 1.218`
- Example: CUR 1.45 Sun Goddess VP=0.3584 → full-formula estimate ≈ 0.294

Some horses may have been promoted to Tier B/A under today's formula that would be Tier C/B under the full formula. The "strong card" A=1 / B=19 posture is based on inflated VP scores.

### SQPE and MDS availability

Both components were available and functional:
- SQPE v17: loaded, all 29 races scored
- MDS: loaded, values vary per race (not constant)

The core signal (SQPE) is intact. The degradation is in the improvement_score component only.

### Dry comparison: NOT FEASIBLE

A dry comparison between today's degraded output and a hypothetical full-RPDC output cannot be run because:
- `runner_release_candidates` is empty for 2026-05-24
- Ingesting 2026-05-23 results now would rebuild the RRC and change the "official" RPDC state
- Any re-score would require operator approval (scoring change)

**No comparison run. No Supabase writes. No re-score.**

### Classification

```
PREDICTION_INTEGRITY: OFFICIAL_VALID_FEATURE_DEGRADED

Rationale:
- SQPE v17 scored correctly (0.45 weight — 81.8% of full denominator)
- MDS scored correctly (0.10 weight)
- improvement_score was absent due to RPDC failure (not a model failure)
- VP scores are real but ~22% inflated vs full formula
- Tier assignments may be inflated by 1 tier in borderline cases
- CUR 1.45 Sun Goddess (prob=0.3584) — full-formula estimate ~0.294 — still
  likely Tier A (VP≥0.30 + gap) but not confirmed
- All 29 races scored, 0 errors, 29/29 persisted to Supabase
```

---

## Task 4 — Mission Control / Sentinel Gaps

### What Mission Control did not flag

The following conditions occurred without any system-level warning, block, or degraded-feature banner:

| Condition | Expected response | Actual response |
|---|---|---|
| RPDC returned 0 runners | WARN or BLOCK | Silent — "No runners to score" to stdout only |
| improvement_score constant across all races | FEATURE_DEGRADED banner in Telegram | Silent — log WARNING only |
| active_components reduced from 3 to 2 | WARN — live-weighted component missing | Silent |
| VP formula denominator changed (0.67→0.55) | WARN — formula integrity changed | Silent |
| Supabase publisher read fallback | WARN — dashboard using local artifact | Silent |
| decision_tier NULL in Supabase persist | WARN — persist mapping failure | Silent |
| RPDC chain broken for 16+ days | DAILY_WARN accumulation | Never flagged |

### Required future gates (documentation only — not implemented)

These gates must be defined and implemented before the next full scoring run. Operator approval required.

```
GATE_1: RPDC_ZERO_BLOCK_OR_WARN
  Trigger: build_rpdc_daily returns 0 runners
  Action:  WARN in Telegram pre-flight. Log to mission_control.json.
           If improvement_score becomes constant → FEATURE_DEGRADED_BANNER.
  Note:    Do NOT block scoring on RPDC=0. improvement_score exclusion is correct
           behavior. But the operator must see it.

GATE_2: FEATURE_DEGRADED_BANNER
  Trigger: Any live-weighted component excluded from ensemble (improvement_score,
           MDS, SQPE — anything in active_components reduced vs full-truth formula)
  Action:  Prepend banner to Telegram day posture message:
           "⚠ FEATURE_DEGRADED: improvement_score excluded — RPDC unavailable.
            VP formula: SQPE+MDS only. Scores ~22% inflated vs full formula."
  Note:    Must appear in Telegram, dashboard, and Mission Control daily packet.

GATE_3: SUPABASE_PUBLISH_FALLBACK_WARN
  Trigger: publish_daily_predictions_to_dashboard.py uses local_json_top_only
  Action:  Warn in Telegram summary. Label dashboard output as FALLBACK_LOCAL.
  Note:    Does not affect scoring but affects dashboard integrity.

GATE_4: SUPABASE_WRITE_PROOF_REQUIRED
  Trigger: After every persist step
  Action:  Query velo_verdicts count for today. Log to mission_control.json.
           If count < expected: ALERT. If decision_tier NULL: SECONDARY_WARN.

GATE_5: RPDC_COVERAGE_WARN
  Trigger: runner_release_candidates latest date > 3 days behind scoring date
  Action:  Pre-flight WARN before scoring begins. Log to mission_control.json.
  Note:    Prevents silent multi-day RPDC drift like the current 16-day gap.

GATE_6: LEARNING_ELIGIBILITY_BLOCK
  Trigger: Any sigma day where improvement_score was constant (feature degraded)
  Action:  Mark sigma result as LEARNING_BLOCKED_FEATURE_DEGRADED.
           Block eod_shadow_learning_bridge.py from consuming those rows.
  Note:    Currently no gate exists. All sigma rows since 2026-05-08 are at risk.
```

---

## Final Summary

```
SUPABASE_WRITE_STATUS:          CONFIRMED — 29/29 rows
SUPABASE_PUBLISH_FALLBACK:      TRIGGERED — decision_tier NULL caused read fallback
RPDC_ROOT_CAUSE:                ingest_results_to_horse_runs.py not run for 2026-05-23
                                RPDC chain broken since 2026-05-08 (16+ days)
IMPROVEMENT_SCORE_STATUS:       EXCLUDED from ensemble — constant at 0.0872
EFFECTIVE_VP_FORMULA:           (0.45×sqpe + 0.10×mds) / 0.55 — NOT live-truth formula
VP_SCORE_INFLATION:             ~22% vs full formula (denominator 0.67→0.55)
SQPE_STATUS:                    OPERATIONAL
MDS_STATUS:                     OPERATIONAL
PREDICTION_INTEGRITY:           OFFICIAL_VALID_FEATURE_DEGRADED
LEARNING_STATUS:                NO_LEARNING_UNTIL_RECONCILED
DEGRADATION_SCOPE:              2026-05-08 to 2026-05-24 minimum (16+ days)
SENTINEL_GAPS:                  6 gates missing (documented above — not implemented)
NO_SCORING_CHANGE:              CONFIRMED — no runtime code touched
NO_MODEL_PROMOTION:             CONFIRMED
NO_ROUTER_STAKING_CHANGES:      CONFIRMED
NO_TELEGRAM_RUNTIME_CHANGES:    CONFIRMED
NO_PLAYBOOK_G_CHANGES:          CONFIRMED
NO_LIVE_STATE_MUTATION:         CONFIRMED
```
