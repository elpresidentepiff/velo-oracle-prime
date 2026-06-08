# International Schema Migration — Operator Approval Packet

**Date:** 2026-05-23  
**File:** `migrations/intl_schemas_v1.sql`  
**Status:** AWAITING_OPERATOR_APPROVAL  
**Preflight audit:** `docs/audit/INTL_SCHEMA_MIGRATION_PREFLIGHT.md` — verdict: MIGRATION_READY

---

## Migration Status Summary

| Property | Value |
|---|---|
| Migration file | `migrations/intl_schemas_v1.sql` |
| Preflight verdict | MIGRATION_READY |
| Applied to Supabase | **NO — NOT YET RUN** |
| Schemas to create | `fr_research`, `hk_research` |
| Tables to create | 16 tables (7 FR + 9 HK) |
| Destructive statements | NONE |
| UK table touches | NONE |
| Live state mutation | NONE |
| Idempotent | YES (`IF NOT EXISTS` throughout) |
| Rollback | `DROP SCHEMA fr_research CASCADE; DROP SCHEMA hk_research CASCADE;` |

---

## What Is Created

### fr_research schema (7 tables)
- `fr_research.fr_races` — Race metadata with going_penetrometer, quintet_plus columns
- `fr_research.fr_runners` — Runner snapshot with valeur_rating column
- `fr_research.fr_results` — Post-race results
- `fr_research.fr_market_snapshots` — Odds at ingestion time
- `fr_research.fr_ingestion_log` — Ingestion audit trail
- `fr_research.fr_verdicts` — Shadow scoring outputs (FR_V1_SHADOW)
- `fr_research.fr_sigma_ledger` — FR evidence audit

### hk_research schema (9 tables)
- `hk_research.hk_races` — Race metadata with hk_class, distance_m
- `hk_research.hk_runners` — Runner snapshot with griffin_flag, class_trajectory, barrier_trial_rpr
- `hk_research.hk_results` — Post-race results
- `hk_research.hk_horse_history` — Per-horse historical HK runs
- `hk_research.hk_sectionals` — HKJC official sectional times (400m splits, pace_rank_400m)
- `hk_research.hk_draw_stats` — Draw bias statistics by (course, distance, draw_position)
- `hk_research.hk_ingestion_log` — Ingestion audit trail
- `hk_research.hk_verdicts` — Shadow scoring outputs with benter_prob field
- `hk_research.hk_sigma_ledger` — HK evidence audit

---

## No UK Table Touches

Confirmed: zero references to `public.*`, `velo_*`, `sigma_audits`, `velo_verdicts`, `pipeline_runs`, or any UK production table in `migrations/intl_schemas_v1.sql`.

---

## Rollback Plan

If migration is applied and needs to be reversed:

```sql
-- Complete rollback — drops all FR and HK research data
DROP SCHEMA fr_research CASCADE;
DROP SCHEMA hk_research CASCADE;
```

Safe to execute at any time. No production data. No UK data. Idempotent — safe to re-run.

---

## Idempotency Confirmation

Every DDL statement uses `IF NOT EXISTS`. The migration can be run multiple times — on second run, all statements succeed with no-op. Safe to re-apply if partial failure occurs.

---

## Exact SQL File Path

```
migrations/intl_schemas_v1.sql
```

File size: ~200 lines. Contains only DDL (CREATE SCHEMA, CREATE TABLE, GRANT). No DML (INSERT, UPDATE, DELETE). No functions. No triggers.

---

## Manual Execution Steps

1. Open Supabase Dashboard at `ltbsxbvfsxtnharjvqcm.supabase.co`
2. Navigate to: **SQL Editor** (left sidebar)
3. Create a new query
4. Copy the full contents of `migrations/intl_schemas_v1.sql`
5. Paste into the SQL editor
6. Click **Run** (or press F5)
7. Confirm "Success. No rows returned" message

**Post-migration step required:**
8. Navigate to: **Settings → API → Exposed schemas**
9. Add `fr_research` and `hk_research` to the exposed schemas list
10. Save settings (PostgREST reload may take ~60 seconds)

---

## Post-Migration Verification Queries

Run these in SQL Editor after applying:

```sql
-- Confirm both schemas exist
SELECT schema_name FROM information_schema.schemata
WHERE schema_name IN ('fr_research', 'hk_research');
-- Expected: 2 rows

-- Confirm FR tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'fr_research'
ORDER BY table_name;
-- Expected: 7 rows (fr_ingestion_log, fr_market_snapshots, fr_races, fr_results, fr_runners, fr_sigma_ledger, fr_verdicts)

-- Confirm HK tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'hk_research'
ORDER BY table_name;
-- Expected: 9 rows (hk_draw_stats, hk_horse_history, hk_ingestion_log, hk_races, hk_results, hk_runners, hk_sectionals, hk_sigma_ledger, hk_verdicts)

-- Confirm zero rows (cold start)
SELECT COUNT(*) FROM fr_research.fr_races;  -- Expected: 0
SELECT COUNT(*) FROM hk_research.hk_races;  -- Expected: 0

-- Confirm no UK data contamination
SELECT COUNT(*) FROM velo_verdicts;  -- Should be unchanged
SELECT COUNT(*) FROM pipeline_runs;  -- Should be unchanged
```

---

## What Happens After Migration

The migration creates empty schemas and tables. Nothing is populated automatically.

Next required steps (in order):
1. Build FR ingest worker using PMU API (Racing API unavailable)
2. Build HK ingest worker using HKJC official site (Racing API unavailable)
3. Test workers against staging with dry-run mode
4. Begin cold archive collection
5. Accumulate 90 days of live data
6. Run Phase 2 model training

---

## Operator Approval Checkbox

Before applying this migration, the operator must confirm:

- [ ] Migration file reviewed at `migrations/intl_schemas_v1.sql`
- [ ] Preflight audit reviewed at `docs/audit/INTL_SCHEMA_MIGRATION_PREFLIGHT.md`
- [ ] Supabase project backup confirmed (or acknowledged as cold schemas only)
- [ ] No UK table modifications expected
- [ ] Rollback plan understood
- [ ] Phase 1 of international expansion formally approved

**Current status: AWAITING_OPERATOR_APPROVAL**  
**Do not apply without explicit approval from El Presidente.**

---

```
MIGRATION_STATUS:    READY_NOT_APPLIED
OPERATOR_APPROVAL:   PENDING
UK_CONTAMINATION:    ZERO_RISK
ROLLBACK_PLAN:       DROP_SCHEMA_CASCADE
IDEMPOTENT:          YES
LIVE_STATE_IMPACT:   NONE
```
