-- Fix: pipeline_runs.status must allow NULL for in-flight rows.
--
-- The PR2 migration (20260328_001) added a CHECK constraint requiring
-- status IN ('PASS','DEGRADED','FAIL'), but left the old NOT NULL constraint
-- and DEFAULT 'in_progress' in place. These conflict: any INSERT without
-- an explicit status gets the DEFAULT which violates the CHECK constraint.
--
-- Fix: drop NOT NULL + DROP DEFAULT so status is NULL while running, and
-- is only written on run close (matching the PR2 design intent).

ALTER TABLE pipeline_runs ALTER COLUMN status DROP NOT NULL;
ALTER TABLE pipeline_runs ALTER COLUMN status DROP DEFAULT;
