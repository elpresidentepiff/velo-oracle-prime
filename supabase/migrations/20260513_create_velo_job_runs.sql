-- VÉLØ Ops Worker Phase 1 — Job Run Tracking
-- NOT APPLIED. Dry-run / contract only in Phase 1.
-- Apply manually when Phase 2 live execution is authorised.

CREATE TABLE IF NOT EXISTS public.velo_job_runs (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_date          DATE        NOT NULL,
    job_type          TEXT        NOT NULL,
    status            TEXT        NOT NULL,
    started_at        TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    error_type        TEXT,
    error_message     TEXT,
    input_artifacts   JSONB       NOT NULL DEFAULT '{}'::jsonb,
    output_artifacts  JSONB       NOT NULL DEFAULT '{}'::jsonb,
    metrics           JSONB       NOT NULL DEFAULT '{}'::jsonb,
    retry_count       INT         NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_velo_job_runs_run_date  ON public.velo_job_runs (run_date);
CREATE INDEX IF NOT EXISTS idx_velo_job_runs_job_type  ON public.velo_job_runs (job_type);
CREATE INDEX IF NOT EXISTS idx_velo_job_runs_status    ON public.velo_job_runs (status);
