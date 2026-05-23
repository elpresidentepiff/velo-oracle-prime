# International Schema Migration Preflight

**Date:** 2026-05-23  
**File:** `migrations/intl_schemas_v1.sql`  
**Status:** NOT RUN — preflight only  
**Verdict: MIGRATION_READY** (with one note below)

---

## What the Migration Creates

### Schemas
| Schema | Purpose |
|---|---|
| `fr_research` | French racing cold archive — completely separate from UK/production |
| `hk_research` | Hong Kong racing cold archive — completely separate from UK/production |

### Tables Created

**fr_research (7 tables):**
| Table | Primary Key | Purpose |
|---|---|---|
| `fr_research.fr_races` | `race_id` | Race-level metadata including going, distance, prize |
| `fr_research.fr_runners` | `(race_id, horse_id)` | Runner snapshot at racecard time |
| `fr_research.fr_results` | `(race_id, horse_id)` | Post-race results with SP and finish position |
| `fr_research.fr_market_snapshots` | `(race_id, horse_id)` | Odds at ingestion time |
| `fr_research.fr_ingestion_log` | `BIGSERIAL` | Ingestion audit trail |
| `fr_research.fr_verdicts` | `(race_id, horse_id)` | Shadow model scoring outputs |
| `fr_research.fr_sigma_ledger` | `(race_id, horse_id)` | FR evidence audit (sigma equivalent) |

**hk_research (9 tables):**
| Table | Primary Key | Purpose |
|---|---|---|
| `hk_research.hk_races` | `race_id` | Race-level metadata including class, distance |
| `hk_research.hk_runners` | `(race_id, horse_id)` | Runner snapshot including griffin_flag, class_trajectory |
| `hk_research.hk_results` | `(race_id, horse_id)` | Post-race results |
| `hk_research.hk_horse_history` | `(horse_id, race_id)` | Per-horse historical runs |
| `hk_research.hk_sectionals` | `(race_id, horse_id)` | HKJC official 400m split times |
| `hk_research.hk_draw_stats` | `(course, distance_m, draw_position)` | Draw bias statistics |
| `hk_research.hk_ingestion_log` | `BIGSERIAL` | Ingestion audit trail |
| `hk_research.hk_verdicts` | `(race_id, horse_id)` | Shadow model scoring outputs (SQPE + Benter) |
| `hk_research.hk_sigma_ledger` | `(race_id, horse_id)` | HK evidence audit |

### Indexes
All tables include `CREATE TABLE IF NOT EXISTS` — no direct index creation in current migration. Indexes on date/race_id columns should be added before first ingestion run.

### Row Level Security (RLS)
- NOT configured in current migration
- Supabase default: RLS off for service_role
- Service role key used by workers — safe without explicit RLS since schemas are cold research only
- Note: If anon access is ever needed, add RLS policies before enabling

### Grants
```sql
GRANT USAGE ON SCHEMA fr_research TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA fr_research TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA fr_research TO service_role;
-- Same for hk_research
```

### Destructive Statements
**NONE.** Every statement uses `CREATE TABLE IF NOT EXISTS` and `CREATE SCHEMA IF NOT EXISTS`. Safe to re-run.

### UK Table Touches
**NONE.** Migration only creates `fr_research.*` and `hk_research.*` objects. No `public.*`, `velo_*`, or any existing table is modified.

### Live State Touches
**NONE.** Schema creation has no effect on running services. PostgREST needs a reload to see new schemas (see note below).

---

## Rollback Plan

```sql
DROP SCHEMA fr_research CASCADE;
DROP SCHEMA hk_research CASCADE;
```

Safe to execute at any time. No production data in these schemas. No UK data in these schemas.

---

## Idempotency Check

All statements use `IF NOT EXISTS`. The migration can be run multiple times safely. Re-running on an existing schema does nothing.

---

## Required Env Vars

None. This is a DDL-only migration. No application code is executed.

---

## PostgREST Schema Exposure (Action Required After Applying)

The Supabase Python client routes through PostgREST. PostgREST only exposes schemas listed in its `db_schema_cache` setting.

After applying the migration, go to:
**Supabase Dashboard → Settings → API → exposed_schemas**

Add: `fr_research` and `hk_research`

Without this step, the workers' `db.table("fr_research.fr_races")` calls will return the error:
`Could not find the table 'public.fr_research.fr_races' in the schema cache`

(This is the exact error confirmed when checking schema existence — see session notes.)

---

## One Open Question

The `fr_research.fr_runners` table in the migration currently lacks `going_penetrometer` (the FR-specific numeric going field). This was defined in the architecture document but not included in the runner-level table — it belongs in `fr_races`. The `fr_races` table does include `going_penetrometer FLOAT`. This is correct — going is a race-level attribute, not runner-level. No action needed.

---

## Verdict

```
MIGRATION_READY
No destructive statements
No UK table touches
No live state mutation
Fully idempotent
Rollback is clean DROP SCHEMA CASCADE
One post-apply action required: expose schemas in Supabase API settings
Do not run until operator approves and Phase 1 begins
```

---

## How to Apply

1. Open Supabase Dashboard → SQL Editor
2. Paste contents of `migrations/intl_schemas_v1.sql`
3. Run
4. Go to Settings → API → Add `fr_research`, `hk_research` to exposed schemas
5. Verify:
```sql
SELECT schema_name FROM information_schema.schemata
WHERE schema_name IN ('fr_research', 'hk_research');
-- Expected: 2 rows
```
