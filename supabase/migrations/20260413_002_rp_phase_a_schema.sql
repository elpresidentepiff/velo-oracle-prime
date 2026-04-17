-- migration: 20260413_002_rp_phase_a_schema
-- Racing Post Phase A intelligence tables.
-- Phase A scope: entity alias resolution + trainer/jockey stats enrichment.
-- These tables enrich RPDC tags with RP-sourced strike rates not available
-- from the Racing API (first-time headgear win rates, post-gelding rates,
-- course-specialist rates, jockey booking lead times).
-- Added 2026-04-13.

-- ── rp_entity_aliases ─────────────────────────────────────────────────────────
-- Maps Racing Post entity IDs to Racing API IDs (and other alias types).
-- Grows over time as resolution runs — verified=FALSE until manually confirmed.
CREATE TABLE IF NOT EXISTS rp_entity_aliases (
    id              BIGSERIAL PRIMARY KEY,
    entity_type     TEXT NOT NULL,   -- 'trainer','jockey','horse','course','owner'
    rp_id           TEXT NOT NULL,   -- Racing Post numeric ID (as text)
    alias_type      TEXT NOT NULL,   -- 'racing_api_id','rp_slug','name_canonical'
    alias_value     TEXT NOT NULL,
    match_score     NUMERIC(4,3),    -- fuzzy match confidence 0.0–1.0 (NULL = exact)
    verified        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (entity_type, rp_id, alias_type)
);

CREATE INDEX IF NOT EXISTS idx_rp_aliases_racing_api
    ON rp_entity_aliases (alias_type, alias_value)
    WHERE alias_type = 'racing_api_id';

CREATE INDEX IF NOT EXISTS idx_rp_aliases_type_entity
    ON rp_entity_aliases (entity_type, rp_id);

-- ── rp_trainer_stats ──────────────────────────────────────────────────────────
-- Trainer strike rates scraped from Racing Post trainer stats pages.
-- Primary key: rp_trainer_id (RP numeric ID).
-- Joined to trainer_campaign_profile via rp_entity_aliases.
CREATE TABLE IF NOT EXISTS rp_trainer_stats (
    rp_trainer_id           TEXT PRIMARY KEY,
    racing_api_id           TEXT,           -- denormalised join key from aliases
    trainer_name            TEXT NOT NULL,
    rp_slug                 TEXT,           -- URL slug e.g. 'william-haggas'

    -- Rolling windows
    runs_14d                INTEGER,
    wins_14d                INTEGER,
    win_rate_14d            NUMERIC(5,1),
    runs_30d                INTEGER,
    wins_30d                INTEGER,
    win_rate_30d            NUMERIC(5,1),
    runs_180d               INTEGER,
    wins_180d               INTEGER,
    win_rate_180d           NUMERIC(5,1),

    -- Campaign run number (derived from RP stats or Racing API)
    win_rate_run1           NUMERIC(5,1),   -- first run after 30d+ break
    win_rate_run2           NUMERIC(5,1),
    win_rate_run3           NUMERIC(5,1),
    preferred_release_run   INTEGER,        -- run number with peak strike rate

    -- Conditions
    win_rate_good_plus      NUMERIC(5,1),
    win_rate_soft_plus      NUMERIC(5,1),
    win_rate_aw             NUMERIC(5,1),

    -- Rest buckets
    win_rate_8_21d          NUMERIC(5,1),
    win_rate_22_45d         NUMERIC(5,1),
    win_rate_46_90d         NUMERIC(5,1),
    win_rate_90d_plus       NUMERIC(5,1),

    -- Situational — key RPDC signals
    win_rate_mark_relief          NUMERIC(5,1),
    win_rate_class_drop           NUMERIC(5,1),
    win_rate_first_time_headgear  NUMERIC(5,1),
    win_rate_post_gelding         NUMERIC(5,1),

    -- Stable heat flags
    stable_heat_flag        BOOLEAN DEFAULT FALSE,
    stable_heat_score       NUMERIC(5,1),   -- (14d_rate / 30d_rate) - 1.0

    -- Top courses and jockeys (arrays of names)
    top_courses             TEXT[],
    top_jockeys             TEXT[],

    -- Metadata
    scraped_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rp_trainer_stats_racing_api
    ON rp_trainer_stats (racing_api_id);

-- ── rp_jockey_stats ───────────────────────────────────────────────────────────
-- Jockey strike rates from Racing Post jockey stats pages.
CREATE TABLE IF NOT EXISTS rp_jockey_stats (
    rp_jockey_id            TEXT PRIMARY KEY,
    racing_api_id           TEXT,
    jockey_name             TEXT NOT NULL,
    rp_slug                 TEXT,
    claim_lbs               INTEGER DEFAULT 0,

    -- Rolling windows
    runs_14d                INTEGER,
    wins_14d                INTEGER,
    win_rate_14d            NUMERIC(5,1),
    runs_30d                INTEGER,
    wins_30d                INTEGER,
    win_rate_30d            NUMERIC(5,1),
    runs_180d               INTEGER,
    wins_180d               INTEGER,
    win_rate_180d           NUMERIC(5,1),

    -- Booking split
    win_rate_retained       NUMERIC(5,1),   -- on retained yard horses
    win_rate_outside        NUMERIC(5,1),   -- outside booking

    -- Conditions
    win_rate_good_plus      NUMERIC(5,1),
    win_rate_soft_plus      NUMERIC(5,1),
    win_rate_aw             NUMERIC(5,1),
    win_rate_sprint         NUMERIC(5,1),   -- 5f–7f
    win_rate_middle         NUMERIC(5,1),   -- 8f–11f
    win_rate_stayer         NUMERIC(5,1),   -- 12f+

    -- Intent signals
    avg_days_to_booking     NUMERIC(5,1),   -- average booking lead time in days
    late_booking_rate       NUMERIC(5,1),   -- % of rides booked within 24h

    -- Course and trainer affiliations
    top_courses             TEXT[],
    top_trainers            TEXT[],

    scraped_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rp_jockey_stats_racing_api
    ON rp_jockey_stats (racing_api_id);

-- ── rp_ingestion_runs ─────────────────────────────────────────────────────────
-- Tracks each RP ingestion run for auditability and rate-limit management.
CREATE TABLE IF NOT EXISTS rp_ingestion_runs (
    id              BIGSERIAL PRIMARY KEY,
    run_type        TEXT NOT NULL,   -- 'trainer_stats','jockey_stats','horse_profile','alias_seed'
    target_id       TEXT,            -- entity ID being processed (NULL = batch)
    target_name     TEXT,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    records_fetched INTEGER DEFAULT 0,
    records_written INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'running',  -- 'running','pass','fail','partial'
    error_note      TEXT
);
