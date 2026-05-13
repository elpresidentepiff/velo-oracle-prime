-- VÉLØ Ops Worker Phase 1 — Learning Event Store
-- NOT APPLIED. Dry-run / contract only in Phase 1.
-- Apply manually when Phase 2 live execution is authorised.

CREATE TABLE IF NOT EXISTS public.velo_learning_events (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_date             DATE        NOT NULL,
    race_id              TEXT        NOT NULL,
    horse_id             TEXT,
    event_type           TEXT        NOT NULL,
    event_id             TEXT        NOT NULL,
    target_state_name    TEXT        NOT NULL,
    consumption_id       TEXT        NOT NULL,
    prediction           JSONB       NOT NULL,
    result               JSONB       NOT NULL,
    sidecars             JSONB       NOT NULL DEFAULT '{}'::jsonb,
    learning_allowed     BOOLEAN     NOT NULL DEFAULT false,
    missing_hfs_context  BOOLEAN     NOT NULL DEFAULT false,
    consumed_shadow      BOOLEAN     NOT NULL DEFAULT false,
    consumed_live        BOOLEAN     NOT NULL DEFAULT false,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, target_state_name),
    UNIQUE (consumption_id)
);

CREATE INDEX IF NOT EXISTS idx_velo_learning_events_run_date  ON public.velo_learning_events (run_date);
CREATE INDEX IF NOT EXISTS idx_velo_learning_events_race_id   ON public.velo_learning_events (race_id);
CREATE INDEX IF NOT EXISTS idx_velo_learning_events_target    ON public.velo_learning_events (target_state_name);
