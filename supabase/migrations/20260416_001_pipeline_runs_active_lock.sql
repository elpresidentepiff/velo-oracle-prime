-- Enforce one active pipeline run per service_name + source_date.
-- This is the DB-backed concurrency guard for trigger admission and child-run reuse.

CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_runs_active_service_date
ON public.pipeline_runs (service_name, source_date)
WHERE run_state = 'running';
