-- PR 2: pipeline_runs — separate lifecycle, provenance, and terminal truth
--
-- Three truths, three columns:
--   run_state      : running | completed          (lifecycle)
--   trigger_source : manual | github_actions_scheduled | github_actions_manual | api_manual (provenance)
--   status         : PASS | DEGRADED | FAIL       (terminal truth — NULL until run completes)
--
-- Before this migration:
--   - status held both lifecycle ('in_progress') and terminal ('PASS','DEGRADED','FAIL') values
--   - trigger_source was stuffed into environment as 'production/github_actions_scheduled'
--   - no age gate existed; stale runs could block new runs indefinitely
--
-- After this migration:
--   - status is only ever written on run close (NULL while running)
--   - run_state tracks whether a run is active
--   - trigger_source is a dedicated column
--   - environment reverts to its only true meaning: production | staging | local


-- ── Step 1: Add new columns ───────────────────────────────────────────────────

ALTER TABLE pipeline_runs
  ADD COLUMN IF NOT EXISTS run_state     TEXT DEFAULT 'completed',
  ADD COLUMN IF NOT EXISTS trigger_source TEXT DEFAULT 'manual';


-- ── Step 2: Backfill trigger_source from environment ─────────────────────────
-- Pattern: 'production/github_actions_scheduled' → 'github_actions_scheduled'
-- Pattern: 'production/github_actions_manual'    → 'github_actions_manual'
-- Pattern: 'production/api_manual'               → 'api_manual'
-- Pattern: 'production' / anything else          → 'manual'

UPDATE pipeline_runs
SET trigger_source = CASE
  WHEN environment LIKE '%/github_actions_scheduled' THEN 'github_actions_scheduled'
  WHEN environment LIKE '%/github_actions_manual'    THEN 'github_actions_manual'
  WHEN environment LIKE '%/api_manual'               THEN 'api_manual'
  WHEN environment LIKE '%/api%'                     THEN 'api_manual'
  ELSE 'manual'
END;

-- Strip the trigger_source suffix from environment (restore it to env-only truth)
UPDATE pipeline_runs
SET environment = SPLIT_PART(environment, '/', 1)
WHERE environment LIKE '%/%';


-- ── Step 3: Close all in_progress rows (migration-time cleanup) ───────────────
-- Any run still showing in_progress at migration time is stale.
-- Runs > 24h old → FAIL (clearly orphaned)
-- Runs ≤ 24h old → DEGRADED (may have been live; we can't confirm success)

UPDATE pipeline_runs
SET
  status        = 'FAIL',
  run_state     = 'completed',
  finished_at   = COALESCE(finished_at, NOW()),
  error_message = 'Closed by PR2 migration: stale run (age > 24h)'
WHERE status = 'in_progress'
  AND started_at < NOW() - INTERVAL '24 hours';

UPDATE pipeline_runs
SET
  status        = 'DEGRADED',
  run_state     = 'completed',
  finished_at   = COALESCE(finished_at, NOW()),
  error_message = 'Closed by PR2 migration: run_state column introduction'
WHERE status = 'in_progress';


-- ── Step 4: Normalise abandoned → FAIL ───────────────────────────────────────
-- 'abandoned' was a lifecycle state, not a terminal truth.
-- An abandoned run is a failed run.

UPDATE pipeline_runs
SET status = 'FAIL'
WHERE status = 'abandoned';


-- ── Step 5: Constraints ───────────────────────────────────────────────────────

-- run_state enum
ALTER TABLE pipeline_runs
  ADD CONSTRAINT pipeline_runs_run_state_enum
  CHECK (run_state IN ('running', 'completed'));

-- Drop old status constraint (allowed 'in_progress' and 'abandoned')
ALTER TABLE pipeline_runs
  DROP CONSTRAINT IF EXISTS pipeline_runs_status_enum;

-- Drop the old DEFAULT 'in_progress' — status is now written only on close (NULL while running).
-- Without this, INSERT without explicit status gets 'in_progress' which violates the new constraint.
ALTER TABLE pipeline_runs ALTER COLUMN status DROP DEFAULT;

-- New status constraint: terminal truth only. NULL is allowed (run in flight).
-- PostgreSQL CHECK constraints allow NULL by default — this is intentional.
ALTER TABLE pipeline_runs
  ADD CONSTRAINT pipeline_runs_status_enum
  CHECK (status IN ('PASS', 'DEGRADED', 'FAIL'));

-- trigger_source enum
ALTER TABLE pipeline_runs
  ADD CONSTRAINT pipeline_runs_trigger_source_enum
  CHECK (trigger_source IN ('manual', 'github_actions_scheduled', 'github_actions_manual', 'api_manual'));
