# July 06 Canonical Runtime Persistence Report

Generated: 2026-07-06T22:15:57.696475Z
Mode: **EXECUTE**

## Classification

- source_type = RUNTIME_RACEDAY_MODEL_SUGGESTION
- sigma_classification = SIGMA_RUNTIME_LEARNING_FROM_EXISTING_RACEDAY_ARTIFACTS
- not_official_live_sigma = true
- promotion_block_reason = JULY06_RUNTIME_ARTIFACT_LEARNING_NOT_PROMOTION_GRADE

## Schema-compatibility note

`canonical_model_scorecards` (see `supabase/migrations/20260706_create_canonical_model_scorecards.sql`)
has no `promotion_eligible` / `source_type` / `sigma_classification` columns.
Those labels are packed into the existing `learning_class` (=
`RUNTIME_RACEDAY_MODEL_SUGGESTION`) and `notes` text columns instead of
adding new columns via an unauthorised schema migration. `stake_authorised`
is a real boolean column and is written as `false` on every row.

`canonical_learning_events` natively has `promotion_eligible` and
`promotion_block_reason` typed columns (per `scripts/ops/build_canonical_learning_events.py`) —
written as real typed `false` / `JULY06_RUNTIME_ARTIFACT_LEARNING_NOT_PROMOTION_GRADE` there.

## Preflight

```json
{
  "scorecard_row_count": 1647,
  "expected_scorecard_rows": 1647,
  "learning_event_count": 325,
  "expected_learning_events": 325,
  "scorecard_promotion_eligible_column_present": false,
  "scorecard_stake_authorised_true_count": 0,
  "event_promotion_eligible_true_count": 0,
  "no_velo_verdicts_target": true,
  "preflight_pass": true
}
```

## Write result

- canonical_model_scorecards rows written: **1647**
- canonical_learning_events rows written: **324**
- Post-write canonical_model_scorecards count for 2026-07-06: 1647
- Post-write canonical_learning_events count for 2026-07-06: 324
- velo_verdicts touched: **false** (this script never references that table)

## Known field-mapping gaps (disclosed, not fabricated)

- `canonical_learning_events.source_scorecard_id`, `.score`: not populated (local join did not
  retain the parent scorecard row id or a numeric score per event) — left NULL.
- `canonical_learning_events.rank`: set to 1 for every event, since only top-pick (rank=1) rows
  were ever converted into learning events by the Task 4 builder.
