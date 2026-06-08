# Improvement Feature Availability Audit — 2026-05-25

**Generated:** 2026-05-24T18:00:38.975973+00:00  
**Data source:** racecard:racecards_2026_05_17_standard.json (proxy for 2026-05-25)  
**NOTE:** Using 2026-05-17 as proxy — May25 card not yet available  

---

## Verdict: `PARTIAL_RESTORE_POSSIBLE`

> 4 features available in local data but NOT injected by current pipeline. Pipeline change required (not done yet). Improvement_score REMAINS CONSTANT under current scoring path.

## Summary

| Metric | Value |
|---|---|
| Total improvement features | 12 |
| Features with variance in current pipeline | 0 |
| Features restorable by RPDC/racecard (with pipeline change) | 4 |
| Improvement_score currently constant? | True |
| Zero-variance kill switch would fire? | True |

## Per-Feature Analysis

| Feature | Source | Current Status | With RPDC/RC | Variance Restored? | Pipeline Change Needed? |
|---|---|---|---|---|---|
| `mark_compression_score` | RP_DEEP_PROFILE | ALL_NULL | ALL_NULL | NO | NO |
| `curr_or_minus_best_or` | RACING_API_FORM_HISTORY | ALL_NULL | ALL_NULL | NO | NO |
| `curr_or_minus_last_win_or` | RACING_API_WIN_HISTORY | ALL_NULL | ALL_NULL | NO | YES |
| `release_window_score` | SPECIALIST_MODEL_RELEASE_WINDOW | ALL_NULL | ALL_NULL | NO | NO |
| `runs_since_win` | RACING_API_FORM_HISTORY | ALL_NULL | ALL_NULL | NO | NO |
| `runs_since_place` | RACING_API_FORM_HISTORY | ALL_NULL | ALL_NULL | NO | NO |
| `trainer_timing_score` | RACING_API_JTC_TABLES | ALL_NULL | ALL_NULL | NO | NO |
| `distance_fit_score` | RACING_API_FORM_HISTORY | ALL_NULL | ALL_NULL | NO | NO |
| `course_fit_score` | RACING_API_FORM_HISTORY | ALL_NULL | ALL_NULL | NO | NO |
| `or_vs_field` | RACECARD_FIELD_AGGREGATION | ALL_NULL | HAS_VARIANCE | YES | YES |
| `rpr_vs_field` | RACECARD_FIELD_AGGREGATION | ALL_NULL | HAS_VARIANCE | YES | YES |
| `age_num` | RACECARD | ALL_NULL | HAS_VARIANCE | YES | YES |

## Recovery Path by Feature

**`mark_compression_score`** (RP_DEEP_PROFILE)
  Requires RP deep-form profile data (not available in standard racecard)

**`curr_or_minus_best_or`** (RACING_API_FORM_HISTORY)
  Requires full OR history per horse (best ever OR). Not in RPDC JSONL. Racing API decommissioned.

**`curr_or_minus_last_win_or`** (RACING_API_WIN_HISTORY)
  RPDC memory provides or_delta_to_win for matched horses (62.7% coverage). Requires pipeline change to inject.

**`release_window_score`** (SPECIALIST_MODEL_RELEASE_WINDOW)
  Output of release_window_model, which itself needs Racing API features. Blocked upstream.

**`runs_since_win`** (RACING_API_FORM_HISTORY)
  Not stored in RPDC JSONL (computed but not persisted in backfill_rpdc_historical_local.py). Could be added to next backfill run.

**`runs_since_place`** (RACING_API_FORM_HISTORY)
  Not stored in RPDC JSONL. Same as runs_since_win — could be added to backfill output.

**`trainer_timing_score`** (RACING_API_JTC_TABLES)
  From JTC (Jockey-Trainer-Course) data tables built via Racing API. Racing API decommissioned. Must be rebuilt from RP pipeline.

**`distance_fit_score`** (RACING_API_FORM_HISTORY)
  Requires horse distance win rate from Racing API. Not in RPDC. RP JTC tables partially cover this.

**`course_fit_score`** (RACING_API_FORM_HISTORY)
  Requires horse course win rate from Racing API. Not in RPDC. RP JTC tables partially cover this.

**`or_vs_field`** (RACECARD_FIELD_AGGREGATION)
  Can be computed from racecard ofr values (runner_ofr - mean_field_ofr). Available now — requires pipeline change.

**`rpr_vs_field`** (RACECARD_FIELD_AGGREGATION)
  Can be computed from racecard rpr values (runner_rpr - mean_field_rpr). Available now — requires pipeline change.

**`age_num`** (RACECARD)
  Available directly from racecard age field. Requires pipeline change to convert age string to int.

---

```
VERDICT:                          PARTIAL_RESTORE_POSSIBLE
AUDIT_DATE:                       2026-05-25
DATA_DATE:                        2026-05-17
IS_PROXY:                         True
IMPROVEMENT_CONSTANT:             True
KILL_SWITCH_FIRES:                True
FEATURES_RESTORABLE_WITH_CHANGE:  4
SUPABASE_READS:                   NONE
SCORING_CHANGE:                   NONE
```