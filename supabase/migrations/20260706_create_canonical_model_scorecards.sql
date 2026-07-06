-- MODEL-TRUTH-02 — Canonical Model Scorecard persistence contract
-- NOT APPLIED by this migration file alone in CI. Apply via Supabase migration
-- runner when the operator authorises. No write happens until
-- scripts/ops/persist_canonical_model_scorecard.py is run with --execute.

CREATE TABLE IF NOT EXISTS public.canonical_model_scorecards (
    id                    BIGSERIAL   PRIMARY KEY,
    run_date              DATE        NOT NULL,
    race_id               TEXT        NOT NULL,
    course                TEXT,
    off_time              TEXT,
    model_name            TEXT        NOT NULL,
    lane_name              TEXT,
    source_path           TEXT        NOT NULL,
    source_field          TEXT,
    sort_direction        TEXT,
    rank                  INTEGER,
    horse                 TEXT,
    horse_id              TEXT,
    score                 NUMERIC,
    sp_dec                NUMERIC,
    result_position       INTEGER,
    win                   BOOLEAN,
    frame                 BOOLEAN,
    policy_decision       TEXT,
    stake_authorised      BOOLEAN,
    dashboard_visible     BOOLEAN,
    learning_class        TEXT,
    tie_status            TEXT,
    notes                 TEXT,
    generated_from_commit TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT canonical_model_scorecards_unique_row
        UNIQUE (run_date, race_id, model_name, lane_name, source_path, source_field, horse_id, rank)
);

CREATE INDEX IF NOT EXISTS idx_cms_run_date          ON public.canonical_model_scorecards (run_date);
CREATE INDEX IF NOT EXISTS idx_cms_race_id           ON public.canonical_model_scorecards (race_id);
CREATE INDEX IF NOT EXISTS idx_cms_model_name        ON public.canonical_model_scorecards (model_name);
CREATE INDEX IF NOT EXISTS idx_cms_learning_class    ON public.canonical_model_scorecards (learning_class);
CREATE INDEX IF NOT EXISTS idx_cms_win               ON public.canonical_model_scorecards (win);
CREATE INDEX IF NOT EXISTS idx_cms_dashboard_visible ON public.canonical_model_scorecards (dashboard_visible);
