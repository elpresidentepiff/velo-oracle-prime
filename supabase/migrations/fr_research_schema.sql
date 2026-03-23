-- ============================================================
-- VÉLØ FR RESEARCH LANE — Cold Archive Schema
-- Schema: fr_research
-- Purpose: Cold storage. No production verdict authority.
--           No doctrine learning. No phase-gate effect.
--           Archive-first. Analyze later if strategically chosen.
-- ============================================================
-- Run as: Supabase SQL Editor
-- Prerequisites: CREATE SCHEMA IF NOT EXISTS fr_research;

-- ── FR_RACES ───────────────────────────────────────────────
-- Core race metadata. One row per FR race.
CREATE TABLE IF NOT EXISTS fr_research.fr_races (
    race_id          TEXT PRIMARY KEY,
    meeting_date     DATE NOT NULL,
    course           TEXT NOT NULL,
    region           TEXT NOT NULL DEFAULT 'FR',
    off_time         TIME,
    off_dt           TIMESTAMPTZ,
    race_name        TEXT,
    distance_round   TEXT,
    distance_f       INTEGER,
    pattern          TEXT,
    race_class       TEXT,
    race_type        TEXT,
    age_band         TEXT,
    prize            NUMERIC,
    field_size       INTEGER,
    going            TEXT,
    surface          TEXT,
    weather          TEXT,
    is_abandoned     BOOLEAN DEFAULT FALSE,
    race_status      TEXT,
    imported_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fr_races_date ON fr_research.fr_races(meeting_date);
CREATE INDEX IF NOT EXISTS idx_fr_races_course ON fr_research.fr_races(course);
CREATE INDEX IF NOT EXISTS idx_fr_races_imported ON fr_research.fr_races(imported_at DESC);

-- ── FR_RUNNERS ──────────────────────────────────────────────
-- Runner snapshot at time of racecard.
CREATE TABLE IF NOT EXISTS fr_research.fr_runners (
    id               BIGSERIAL PRIMARY KEY,
    race_id          TEXT NOT NULL REFERENCES fr_research.fr_races(race_id),
    horse_id         TEXT NOT NULL,
    horse_name       TEXT NOT NULL,
    draw             INTEGER,
    weight_kg        NUMERIC,
    age              INTEGER,
    sex              TEXT,
    jockey_id        TEXT,
    jockey_name      TEXT,
    trainer_id       TEXT,
    trainer_name     TEXT,
    odds_open        NUMERIC,
    odds_live        NUMERIC,
    fav_flag         BOOLEAN,
    rpr              NUMERIC,
    ts               NUMERIC,
    or_rating        NUMERIC,
    form             TEXT,
    comment          TEXT,
    imported_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(race_id, horse_id)
);

CREATE INDEX IF NOT EXISTS idx_fr_runners_race ON fr_research.fr_runners(race_id);
CREATE INDEX IF NOT EXISTS idx_fr_runners_horse ON fr_research.fr_runners(horse_id);

-- ── FR_RESULTS ──────────────────────────────────────────────
-- Post-race results.
CREATE TABLE IF NOT EXISTS fr_research.fr_results (
    id               BIGSERIAL PRIMARY KEY,
    race_id          TEXT NOT NULL REFERENCES fr_research.fr_races(race_id),
    horse_id         TEXT NOT NULL,
    horse_name       TEXT NOT NULL,
    finish_position  INTEGER,
    position_text    TEXT,
    beaten_distance  TEXT,
    sp               NUMERIC,
    win_flag         BOOLEAN,
    place_flag       BOOLEAN,
    result_status    TEXT,
    jockey_name      TEXT,
    trainer_name     TEXT,
    imported_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(race_id, horse_id)
);

CREATE INDEX IF NOT EXISTS idx_fr_results_race ON fr_research.fr_results(race_id);
CREATE INDEX IF NOT EXISTS idx_fr_results_horse ON fr_research.fr_results(horse_id);

-- ── FR_MARKET_SNAPSHOTS ─────────────────────────────────────
-- Timestamped odds at ingestion time.
CREATE TABLE IF NOT EXISTS fr_research.fr_market_snapshots (
    id               BIGSERIAL PRIMARY KEY,
    race_id          TEXT NOT NULL,
    horse_id         TEXT NOT NULL,
    snapshot_time    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    odds             NUMERIC,
    rank             INTEGER,
    source           TEXT DEFAULT 'api',
    imported_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fr_mkt_race ON fr_research.fr_market_snapshots(race_id);
CREATE INDEX IF NOT EXISTS idx_fr_mkt_horse ON fr_research.fr_market_snapshots(horse_id);

-- ── FR_INGESTION_LOG ────────────────────────────────────────
-- Audit trail. Raw payload stored for replay power.
CREATE TABLE IF NOT EXISTS fr_research.fr_ingestion_log (
    id               BIGSERIAL PRIMARY KEY,
    run_date         DATE NOT NULL,
    races_fetched    INTEGER,
    runners_fetched  INTEGER,
    results_fetched  INTEGER,
    status           TEXT,
    error_message    TEXT,
    raw_payload      JSONB,          -- optional replay blob (HK only; FR cold archive omits for storage)
    source_url       TEXT,
    fetched_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fr_log_date ON fr_research.fr_ingestion_log(run_date DESC);
CREATE INDEX IF NOT EXISTS idx_fr_log_fetched ON fr_research.fr_ingestion_log(fetched_at DESC);

-- ============================================================
-- RLS — fr_research is cold archive
-- ============================================================
ALTER SCHEMA fr_research ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_full_fr" ON fr_research.fr_races
    FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_full_fr_runners" ON fr_research.fr_runners
    FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_full_fr_results" ON fr_research.fr_results
    FOR ALL TO service_role USING (true);

CREATE POLICY "anon_read_fr" ON fr_research.fr_races
    FOR SELECT TO anon USING (true);

COMMENT ON SCHEMA fr_research IS 'VÉLØ FR cold archive. Archive-only. No production verdict authority. No doctrine learning.';
