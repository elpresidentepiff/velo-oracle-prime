# External Supabase sigma_audits Mutation Note — 2026-06-14

**Recorded:** 2026-06-14
**Recorded by:** Operator (VFU-03 session)
**Source:** External Supabase MCP agent (separate from Claude Code VFU session)

## What Was Executed

A separate Supabase AI agent, operating with operator approval, performed schema
migration and backfill passes on the table `public.sigma_audits`.

## Schema Changes Applied

```sql
alter table public.sigma_audits
  add column if not exists pick_sp numeric,
  add column if not exists distance text,
  add column if not exists going text,
  add column if not exists race_type text,
  add column if not exists field_size integer;
```

## Backfill Passes Attempted

1. `horse_id` — joined from `velo_verdicts` via verdict_id, fallback by race_id
2. `pick_sp` — joined from `runner_results.sp_dec` via (race_id, horse_id)
3. Race metadata (distance, going, race_type, field_size) — from races/racecards/runner_race_facts
4. `actual_winner_sp` — from runner_results via (race_id, actual_winner_id)
5. Secondary key metadata — via racecards date+course+off_time join

## Validation Result (Latest 20 sigma_audits rows)

| Field | Null Count | Status |
|---|---|---|
| horse_id | 0 | FIXED |
| actual_winner_sp | 0 | FIXED |
| pick_sp | 20 | STILL NULL — no DB join available |
| distance | 20 | STILL NULL — no DB join available |
| going | 20 | STILL NULL — no DB join available |
| race_type | 20 | STILL NULL — no DB join available |
| field_size | 20 | STILL NULL — no DB join available |

## Root Cause of Remaining Nulls

The latest sigma_audits rows use race IDs from the RP/local pipeline era
(e.g. 920243, 922700) that do not exist in `races`, `racecards`,
`runner_results`, or `racing_today_*` tables. These race IDs were generated
by the local RP ingestion pipeline, not the Racing API pipeline that populates
the standard DB tables.

## VFU Decision

**Local enrichment first. Supabase staging NOT approved in VFU-03.**

The pick_sp enrichment for VFU forensic analysis is handled entirely locally:
- Source: `data/velo_innovation_protocol_1k_deduped.csv`
- Script: `scripts/ops/vfu_enrich_pick_sp.py`
- Output: `data/reports/current_era_sigma_union_rows_enriched_vfu_v1.json`
- Coverage achieved: 107/1,263 rows (8.5%)
- Structural blockers: 537 LOCAL_ONLY rows unmatchable; 465 rows on dates not in CSV

No further Supabase writes are approved under the VFU-03 task scope.

## Hard Rule Confirmations

- No VFU script writes to Supabase: CONFIRMED
- No Supabase staging table created by Claude Code: CONFIRMED
- Canonical Horse Passport not mutated: CONFIRMED
- No live scoring change: CONFIRMED
- No model promotion: CONFIRMED

## Approved Supabase Changes (for audit completeness)

These changes ARE live in Supabase as of 2026-06-14, operator-approved:

- `public.sigma_audits` — 5 columns added (pick_sp, distance, going, race_type, field_size)
- `horse_id` backfilled for rows where join to `velo_verdicts` succeeded
- `actual_winner_sp` backfilled for rows where join to `runner_results` succeeded

These changes do not affect VÉLØ scoring, VP, or Sigma output.
