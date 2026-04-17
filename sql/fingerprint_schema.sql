-- ============================================================
-- Fingerprint Analog Layer — Schema
-- Reconstructed from Supabase via schema probing
-- 2026-04-08
-- ============================================================
-- Purpose: stores canonical race/runner fingerprint vectors,
-- their realized outcomes, nearest analog matches, and
-- per-runner analog signal summaries.
--
-- Design rules (DOCTRINE-locked):
--   - All tables are APPEND-ONLY (no updates, no deletes in production)
--   - All tables use IF NOT EXISTS / IF NOT NULL guards
--   - lineage (feature_version, signal_version) is mandatory
--   - shadow_only = TRUE until Stage 4 promotion
-- ============================================================

-- ────────────────────────────────────────────────────────────
-- race_fingerprint_vectors
--
-- One row per scored runner in a historical race.
-- Canonical fingerprint = 13 locked features + metadata.
-- Vector positions are column-based (not JSON/JSONB) for
-- Supabase query efficiency.
--
-- Confirmed column positions (via Supabase probing):
--   pos 1: id (BIGSERIAL PK)
--   pos 2: race_id (TEXT NOT NULL)
--   pos 3: runner_id (TEXT NOT NULL)
--   pos 4-5: unused (nullable)
--   pos 6: sqpe (NUMERIC NOT NULL)
--   pos 7: sqpe_band (TEXT)
--   pos 8: unused (nullable)
--   pos 9: sp_band (TEXT)
--   pos 10: trainer_signal_type (TEXT)
--   pos 11: trainer_ae (NUMERIC)
--   pos 12: trainer_ae_band (TEXT)
--   pos 13: class_movement_subtype (TEXT)
--   pos 14: days_since_run_band (TEXT)
--   pos 15: run_cycle_position (TEXT)
--   pos 16: distance_change_band (TEXT)
--   pos 17: going_band (TEXT)
--   pos 18: recent_form_state (TEXT)
--   pos 19: finish_consistency_band (TEXT)
--   pos 20: unused (nullable)
--   pos 21: feature_version (TEXT DEFAULT 'fingerprint_v1')
--   pos 22: created_at (TIMESTAMPTZ DEFAULT NOW())
-- ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS race_fingerprint_vectors (
    id                      BIGSERIAL PRIMARY KEY,
    race_id                 TEXT        NOT NULL,
    runner_id               TEXT        NOT NULL,

    -- 13 locked features (canonical fingerprint)
    sqpe                    NUMERIC(6,4)   NOT NULL,
    sqpe_band               TEXT,
    sp_band                 TEXT,
    trainer_ae              NUMERIC(6,4),
    trainer_ae_band         TEXT,
    trainer_signal_type     TEXT,
    class_movement_subtype  TEXT,
    days_since_run_band     TEXT,
    run_cycle_position      TEXT,
    distance_change_band    TEXT,
    going_band              TEXT,
    recent_form_state       TEXT,
    finish_consistency_band TEXT,

    -- Lineage (mandatory)
    feature_version         TEXT        DEFAULT 'fingerprint_v1',
    signal_version          TEXT        DEFAULT 'phase35_locked',
    created_at              TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT rfv_race_runner_uniq UNIQUE (race_id, runner_id)
);

CREATE INDEX IF NOT EXISTS idx_rfv_race_id      ON race_fingerprint_vectors (race_id);
CREATE INDEX IF NOT EXISTS idx_rfv_runner_id    ON race_fingerprint_vectors (runner_id);
CREATE INDEX IF NOT EXISTS idx_rfv_sqpe_band    ON race_fingerprint_vectors (sqpe_band);
CREATE INDEX IF NOT EXISTS idx_rfv_feature_ver  ON race_fingerprint_vectors (feature_version);
CREATE INDEX IF NOT EXISTS idx_rfv_created      ON race_fingerprint_vectors (created_at DESC);


-- ────────────────────────────────────────────────────────────
-- race_fingerprint_outcomes
--
-- One row per runner in race_fingerprint_vectors,
-- written AFTER the race has a result.
--
-- Confirmed columns (via probing):
--   pos 1: id (BIGSERIAL PK, auto=2 in test)
--   pos 2: runner_id (NOT NULL)
--   pos 3: race_id (NOT NULL)
--   pos 4-5: TBC (nullable)
--   pos 6: similarity_score (NUMERIC, nullable)
--   pos 7-17: TBC (nullable)
--   pos 18: created_at
--
-- Known fields:
--   winner_id = horse_id of the winner
--   sp = starting price (Betfair SP decimal)
--   win = bool
--   placed = bool
--   finish_position = int
--   winning_distance = text (e.g. "1.25L", "sh", "hd")
-- ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS race_fingerprint_outcomes (
    id                    BIGSERIAL PRIMARY KEY,
    race_id               TEXT        NOT NULL,
    runner_id             TEXT        NOT NULL,

    -- Outcome facts
    winner_id             TEXT,
    sp                   NUMERIC(8,2),
    win                  BOOLEAN,
    placed               BOOLEAN,
    finish_position      INTEGER,
    winning_distance     TEXT,

    -- Lineage
    feature_version       TEXT        DEFAULT 'fingerprint_v1',
    signal_version       TEXT        DEFAULT 'phase35_locked',
    created_at           TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT rfo_race_runner_uniq UNIQUE (race_id, runner_id)
);

CREATE INDEX IF NOT EXISTS idx_rfo_race_id    ON race_fingerprint_outcomes (race_id);
CREATE INDEX IF NOT EXISTS idx_rfo_winner_id  ON race_fingerprint_outcomes (winner_id);
CREATE INDEX IF NOT EXISTS idx_rfo_created    ON race_fingerprint_outcomes (created_at DESC);


-- ────────────────────────────────────────────────────────────
-- race_fingerprint_analogs
--
-- One row per analog match found.
-- Written by analog_index.py (nearest-neighbor retrieval).
--
-- Confirmed columns (via probing):
--   pos 1: id (BIGSERIAL PK)
--   pos 2: runner_id (NOT NULL)
--   pos 3: race_id (NOT NULL)
--   pos 4: analog_runner_id (NOT NULL)
--   pos 5: analog_race_id (NOT NULL)
--   pos 6: similarity_score (NUMERIC)
--   pos 7-17: TBC (nullable)
--   pos 18: created_at
--
-- Additional fields (per spec):
--   analog_sqpe, analog_sqpe_band, analog_sp_band,
--   analog_outcome (WIN/PLACED/MISS),
--   analog_win, analog_placed,
--   analog_finish_position,
--   rank (1=closest analog)
-- ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS race_fingerprint_analogs (
    id                      BIGSERIAL PRIMARY KEY,
    race_id                 TEXT        NOT NULL,
    runner_id               TEXT        NOT NULL,

    -- Analog reference
    analog_race_id           TEXT        NOT NULL,
    analog_runner_id        TEXT        NOT NULL,
    rank                    INTEGER     DEFAULT 1,

    -- Similarity
    similarity_score        NUMERIC(5,4) DEFAULT 0,

    -- Analog outcome facts
    analog_sqpe             NUMERIC(6,4),
    analog_sqpe_band        TEXT,
    analog_sp_band          TEXT,
    analog_outcome          TEXT,
    analog_win              BOOLEAN,
    analog_placed           BOOLEAN,
    analog_finish_position  INTEGER,
    analog_sp               NUMERIC(8,2),

    -- Lineage
    feature_version         TEXT        DEFAULT 'fingerprint_v1',
    signal_version          TEXT        DEFAULT 'phase35_locked',
    created_at              TIMESTAMPTZ DEFAULT NOW(),

    -- One analog match per (source, analog, rank) triple
    CONSTRAINT rfa_match_uniq UNIQUE (race_id, runner_id, analog_race_id, analog_runner_id, rank)
);

CREATE INDEX IF NOT EXISTS idx_rfa_race_runner  ON race_fingerprint_analogs (race_id, runner_id);
CREATE INDEX IF NOT EXISTS idx_rfa_analog_rr    ON race_fingerprint_analogs (analog_race_id, analog_runner_id);
CREATE INDEX IF NOT EXISTS idx_rfa_rank          ON race_fingerprint_analogs (rank);
CREATE INDEX IF NOT EXISTS idx_rfa_similarity    ON race_fingerprint_analogs (similarity_score DESC);
CREATE INDEX IF NOT EXISTS idx_rfa_created       ON race_fingerprint_analogs (created_at DESC);


-- ────────────────────────────────────────────────────────────
-- fingerprint_signal_summary
--
-- One row per runner. Aggregated analog statistics.
--
-- Confirmed columns (via probing):
--   pos 1: id (BIGSERIAL PK)
--   pos 2: runner_id (NOT NULL)
--   pos 3: race_id (NOT NULL)
--   pos 4-7: TBC (nullable)
--   pos 8: analog_count (INTEGER)
--   pos 9: analog_win_rate (NUMERIC)
--   pos 10: analog_place_rate (NUMERIC)
--   pos 11: analog_ae (NUMERIC)
--   pos 12: analog_roi (NUMERIC)
--   pos 13-16: TBC (nullable)
--   pos 17: created_at
--
-- Additional fields (per spec):
--   confidence (high/medium/low),
--   warnings (TEXT[]),
--   explanation (TEXT)
-- ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fingerprint_signal_summary (
    id                    BIGSERIAL PRIMARY KEY,
    race_id               TEXT        NOT NULL,
    runner_id             TEXT        NOT NULL,

    -- Aggregated analog stats
    analog_count          INTEGER     DEFAULT 0,
    analog_win_rate       NUMERIC(5,4) DEFAULT 0,
    analog_place_rate     NUMERIC(5,4) DEFAULT 0,
    analog_ae             NUMERIC(5,4) DEFAULT 0,
    analog_roi            NUMERIC(6,4) DEFAULT 0,

    -- Advisory output (Stage 2+)
    confidence            TEXT,       -- high | medium | low
    warnings               TEXT[],     -- e.g. ["low_analog_count", "regime_mismatch"]
    explanation           TEXT,       -- human-readable why this is/isn't a signal

    -- Stage gate
    shadow_only           BOOLEAN     DEFAULT TRUE,  -- must be TRUE until Stage 4

    -- Lineage
    feature_version       TEXT        DEFAULT 'fingerprint_v1',
    signal_version        TEXT        DEFAULT 'phase35_locked',
    created_at            TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT fss_race_runner_uniq UNIQUE (race_id, runner_id)
);

CREATE INDEX IF NOT EXISTS idx_fss_race_runner  ON fingerprint_signal_summary (race_id, runner_id);
CREATE INDEX IF NOT EXISTS idx_fss_confidence   ON fingerprint_signal_summary (confidence);
CREATE INDEX IF NOT EXISTS idx_fss_shadow       ON fingerprint_signal_summary (shadow_only) WHERE shadow_only = TRUE;
CREATE INDEX IF NOT EXISTS idx_fss_created      ON fingerprint_signal_summary (created_at DESC);


-- ============================================================
-- APPEND-ONLY ENFORCEMENT (optional, soft)
-- In Supabase SQL Editor, run:
--
-- CREATE OR REPLACE FUNCTION block_updates_on_fingerprint_tables()
-- RETURNS event_trigger AS $$
-- BEGIN
--   RAISE EXCEPTION 'Updates and deletes are disabled on fingerprint tables';
-- END;
-- $$ LANGUAGE plpgsql;
--
-- CREATE OR REPLACE event_trigger_fingerprint()
-- EVENT TRIGGER ON ddl_command_end
-- WHEN TAG IN ('DROP','TRUNCATE')
-- EXECUTE FUNCTION block_updates_on_fingerprint_tables();
-- ============================================================
