-- migration: 20260710_001_add_in_running_comment
-- Adds RP's per-horse in-running comment (e.g. "Made all, pushed along before
-- 3 out, ran on well") to the horse-run ledger, so it can be surfaced in
-- future-built passports. Wired from run_results_sigma.py Step 13
-- (ingest_results_to_horse_runs.py) onward starting 2026-07-10 -- historical
-- rows before this date will have NULL here, not backfilled.

ALTER TABLE racing_horse_runs
    ADD COLUMN IF NOT EXISTS in_running_comment TEXT;

COMMENT ON COLUMN racing_horse_runs.in_running_comment IS
    'RP post-race in-running comment for this horse in this run, e.g. "Made all, pushed along before 3 out". NULL for runs ingested before 2026-07-10.';
