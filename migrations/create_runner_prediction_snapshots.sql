-- Issue #80: Per-runner prediction snapshot storage
-- Creates runner_prediction_snapshots table in Supabase.
--
-- Purpose: Store full per-runner scored output for every scored race so that
-- Mid-Price Hunter Phase 2 can compute winner_mds - top_mds delta features,
-- and Sigma can query full-field runner context instead of only top-pick verdicts.
--
-- Safety: this table is append-only storage. It has no write-back path to
-- live scoring, routing, or execution. live_scoring_changed is always False.
--
-- Run once in Supabase SQL Editor or via psql:
--   psql $DATABASE_URL -f migrations/create_runner_prediction_snapshots.sql

CREATE TABLE IF NOT EXISTS runner_prediction_snapshots (
    id                      BIGSERIAL PRIMARY KEY,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    race_date               DATE        NOT NULL,
    race_id                 TEXT        NOT NULL,
    course                  TEXT,
    off_time                TEXT,
    tier                    TEXT,
    rank                    INTEGER     NOT NULL,  -- 0 = top pick, 1 = second, etc.
    horse                   TEXT,
    horse_id                TEXT,

    -- Core scoring outputs
    velo_prime_prob         NUMERIC(8,6),
    sqpe_v17_prob           NUMERIC(8,6),
    market_deception_score  NUMERIC(8,6),
    improvement_score       NUMERIC(8,6),
    place_prob              NUMERIC(8,6),
    longshot_prob           NUMERIC(8,6),
    release_day_prob        NUMERIC(8,6),
    comment_intel_score     NUMERIC(8,6),
    mark_compression_score  NUMERIC(8,6),
    spotlight_score         NUMERIC(8,6),
    postdata_score          NUMERIC(8,6),  -- 0% coverage currently; stored when available
    plot_conviction         NUMERIC(8,6),  -- 0% coverage currently; stored when available

    -- Race context derived at snapshot time
    top_pick_name           TEXT,
    top_pick_vp             NUMERIC(8,6),
    prob_gap                NUMERIC(8,6),  -- top_vp - this_runner_vp (0.0 for rank=0)

    -- Flags
    cash_run_flag           BOOLEAN,
    setup_run_flag          BOOLEAN,
    decoy_support_flag      BOOLEAN,
    tie_gate_fires          BOOLEAN,
    tie_gate_tier_upgrade   TEXT,

    -- RPD
    rpd_tag                 TEXT,
    rpd_confidence          NUMERIC(6,4),
    rpd_evidence_codes      JSONB,

    -- RPDC
    rpdc_primary_tag        TEXT,
    rpdc_release_score      NUMERIC(6,4),
    rpdc_cash_window_flag   BOOLEAN,
    rpdc_tags               JSONB,

    -- Ensemble metadata
    active_components       JSONB,
    excluded_from_ensemble  JSONB,
    assigned_product        TEXT,
    confidence_level        TEXT,
    decision_tier           TEXT,
    execution_allowed       BOOLEAN,
    race_archetype          TEXT,
    archetype_confidence    TEXT,
    router_reasons          JSONB,

    -- Market data (not always populated pre-race)
    sp_dec                  NUMERIC(8,4),
    is_fav                  BOOLEAN,

    -- Safety invariants: always False, never writable from outside
    live_scoring_changed    BOOLEAN NOT NULL DEFAULT FALSE,
    write_execution_allowed BOOLEAN NOT NULL DEFAULT FALSE
);

-- Index for Mid-Price Hunter Phase 2 delta queries (winner join by race_id + date)
CREATE INDEX IF NOT EXISTS idx_rps_race_id_date
    ON runner_prediction_snapshots (race_id, race_date);

-- Index for Sigma queries (all runners for a given date)
CREATE INDEX IF NOT EXISTS idx_rps_race_date
    ON runner_prediction_snapshots (race_date);

-- Index for horse-level lookups across dates
CREATE INDEX IF NOT EXISTS idx_rps_horse_date
    ON runner_prediction_snapshots (horse_id, race_date);

COMMENT ON TABLE runner_prediction_snapshots IS
    'Full per-runner prediction snapshots. Append-only. No write-back to scoring path. Issue #80.';
