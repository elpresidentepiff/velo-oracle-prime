-- VÉLØ International Schemas — Migration V1
-- Apply via: Supabase SQL Editor or psql
-- Date: 2026-05-23
-- Schemas: fr_research, hk_research
-- These are cold research schemas. NEVER mixed into public.* or velo_* tables.

-- ─────────────────────────────────────────────────────────────────────────────
-- CREATE SCHEMAS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS fr_research;
CREATE SCHEMA IF NOT EXISTS hk_research;


-- ─────────────────────────────────────────────────────────────────────────────
-- FRANCE (fr_research)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fr_research.fr_races (
    race_id           TEXT PRIMARY KEY,
    meeting_date      DATE,
    course            TEXT,
    region            TEXT DEFAULT 'FR',
    off_time          TEXT,
    off_dt            TEXT,
    race_name         TEXT,
    distance_round    TEXT,
    distance_f        FLOAT,
    pattern           TEXT,
    race_class        TEXT,
    race_type         TEXT,
    age_band          TEXT,
    prize             FLOAT,
    field_size        INT,
    going             TEXT,
    going_penetrometer FLOAT,
    surface           TEXT,
    weather           TEXT,
    is_abandoned      BOOLEAN DEFAULT FALSE,
    race_status       TEXT,
    quintet_plus      BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fr_research.fr_runners (
    race_id           TEXT NOT NULL,
    horse_id          TEXT NOT NULL,
    horse_name        TEXT,
    draw              INT,
    weight_kg         FLOAT,
    age               INT,
    sex               TEXT,
    jockey_id         TEXT,
    jockey_name       TEXT,
    trainer_id        TEXT,
    trainer_name      TEXT,
    odds_open         FLOAT,
    odds_live         FLOAT,
    fav_flag          BOOLEAN,
    rpr               FLOAT,
    ts                FLOAT,
    or_rating         FLOAT,
    valeur_rating     FLOAT,
    form              TEXT,
    comment           TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS fr_research.fr_results (
    race_id           TEXT NOT NULL,
    horse_id          TEXT NOT NULL,
    horse_name        TEXT,
    finish_position   INT,
    position_text     TEXT,
    beaten_distance   FLOAT,
    sp                FLOAT,
    win_flag          BOOLEAN,
    place_flag        BOOLEAN,
    result_status     TEXT,
    jockey_name       TEXT,
    trainer_name      TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS fr_research.fr_market_snapshots (
    race_id           TEXT NOT NULL,
    horse_id          TEXT NOT NULL,
    snapshot_time     TIMESTAMPTZ,
    odds              FLOAT,
    source            TEXT DEFAULT 'api',
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS fr_research.fr_ingestion_log (
    id                BIGSERIAL PRIMARY KEY,
    run_date          TEXT,
    races_fetched     INT DEFAULT 0,
    runners_fetched   INT DEFAULT 0,
    results_fetched   INT DEFAULT 0,
    status            TEXT,
    error_message     TEXT,
    raw_payload       JSONB,
    source_url        TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fr_research.fr_verdicts (
    race_id           TEXT NOT NULL,
    horse_id          TEXT NOT NULL,
    horse_name        TEXT,
    velo_prime_prob   FLOAT,
    rpr_vs_field      FLOAT,
    decision_tier     TEXT,
    verdict_date      DATE,
    model_version     TEXT DEFAULT 'FR_V1_SHADOW',
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS fr_research.fr_sigma_ledger (
    race_id           TEXT NOT NULL,
    horse_id          TEXT NOT NULL,
    verdict_date      DATE,
    velo_prime_prob   FLOAT,
    decision_tier     TEXT,
    outcome           TEXT,
    sp                FLOAT,
    miss_reason       TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (race_id, horse_id)
);


-- ─────────────────────────────────────────────────────────────────────────────
-- HONG KONG (hk_research)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS hk_research.hk_races (
    race_id           TEXT PRIMARY KEY,
    meeting_date      DATE,
    course            TEXT,
    region            TEXT DEFAULT 'HK',
    off_time          TEXT,
    off_dt            TEXT,
    race_name         TEXT,
    distance_round    TEXT,
    distance_f        FLOAT,
    distance_m        INT,
    hk_class          INT,
    race_type         TEXT,
    age_band          TEXT,
    prize             FLOAT,
    field_size        INT,
    going             TEXT,
    surface           TEXT DEFAULT 'Turf',
    is_abandoned      BOOLEAN DEFAULT FALSE,
    race_status       TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hk_research.hk_runners (
    race_id           TEXT NOT NULL,
    horse_id          TEXT NOT NULL,
    horse_name        TEXT,
    draw              INT,
    weight_kg         FLOAT,
    age               INT,
    sex               TEXT,
    jockey_id         TEXT,
    jockey_name       TEXT,
    trainer_id        TEXT,
    trainer_name      TEXT,
    hk_class          INT,
    griffin_flag      BOOLEAN DEFAULT FALSE,
    barrier_trial_rpr FLOAT,
    class_trajectory  INT,
    odds_open         FLOAT,
    odds_live         FLOAT,
    fav_flag          BOOLEAN,
    rpr               FLOAT,
    ts                FLOAT,
    or_rating         FLOAT,
    form              TEXT,
    comment           TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS hk_research.hk_results (
    race_id           TEXT NOT NULL,
    horse_id          TEXT NOT NULL,
    horse_name        TEXT,
    finish_position   INT,
    position_text     TEXT,
    beaten_distance   FLOAT,
    sp                FLOAT,
    win_flag          BOOLEAN,
    place_flag        BOOLEAN,
    result_status     TEXT,
    jockey_name       TEXT,
    trainer_name      TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS hk_research.hk_horse_history (
    horse_id          TEXT NOT NULL,
    race_id           TEXT NOT NULL,
    race_date         DATE,
    course            TEXT,
    distance_f        FLOAT,
    going             TEXT,
    hk_class          INT,
    finish_position   INT,
    sp                FLOAT,
    rpr               FLOAT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (horse_id, race_id)
);

CREATE TABLE IF NOT EXISTS hk_research.hk_sectionals (
    race_id           TEXT NOT NULL,
    horse_id          TEXT NOT NULL,
    split_400m        FLOAT,
    split_800m        FLOAT,
    split_1200m       FLOAT,
    final_time        FLOAT,
    pace_rank_400m    INT,
    source            TEXT DEFAULT 'hkjc',
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS hk_research.hk_draw_stats (
    course            TEXT NOT NULL,
    distance_m        INT NOT NULL,
    draw_position     INT NOT NULL,
    win_pct           FLOAT,
    place_pct         FLOAT,
    n_runs            INT DEFAULT 0,
    last_updated      DATE,
    PRIMARY KEY (course, distance_m, draw_position)
);

CREATE TABLE IF NOT EXISTS hk_research.hk_ingestion_log (
    id                BIGSERIAL PRIMARY KEY,
    run_date          TEXT,
    races_fetched     INT DEFAULT 0,
    runners_fetched   INT DEFAULT 0,
    results_fetched   INT DEFAULT 0,
    history_fetched   INT DEFAULT 0,
    status            TEXT,
    error_message     TEXT,
    source_url        TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hk_research.hk_verdicts (
    race_id           TEXT NOT NULL,
    horse_id          TEXT NOT NULL,
    horse_name        TEXT,
    velo_prime_prob   FLOAT,
    benter_prob       FLOAT,
    decision_tier     TEXT,
    verdict_date      DATE,
    model_version     TEXT DEFAULT 'HK_V1_SHADOW',
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS hk_research.hk_sigma_ledger (
    race_id           TEXT NOT NULL,
    horse_id          TEXT NOT NULL,
    verdict_date      DATE,
    velo_prime_prob   FLOAT,
    benter_prob       FLOAT,
    decision_tier     TEXT,
    outcome           TEXT,
    sp                FLOAT,
    miss_reason       TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (race_id, horse_id)
);


-- ─────────────────────────────────────────────────────────────────────────────
-- GRANT permissions to service role
-- (PostgREST requires explicit schema access)
-- ─────────────────────────────────────────────────────────────────────────────
GRANT USAGE ON SCHEMA fr_research TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA fr_research TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA fr_research TO service_role;

GRANT USAGE ON SCHEMA hk_research TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA hk_research TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA hk_research TO service_role;

-- ─────────────────────────────────────────────────────────────────────────────
-- PostgREST schema exposure
-- Add fr_research and hk_research to db_schema_cache in Supabase settings:
-- Settings → API → db_schema_cache
-- Add: fr_research, hk_research
-- ─────────────────────────────────────────────────────────────────────────────
