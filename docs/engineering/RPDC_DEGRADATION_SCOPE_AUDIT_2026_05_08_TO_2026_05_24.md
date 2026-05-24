# RPDC Degradation Scope Audit — 2026-05-08 to 2026-05-24

**Classification:** `SCOPE_AUDIT_COMPLETE`  
**Status:** AUDIT_COMPLETE — two separate degradation tracks identified  
**Date:** 2026-05-24  
**Authority:** El Presidente  
**Reference:** `docs/engineering/MAY24_SUPABASE_RPDC_INCIDENT_AUDIT.md`

---

## Executive Summary

The original incident audit (MAY24_SUPABASE_RPDC_INCIDENT_AUDIT.md) attributed improvement_score being constant to the RPDC chain break since 2026-05-08. **This scope audit corrects that attribution.**

Two separate degradation tracks exist:

| Track | Root cause | Affected dates | Impact |
|---|---|---|---|
| **RPDC tags absent** | `ingest_results_to_horse_runs.py` not run → `runner_release_candidates` empty | 2026-05-08 to 2026-05-24 (all 16 days) | `rpdc_tag_count=0`, no tag context, no cash_window_flag |
| **improvement_score constant** | improvement model input features = None (RP source doesn't populate form features) | 2026-05-20 to 2026-05-24 (5 days) | improvement_score excluded from VP ensemble via zero-variance kill switch |

These are independent failures that happened to overlap.

---

## Track 1 — RPDC Tags Absent (2026-05-08 to 2026-05-24)

### Root cause
`runner_release_candidates` has not been updated since 2026-05-08. The daily chain requires:
```
run_results_sigma → ingest_results_to_horse_runs → build_rpdc_daily → runner_release_candidates
```
`ingest_results_to_horse_runs.py` was not run after sigma on 2026-05-23 (immediate cause for today). The chain has been broken since May 8 for unknown reasons.

### Evidence
```
runner_release_candidates latest run_date: 2026-05-08 (16 days stale as of 2026-05-24)
rpdc_tag_count in velo_verdicts:           0 for ALL dates 2026-05-08 to 2026-05-24
build_rpdc_daily 2026-05-24 output:       "No runners to score"
```

### VP formula impact
NONE — rpdc_tag_count=0 does NOT cause improvement_score to be excluded. Confirmed by:
- May 8-19: rpdc_tag_count=0 AND improvement_score varied (active_components includes improvement_score on most days)
- RPDC tags and improvement_score are different pipelines

### Learning impact
RPDC tags are observability/context data. They do not affect sigma win/miss classification directly. Their absence means `rpdc_primary_tag`, `rpdc_cash_window_flag`, and release score context were missing from all 16 days of verdicts.

### Repair command
```bash
# After tonight's sigma:
source venv/bin/activate && PYTHONPATH=. python scripts/ops/ingest_results_to_horse_runs.py --date 2026-05-24
# Then before tomorrow's scoring:
source venv/bin/activate && PYTHONPATH=. python scripts/ops/build_rpdc_daily.py --date 2026-05-25
```

---

## Track 2 — improvement_score Constant (2026-05-20 to 2026-05-24)

### Root cause
The improvement specialist model (`models/specialist/improvement_model/improvement_model.pkl`) requires 12 input features:
```
mark_compression_score, curr_or_minus_best_or, curr_or_minus_last_win_or,
release_window_score, runs_since_win, runs_since_place, trainer_timing_score,
distance_fit_score, course_fit_score, or_vs_field, rpr_vs_field, age_num
```

All 12 features are `None` for every runner in every race since at least 2026-05-20. When all features are None, the model fills them with 0 and returns a constant output of **0.0872** for every runner.

The ensemble's zero-variance kill switch detects improvement_score is constant across the field and excludes it. This is correct ensemble behavior — a constant signal adds zero ranking information.

### Evidence
```
Runner snapshots 2026-05-20: improvement_score unique values = {0.0872} (all 269 runners)
Runner snapshots 2026-05-21: improvement_score unique values = {0.0872} (all 369 runners)
Runner snapshots 2026-05-22: improvement_score unique values = {0.0872} (all 241 runners)
Runner snapshots 2026-05-23: improvement_score unique values = {0.0872} (all runners)
Runner snapshots 2026-05-24: improvement_score unique values = {0.0872} (all 241 runners)
mark_compression_score, or_vs_field, rpr_vs_field, runs_since_win, etc.: None for all runners
```

### Origin
improvement_score was **varying** through 2026-05-19 (velo_verdicts confirms distinct per-runner values). It became constant on 2026-05-20 — the SCORING_FLATLINE_CONTAMINATED day. Commit `a33c5bd` (fix(#85): RP_MERGED feature differentiation collapse, applied 2026-05-21) fixed VP differentiation but did not restore improvement model features.

The improvement model features (`or_vs_field`, `rpr_vs_field`, etc.) require data not provided by the current RP PDF source. The Racing API was decommissioned on 2026-05-14. These features were populated from Racing API runner data and have not been re-sourced since the pipeline transitioned to RP-only.

**This is NOT caused by RPDC chain break. These are different pipelines.**

### VP formula impact
SIGNIFICANT — affects the VP denominator and absolute tier cuts.

```
Effective formula (active): VP_raw = (0.45 × sqpe + 0.10 × mds) / 0.55
Live-truth formula:          VP_raw = (0.45 × sqpe + 0.12 × improvement_score + 0.10 × mds) / 0.67
```

After field-level renormalization to sum=1.0 per race, absolute VP values are affected. Rankings within a race are NOT affected (improvement_score constant across all runners in a race → zero ranking signal regardless).

### Correction requires
Re-sourcing the improvement model's 12 input features from the RP PDF pipeline or an alternative data source. This is a separate engineering task from RPDC chain repair.

---

## Full Date-By-Date Table

Source: `velo_verdicts` direct query, 695 rows, 2026-05-08 to 2026-05-24.

| Date | Races scored | improvement_score | active_components | rpdc_tag_count | formula status | sigma exists | learning_status |
|---|---|---|---|---|---|---|---|
| 2026-05-08 | 51 | VARYING | None (pre-field tracking) | 0 | UNKNOWN — no active_components field | CHECK | BLOCKED_PENDING_REVIEW |
| 2026-05-09 | 64 | VARYING | None | 0 | UNKNOWN | CHECK | BLOCKED_PENDING_REVIEW |
| 2026-05-11 | 42 | VARYING | improvement+mds+sqpe | 0 | FULL_FORMULA (3 components) | CHECK | CONDITIONALLY_ELIGIBLE |
| 2026-05-12 | 39 | VARYING | improvement+mds+sqpe | 0 | FULL_FORMULA | CHECK | CONDITIONALLY_ELIGIBLE |
| 2026-05-13 | 42 | VARYING | improvement+mds+sqpe | 0 | FULL_FORMULA | CHECK | CONDITIONALLY_ELIGIBLE |
| 2026-05-14 | 35 | VARYING | improvement+mds+sqpe | 0 | FULL_FORMULA | CHECK | CONDITIONALLY_ELIGIBLE |
| 2026-05-15 | 112 | VARYING | improvement+mds+sqpe | 0 | FULL_FORMULA | CHECK | CONDITIONALLY_ELIGIBLE |
| 2026-05-17 | 30 | VARYING | sqpe only | 0 | SQPE_ONLY (mds+improvement both excluded) | CHECK | BLOCKED_SQPE_ONLY_DAY |
| 2026-05-18 | 34 | VARYING | improvement+mds+sqpe | 0 | FULL_FORMULA | CHECK | CONDITIONALLY_ELIGIBLE |
| 2026-05-19 | 38 | VARYING | improvement+mds+sqpe | 0 | FULL_FORMULA (last full-formula day) | CHECK | CONDITIONALLY_ELIGIBLE |
| 2026-05-20 | 33 | CONSTANT 0.0872 | sqpe only | 0 | SQPE_ONLY — FLATLINE_CONTAMINATED | `sigma_results_2026_05_20.json` | BLOCKED — CONTAMINATED |
| 2026-05-21 | 44 | CONSTANT 0.0872 | mds+sqpe | 0 | DEGRADED — improvement excluded | CHECK | BLOCKED — improvement constant |
| 2026-05-22 | 43 | CONSTANT 0.0872 | mds+sqpe | 0 | DEGRADED — improvement excluded | CHECK | BLOCKED — improvement constant |
| 2026-05-23 | 59 | CONSTANT 0.0872 | mds+sqpe | 0 | DEGRADED — improvement excluded | `sigma_results_2026_05_23.json` | BLOCKED — improvement constant |
| 2026-05-24 | 29 | CONSTANT 0.0872 | mds+sqpe | 0 | DEGRADED — OFFICIAL_VALID_FEATURE_DEGRADED | PENDING (tonight) | BLOCKED — improvement constant |

**CONDITIONALLY_ELIGIBLE**: improvement_score varied (full formula was active). RPDC tags absent but this is observability only, not formula degradation. These days may be eligible for learning after operator review — the core VP signal was intact. Council decision required.

**BLOCKED — improvement constant**: improvement_score excluded from VP formula. VP scores are ~22% inflated relative to full formula on an absolute basis. Rankings within each race are unaffected. Learning blocked until improvement model features are re-sourced.

---

## Compare-Only Result — 2026-05-24

**Task**: dry compare of today's official (degraded) predictions vs hypothetical RPDC-restored predictions.

**Findings**:

1. `ingest_results_to_horse_runs.py --date 2026-05-23` — COMPLETED (164 rows written)
2. `build_rpdc_daily.py --date 2026-05-24` — returned 0 runners (fallback to velo_verdicts failed — `top_rank_horse_id` not a live column)
3. Improvement_score with repaired RPDC chain: **still 0.0872 constant** — RPDC repair does not fix the improvement model feature gap
4. VP formula with repaired RPDC: **unchanged** — improvement_score excluded by zero-variance kill switch regardless

**Comparison result**: NO VP CHANGE achievable via RPDC chain repair alone.

```
A-tier changed:           NO — Sun Goddess remains Tier A
Sun Goddess changed:      NO — ranking within CUR 1.45 field unchanged (zero-variance kill)
B-tier tier changes:      0 (from RPDC repair) — all tied to improvement_score feature gap
Rankings changed:         0
Probability delta:        0 (same formula whether RPDC repaired or not)
```

**Operator decision: HOLD_AS_DEGRADED confirmed.**

Full-formula VP cannot be achieved by RPDC chain repair. A true comparison requires re-sourcing the improvement model's 12 input features. That is a separate engineering task.

---

## consumed_shadow and consumed_live Exposure

```
consumed_live (any date):  0 — no live staking active
consumed_shadow:           See sigma files — NONE of the May 20-24 degraded days have
                           been consumed by eod_shadow_learning_bridge.py
```

No learning from this window has been consumed. The LEARNING_BLOCKED classification is protective and not remedial.

---

## Immediate Required Actions

1. **Tonight**: Run `run_results_sigma.py --date 2026-05-24` and `ingest_results_to_horse_runs.py --date 2026-05-24`
2. **Tomorrow morning**: Run `build_rpdc_daily.py --date 2026-05-25` (verify >0 runners — chain now repaired for tomorrow)
3. **Improvement model features**: Engineering task required to re-source the 12 improvement model inputs from the RP PDF pipeline. No timeline set. This blocks full-formula VP from resuming.
4. **Learning eligibility May 8-19**: Conditionally eligible days require Council review before consumption. The core VP signal was intact (improvement_score varied) but RPDC tag context was absent.
5. **build_rpdc_daily fallback path**: The script's `velo_verdicts` fallback uses `top_rank_horse_id` which is not a live column. Fix required before the fallback path is usable.

---

```
SCOPE_AUDIT_STATUS:              COMPLETE
IMPROVEMENT_SCORE_DEGRADED_FROM: 2026-05-20 (not 2026-05-08 as originally stated)
RPDC_TAGS_ABSENT_FROM:           2026-05-08
ORIGINAL_ATTRIBUTION_ERROR:      Corrected — two separate degradation tracks
COMPARE_ONLY_RESULT:             NO_VP_CHANGE — RPDC repair does not fix improvement model features
OFFICIAL_DECISION:               HOLD_AS_DEGRADED
A_TIER_CHANGED:                  NO
SUN_GODDESS_CHANGED:             NO
B_TIER_CHANGES:                  0 (from RPDC repair)
LEARNING_BLOCKED:                2026-05-20 to 2026-05-24 (improvement_score constant)
LEARNING_CONDITIONALLY_ELIGIBLE: 2026-05-08 to 2026-05-19 (Council review required)
LEARNING_BLOCKED_FLATLINE:       2026-05-20 (SCORING_FLATLINE_CONTAMINATED, previously known)
CONSUMED_SHADOW:                 0 (none consumed from degraded window)
CONSUMED_LIVE:                   0 (live staking not active)
NO_SCORING_CHANGE:               CONFIRMED
NO_MODEL_PROMOTION:              CONFIRMED
NO_ROUTER_STAKING_CHANGES:       CONFIRMED
NO_LIVE_STATE_MUTATION:          CONFIRMED
```
