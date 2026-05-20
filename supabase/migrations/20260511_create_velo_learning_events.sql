-- Create velo_learning_events table
CREATE TABLE IF NOT EXISTS public.velo_learning_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_date DATE NOT NULL,
    race_id TEXT NOT NULL,
    horse_id TEXT,
    event_type TEXT NOT NULL,
    event_id TEXT NOT NULL,
    target_state_name TEXT,
    consumption_id TEXT,
    prediction JSONB NOT NULL,
    result JSONB NOT NULL,
    sidecars JSONB,
    learning_allowed BOOLEAN DEFAULT FALSE,
    missing_hfs_context BOOLEAN DEFAULT FALSE,
    consumed_shadow BOOLEAN DEFAULT FALSE,
    consumed_live BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(event_id, target_state_name),
    UNIQUE(consumption_id)
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_velo_learning_events_date ON public.velo_learning_events (run_date);
CREATE INDEX IF NOT EXISTS idx_velo_learning_events_race_id ON public.velo_learning_events (race_id);
