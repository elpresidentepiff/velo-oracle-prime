-- MODEL-TRUTH-03 — Canonical Learning Events
-- NOT APPLIED by this migration file alone. Apply via Supabase SQL editor /
-- migration runner when the operator authorises. No write happens until
-- scripts/ops/build_canonical_learning_events.py is run with --execute.

CREATE TABLE IF NOT EXISTS public.canonical_learning_events (
    id                     BIGSERIAL   PRIMARY KEY,
    run_date               DATE        NOT NULL,
    race_id                TEXT        NOT NULL,
    model_name             TEXT        NOT NULL,
    lane_name              TEXT,
    horse                  TEXT,
    horse_id               TEXT,
    source_scorecard_id    BIGINT,
    source_field           TEXT,
    rank                   INTEGER,
    score                  NUMERIC,
    sp_dec                 NUMERIC,
    result_position        INTEGER,
    win                    BOOLEAN,
    frame                  BOOLEAN,
    policy_decision        TEXT,
    stake_authorised       BOOLEAN,
    dashboard_visible      BOOLEAN,
    learning_class         TEXT        NOT NULL,
    event_type             TEXT        NOT NULL,
    promotion_eligible     BOOLEAN     NOT NULL DEFAULT false,
    promotion_block_reason TEXT,
    lesson                 TEXT,
    evidence               JSONB,
    generated_from_commit  TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT canonical_learning_events_unique_row
        UNIQUE (run_date, race_id, model_name, lane_name, horse_id, learning_class, event_type)
);

CREATE INDEX IF NOT EXISTS idx_cle_run_date           ON public.canonical_learning_events (run_date);
CREATE INDEX IF NOT EXISTS idx_cle_race_id            ON public.canonical_learning_events (race_id);
CREATE INDEX IF NOT EXISTS idx_cle_model_name         ON public.canonical_learning_events (model_name);
CREATE INDEX IF NOT EXISTS idx_cle_learning_class     ON public.canonical_learning_events (learning_class);
CREATE INDEX IF NOT EXISTS idx_cle_event_type         ON public.canonical_learning_events (event_type);
CREATE INDEX IF NOT EXISTS idx_cle_promotion_eligible ON public.canonical_learning_events (promotion_eligible);
