-- ============================================================
-- VÉLØ Phase 2.2 — Relational Tightening Migration
-- Date: 2026-03-15
-- ============================================================
-- Changes:
-- 1. Add off_dt (timestamptz) to runner_race_facts
-- 2. Add FK from runner_results.horse_id → horse_profiles(id)
-- 3. Add source linkage columns to intent_cases
--    (source_verdict_id, source_flag_id)
-- 4. Add uniqueness constraint to market_snapshots
-- 5. Change velo_verdicts UNIQUE (race_id) → UNIQUE (race_id, generated_at)
--    to allow verdict evolution as market data updates
-- 6. Add runner_derived_features extra doctrine fields
-- 7. Add endpoint_family to api_coverage_audit
-- ============================================================

BEGIN;

-- ── 1. runner_race_facts: add off_dt ─────────────────────────────────────────
ALTER TABLE runner_race_facts
    ADD COLUMN IF NOT EXISTS off_dt TIMESTAMPTZ;

-- Back-fill off_dt from existing race_date + race_time where possible
UPDATE runner_race_facts
SET off_dt = (race_date::text || 'T' || race_time || ':00+00:00')::timestamptz
WHERE off_dt IS NULL
  AND race_date IS NOT NULL
  AND race_time IS NOT NULL
  AND race_time::text ~ '^\d{2}:\d{2}$';

CREATE INDEX IF NOT EXISTS idx_rrf_off_dt ON runner_race_facts(off_dt);

-- ── 2. runner_results: FK to horse_profiles ──────────────────────────────────
-- First ensure horse_id column exists (it does, but guard idempotently)
ALTER TABLE runner_results
    ADD COLUMN IF NOT EXISTS horse_id TEXT;

-- Add FK constraint if not already present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_runner_results_horse_profiles'
          AND table_name = 'runner_results'
    ) THEN
        ALTER TABLE runner_results
            ADD CONSTRAINT fk_runner_results_horse_profiles
            FOREIGN KEY (horse_id)
            REFERENCES horse_profiles(id)
            ON DELETE SET NULL
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

-- ── 3. intent_cases: source linkage columns ──────────────────────────────────
ALTER TABLE intent_cases
    ADD COLUMN IF NOT EXISTS source_verdict_id UUID REFERENCES velo_verdicts(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS source_flag_id    UUID REFERENCES velo_anomaly_flags(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_intent_cases_verdict ON intent_cases(source_verdict_id);
CREATE INDEX IF NOT EXISTS idx_intent_cases_flag    ON intent_cases(source_flag_id);

-- ── 4. market_snapshots: uniqueness constraint ────────────────────────────────
-- Dedupe strategy: unique per race+horse+source+label+hour bucket
ALTER TABLE market_snapshots
    ADD COLUMN IF NOT EXISTS snapshot_label   TEXT DEFAULT 'live',
    ADD COLUMN IF NOT EXISTS source           TEXT DEFAULT 'racing_api';

-- Create a unique index on the dedupe key
-- Use a generated column approach: store hour bucket explicitly
ALTER TABLE market_snapshots
    ADD COLUMN IF NOT EXISTS captured_at_hour TIMESTAMPTZ
        GENERATED ALWAYS AS (date_trunc('hour', captured_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC') STORED;

CREATE UNIQUE INDEX IF NOT EXISTS uq_market_snapshots_dedupe
    ON market_snapshots (
        race_id,
        horse_id,
        source,
        snapshot_label,
        captured_at_hour
    );

-- ── 5. velo_verdicts: allow verdict evolution ─────────────────────────────────
-- Drop the existing UNIQUE (race_id) constraint and replace with
-- UNIQUE (race_id, generated_at) to allow multiple verdicts per race
-- as market data updates throughout the day.
DO $$
DECLARE
    v_constraint TEXT;
BEGIN
    SELECT constraint_name INTO v_constraint
    FROM information_schema.table_constraints
    WHERE table_name = 'velo_verdicts'
      AND constraint_type = 'UNIQUE'
      AND constraint_name LIKE '%race_id%';

    IF v_constraint IS NOT NULL THEN
        EXECUTE 'ALTER TABLE velo_verdicts DROP CONSTRAINT ' || quote_ident(v_constraint);
    END IF;
END $$;

-- Also drop any unique index on race_id alone
DROP INDEX IF EXISTS velo_verdicts_race_id_key;
DROP INDEX IF EXISTS uq_velo_verdicts_race;

-- Add the correct composite unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS uq_velo_verdicts_race_time
    ON velo_verdicts (race_id, generated_at);

-- ── 6. runner_derived_features: add doctrine fields ──────────────────────────
ALTER TABLE runner_derived_features
    ADD COLUMN IF NOT EXISTS form_cycle_score        NUMERIC,
    ADD COLUMN IF NOT EXISTS recency_score           NUMERIC,
    ADD COLUMN IF NOT EXISTS trainer_hotness_score   NUMERIC,
    ADD COLUMN IF NOT EXISTS jockey_course_score     NUMERIC,
    ADD COLUMN IF NOT EXISTS market_drift_score      NUMERIC,
    ADD COLUMN IF NOT EXISTS late_support_score      NUMERIC;

-- ── 7. api_coverage_audit: add endpoint_family ───────────────────────────────
ALTER TABLE api_coverage_audit
    ADD COLUMN IF NOT EXISTS endpoint_family TEXT
        CHECK (endpoint_family IN ('racecards_standard', 'results', 'odds', 'future_entries', 'horse_detail', 'other'));

COMMIT;

-- ── Verification query ────────────────────────────────────────────────────────
-- Run this after migration to confirm all changes applied:
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name IN ('runner_race_facts','runner_results','intent_cases','market_snapshots','velo_verdicts','runner_derived_features','api_coverage_audit')
-- ORDER BY table_name, ordinal_position;
