-- ============================================================
-- VÉLØ HK RESEARCH LANE — Supabase Schema
-- Schema: hk_research
-- Purpose: Archive-only. No production verdict authority.
--           No doctrine learning. No phase-gate effect.
-- ============================================================
-- Run as: Supabase SQL Editor
-- Prerequisites: CREATE SCHEMA IF NOT EXISTS hk_research;

-- ── HK_RACES ────────────────────────────────────────────────
-- Core race metadata. One row per HK race.
CREATE TABLE IF NOT EXISTS hk_research.hk_races (
    race_id          TEXT PRIMARY KEY,  -- e.g. rac_XXXXXXX
    meeting_date     DATE NOT NULL,
    course           TEXT NOT NULL,      -- 'Happy Valley' or 'Sha Tin'
    region           TEXT NOT NULL DEFAULT 'HK',
    off_time         TIME,
    off_dt           TIMESTAMPTZ,
    race_name        TEXT,
    distance_round   TEXT,
    distance_f       INTEGER,
    pattern          TEXT,
    race_class       TEXT,
    race_type        TEXT,              -- 'Flat' | 'Handicap' etc
    age_band         TEXT,
    prize            NUMERIC,
    field_size       INTEGER,
    going            TEXT,
    surface          TEXT,
    weather          TEXT,
    big_race         BOOLEAN DEFAULT FALSE,
    is_abandoned     BOOLEAN DEFAULT FALSE,
    race_status      TEXT,
    imported_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hk_races_date ON hk_research.hk_races(meeting_date);
CREATE INDEX IF NOT EXISTS idx_hk_races_course ON hk_research.hk_races(course);
CREATE INDEX IF NOT EXISTS idx_hk_races_imported ON hk_research.hk_races(imported_at DESC);

-- ── HK_RUNNERS ──────────────────────────────────────────────
-- Runner snapshot at time of racecard. One row per horse.
CREATE TABLE IF NOT EXISTS hk_research.hk_runners (
    id               BIGSERIAL PRIMARY KEY,
    race_id          TEXT NOT NULL REFERENCES hk_research.hk_races(race_id),
    horse_id         TEXT NOT NULL,
    horse_name       TEXT NOT NULL,
    draw             INTEGER,
    weight_kg        NUMERIC,
    rating           NUMERIC,
    age              INTEGER,
    sex              TEXT,
    jockey_id        TEXT,
    jockey_name      TEXT,
    trainer_id       TEXT,
    trainer_name     TEXT,
    barrier          INTEGER,
    odds_open        NUMERIC,
    odds_live        NUMERIC,
    fav_flag         BOOLEAN,
    rpr              NUMERIC,
    ts               NUMERIC,
    or_rating        NUMERIC,
    form             TEXT,
    Comment          TEXT,
    imported_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(race_id, horse_id)
);

CREATE INDEX IF NOT EXISTS idx_hk_runners_race ON hk_research.hk_runners(race_id);
CREATE INDEX IF NOT EXISTS idx_hk_runners_horse ON hk_research.hk_runners(horse_id);
CREATE INDEX IF NOT EXISTS idx_hk_runners_trainer ON hk_research.hk_runners(trainer_id);
CREATE INDEX IF NOT EXISTS idx_hk_runners_jockey ON hk_research.hk_runners(jockey_id);

-- ── HK_RESULTS ──────────────────────────────────────────────
-- Post-race results. One row per horse that raced.
CREATE TABLE IF NOT EXISTS hk_research.hk_results (
    id               BIGSERIAL PRIMARY KEY,
    race_id          TEXT NOT NULL REFERENCES hk_research.hk_races(race_id),
    horse_id         TEXT NOT NULL,
    horse_name       TEXT NOT NULL,
    finish_position  INTEGER,
    position_text    TEXT,              -- '1' '2' '3' 'PU' 'F' etc
    beaten_distance  TEXT,
    sp               NUMERIC,
    win_flag         BOOLEAN,
    place_flag       BOOLEAN,
    result_status    TEXT,              -- 'finished' | 'pulled_up' | 'fell' etc
    jockey_name      TEXT,
    trainer_name     TEXT,
    weight_carried   TEXT,
    imported_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(race_id, horse_id)
);

CREATE INDEX IF NOT EXISTS idx_hk_results_race ON hk_research.hk_results(race_id);
CREATE INDEX IF NOT EXISTS idx_hk_results_horse ON hk_research.hk_results(horse_id);
CREATE INDEX IF NOT EXISTS idx_hk_results_date ON hk_research.hk_results(imported_at DESC);

-- ── HK_HORSE_HISTORY ───────────────────────────────────────
-- Historical runs for each horse. Built incrementally from racecard fetches.
CREATE TABLE IF NOT EXISTS hk_research.hk_horse_history (
    id               BIGSERIAL PRIMARY KEY,
    horse_id         TEXT NOT NULL,
    horse_name       TEXT,
    race_id          TEXT REFERENCES hk_research.hk_races(race_id),
    meeting_date     DATE,
    course           TEXT,
    distance_f       INTEGER,
    surface          TEXT,
    race_class       TEXT,
    going            TEXT,
    draw             INTEGER,
    finish_position  INTEGER,
    position_text    TEXT,
    sp               NUMERIC,
    weight_kg        NUMERIC,
    jockey_name      TEXT,
    trainer_name     TEXT,
    rpr              NUMERIC,
    ts               NUMERIC,
    form             TEXT,
    imported_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(horse_id, race_id)
);

CREATE INDEX IF NOT EXISTS idx_hk_horse_hist_horse ON hk_research.hk_horse_history(horse_id);
CREATE INDEX IF NOT EXISTS idx_hk_horse_hist_course ON hk_research.hk_horse_history(course);
CREATE INDEX IF NOT EXISTS idx_hk_horse_hist_date ON hk_research.hk_horse_history(meeting_date DESC);
CREATE INDEX IF NOT EXISTS idx_hk_horse_hist_dist ON hk_research.hk_horse_history(distance_f);

-- ── HK_TRAINER_STATS ───────────────────────────────────────
-- Trainer aggregate stats. Refreshed daily from hk_results.
CREATE TABLE IF NOT EXISTS hk_research.hk_trainer_stats (
    id               BIGSERIAL PRIMARY KEY,
    trainer_id       TEXT UNIQUE NOT NULL,
    trainer_name     TEXT,
    snapshot_date    DATE NOT NULL,
    total_runs       INTEGER DEFAULT 0,
    wins             INTEGER DEFAULT 0,
    places           INTEGER DEFAULT 0,
    win_pct          NUMERIC,
    place_pct        NUMERIC,
    roi_pct          NUMERIC,
    runs_14d         INTEGER DEFAULT 0,
    wins_14d         INTEGER DEFAULT 0,
    runs_30d         INTEGER DEFAULT 0,
    wins_30d         INTEGER DEFAULT 0,
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(trainer_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_hk_trainer_stats_name ON hk_research.hk_trainer_stats(trainer_name);
CREATE INDEX IF NOT EXISTS idx_hk_trainer_stats_date ON hk_research.hk_trainer_stats(snapshot_date DESC);

-- ── HK_JOCKEY_STATS ────────────────────────────────────────
-- Jockey aggregate stats. Refreshed daily from hk_results.
CREATE TABLE IF NOT EXISTS hk_research.hk_jockey_stats (
    id               BIGSERIAL PRIMARY KEY,
    jockey_id        TEXT UNIQUE NOT NULL,
    jockey_name      TEXT,
    snapshot_date    DATE NOT NULL,
    total_runs       INTEGER DEFAULT 0,
    wins             INTEGER DEFAULT 0,
    places           INTEGER DEFAULT 0,
    win_pct          NUMERIC,
    place_pct        NUMERIC,
    roi_pct          NUMERIC,
    runs_14d         INTEGER DEFAULT 0,
    wins_14d         INTEGER DEFAULT 0,
    runs_30d         INTEGER DEFAULT 0,
    wins_30d         INTEGER DEFAULT 0,
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(jockey_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_hk_jockey_stats_name ON hk_research.hk_jockey_stats(jockey_name);
CREATE INDEX IF NOT EXISTS idx_hk_jockey_stats_date ON hk_research.hk_jockey_stats(snapshot_date DESC);

-- ── HK_MARKET_SNAPSHOTS ─────────────────────────────────────
-- Timestamped odds movements. Written on each ingestion run.
CREATE TABLE IF NOT EXISTS hk_research.hk_market_snapshots (
    id               BIGSERIAL PRIMARY KEY,
    race_id          TEXT NOT NULL,
    horse_id         TEXT NOT NULL,
    snapshot_time    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    odds             NUMERIC,
    rank             INTEGER,           -- rank in the market at this time
    source           TEXT DEFAULT 'api',
    imported_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hk_mkt_race ON hk_research.hk_market_snapshots(race_id);
CREATE INDEX IF NOT EXISTS idx_hk_mkt_horse ON hk_research.hk_market_snapshots(horse_id);
CREATE INDEX IF NOT EXISTS idx_hk_mkt_time ON hk_research.hk_market_snapshots(snapshot_time DESC);

-- ── HK_INGESTION_LOG ────────────────────────────────────────
-- Audit trail for every HK ingestion run.
CREATE TABLE IF NOT EXISTS hk_research.hk_ingestion_log (
    id               BIGSERIAL PRIMARY KEY,
    run_date         DATE NOT NULL,
    races_fetched    INTEGER,
    runners_fetched  INTEGER,
    results_fetched  INTEGER,
    status           TEXT,             -- 'success' | 'partial' | 'failed'
    error_message    TEXT,
    raw_payload      JSONB,           -- raw API response for this run (replay power)
    source_url       TEXT,             -- API endpoint called
    fetched_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hk_log_date ON hk_research.hk_ingestion_log(run_date DESC);
CREATE INDEX IF NOT EXISTS idx_hk_log_fetched ON hk_research.hk_ingestion_log(fetched_at DESC);

-- ============================================================
-- RLS — hk_research is append-only archive
-- Service role gets full access. Anon gets read-only.
-- ============================================================
ALTER SCHEMA hk_research ENABLE ROW LEVEL SECURITY;

-- Service role: full access
CREATE POLICY "service_role_full_hk" ON hk_research.hk_races
    FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_full_hk_runners" ON hk_research.hk_runners
    FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_full_hk_results" ON hk_research.hk_results
    FOR ALL TO service_role USING (true);

-- Anon: read-only (for research queries)
CREATE POLICY "anon_read_hk" ON hk_research.hk_races
    FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read_hk_runners" ON hk_research.hk_runners
    FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read_hk_results" ON hk_research.hk_results
    FOR SELECT TO anon USING (true);

COMMENT ON SCHEMA hk_research IS 'VÉLØ HK research lane. Archive only. No production verdict authority.';
