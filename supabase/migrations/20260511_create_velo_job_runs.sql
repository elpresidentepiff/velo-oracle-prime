-- Create velo_job_runs table
CREATE TABLE IF NOT EXISTS public.velo_job_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_date DATE NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_type TEXT,
    error_message TEXT,
    input_artifacts JSONB,
    output_artifacts JSONB,
    metrics JSONB,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_velo_job_runs_date ON public.velo_job_runs (run_date);
CREATE INDEX IF NOT EXISTS idx_velo_job_runs_type ON public.velo_job_runs (job_type);
