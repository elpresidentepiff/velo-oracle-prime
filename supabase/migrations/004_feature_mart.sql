-- VÉLØ Phase 1: Feature Mart for Hot Window Intelligence
-- Database Migration: Feature Engineering Materialized Views
-- Date: 2026-01-08
-- 
-- This migration creates materialized views for trainer, jockey, and combo stats
-- to enable <1s feature extraction for the prediction engine.

-- ============================================================================
-- STEP 1: Add missing columns to support feature calculations
-- ============================================================================

-- Add position and odds columns to runners if they don't exist
-- These will be populated from form data or raw JSON
ALTER TABLE runners 
ADD COLUMN IF NOT EXISTS position INTEGER,
ADD COLUMN IF NOT EXISTS odds DECIMAL(10,2);

-- Add surface column to races if it doesn't exist
-- Will default to 'Turf' for UK flat racing
ALTER TABLE races
ADD COLUMN IF NOT EXISTS surface TEXT DEFAULT 'Turf';

-- Add index on race date for time-windowed queries
CREATE INDEX IF NOT EXISTS idx_races_import_date_batch_status 
ON races(import_date DESC);

-- ============================================================================
-- STEP 2: Create Trainer Performance Stats Views
-- ============================================================================

-- 14-day rolling window
CREATE MATERIALIZED VIEW IF NOT EXISTS trainer_stats_14d AS
SELECT 
  r.trainer,
  COUNT(*) as starts,
  SUM(CASE WHEN r.position = 1 THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN r.position <= 3 THEN 1 ELSE 0 END) as places,
  ROUND(AVG(CASE WHEN r.position = 1 THEN 1.0 ELSE 0.0 END), 4) as win_pct,
  ROUND(AVG(CASE WHEN r.position <= 3 THEN 1.0 ELSE 0.0 END), 4) as place_pct,
  ROUND(AVG(r.odds), 2) as avg_odds,
  MAX(ra.import_date) as last_run_date
FROM runners r
JOIN races ra ON r.race_id = ra.id
JOIN import_batches b ON ra.batch_id = b.id
WHERE ra.import_date >= NOW() - INTERVAL '14 days'
  AND b.status IN ('validated', 'ready')
  AND r.position IS NOT NULL
GROUP BY r.trainer;

-- 30-day window
CREATE MATERIALIZED VIEW IF NOT EXISTS trainer_stats_30d AS
SELECT 
  r.trainer,
  COUNT(*) as starts,
  SUM(CASE WHEN r.position = 1 THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN r.position <= 3 THEN 1 ELSE 0 END) as places,
  ROUND(AVG(CASE WHEN r.position = 1 THEN 1.0 ELSE 0.0 END), 4) as win_pct,
  ROUND(AVG(CASE WHEN r.position <= 3 THEN 1.0 ELSE 0.0 END), 4) as place_pct,
  ROUND(AVG(r.odds), 2) as avg_odds,
  MAX(ra.import_date) as last_run_date
FROM runners r
JOIN races ra ON r.race_id = ra.id
JOIN import_batches b ON ra.batch_id = b.id
WHERE ra.import_date >= NOW() - INTERVAL '30 days'
  AND b.status IN ('validated', 'ready')
  AND r.position IS NOT NULL
GROUP BY r.trainer;

-- 90-day window
CREATE MATERIALIZED VIEW IF NOT EXISTS trainer_stats_90d AS
SELECT 
  r.trainer,
  COUNT(*) as starts,
  SUM(CASE WHEN r.position = 1 THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN r.position <= 3 THEN 1 ELSE 0 END) as places,
  ROUND(AVG(CASE WHEN r.position = 1 THEN 1.0 ELSE 0.0 END), 4) as win_pct,
  ROUND(AVG(CASE WHEN r.position <= 3 THEN 1.0 ELSE 0.0 END), 4) as place_pct,
  ROUND(AVG(r.odds), 2) as avg_odds,
  MAX(ra.import_date) as last_run_date
FROM runners r
JOIN races ra ON r.race_id = ra.id
JOIN import_batches b ON ra.batch_id = b.id
WHERE ra.import_date >= NOW() - INTERVAL '90 days'
  AND b.status IN ('validated', 'ready')
  AND r.position IS NOT NULL
GROUP BY r.trainer;

-- ============================================================================
-- STEP 3: Create Jockey Performance Stats Views
-- ============================================================================

-- 14-day rolling window
CREATE MATERIALIZED VIEW IF NOT EXISTS jockey_stats_14d AS
SELECT 
  r.jockey,
  COUNT(*) as starts,
  SUM(CASE WHEN r.position = 1 THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN r.position <= 3 THEN 1 ELSE 0 END) as places,
  ROUND(AVG(CASE WHEN r.position = 1 THEN 1.0 ELSE 0.0 END), 4) as win_pct,
  ROUND(AVG(CASE WHEN r.position <= 3 THEN 1.0 ELSE 0.0 END), 4) as place_pct,
  ROUND(AVG(r.odds), 2) as avg_odds,
  MAX(ra.import_date) as last_run_date
FROM runners r
JOIN races ra ON r.race_id = ra.id
JOIN import_batches b ON ra.batch_id = b.id
WHERE ra.import_date >= NOW() - INTERVAL '14 days'
  AND b.status IN ('validated', 'ready')
  AND r.position IS NOT NULL
GROUP BY r.jockey;

-- 30-day window
CREATE MATERIALIZED VIEW IF NOT EXISTS jockey_stats_30d AS
SELECT 
  r.jockey,
  COUNT(*) as starts,
  SUM(CASE WHEN r.position = 1 THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN r.position <= 3 THEN 1 ELSE 0 END) as places,
  ROUND(AVG(CASE WHEN r.position = 1 THEN 1.0 ELSE 0.0 END), 4) as win_pct,
  ROUND(AVG(CASE WHEN r.position <= 3 THEN 1.0 ELSE 0.0 END), 4) as place_pct,
  ROUND(AVG(r.odds), 2) as avg_odds,
  MAX(ra.import_date) as last_run_date
FROM runners r
JOIN races ra ON r.race_id = ra.id
JOIN import_batches b ON ra.batch_id = b.id
WHERE ra.import_date >= NOW() - INTERVAL '30 days'
  AND b.status IN ('validated', 'ready')
  AND r.position IS NOT NULL
GROUP BY r.jockey;

-- 90-day window
CREATE MATERIALIZED VIEW IF NOT EXISTS jockey_stats_90d AS
SELECT 
  r.jockey,
  COUNT(*) as starts,
  SUM(CASE WHEN r.position = 1 THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN r.position <= 3 THEN 1 ELSE 0 END) as places,
  ROUND(AVG(CASE WHEN r.position = 1 THEN 1.0 ELSE 0.0 END), 4) as win_pct,
  ROUND(AVG(CASE WHEN r.position <= 3 THEN 1.0 ELSE 0.0 END), 4) as place_pct,
  ROUND(AVG(r.odds), 2) as avg_odds,
  MAX(ra.import_date) as last_run_date
FROM runners r
JOIN races ra ON r.race_id = ra.id
JOIN import_batches b ON ra.batch_id = b.id
WHERE ra.import_date >= NOW() - INTERVAL '90 days'
  AND b.status IN ('validated', 'ready')
  AND r.position IS NOT NULL
GROUP BY r.jockey;

-- ============================================================================
-- STEP 4: Create Jockey-Trainer Combo Stats
-- ============================================================================

-- 365-day combo performance
CREATE MATERIALIZED VIEW IF NOT EXISTS jt_combo_stats_365d AS
SELECT 
  r.jockey,
  r.trainer,
  COUNT(*) as starts,
  SUM(CASE WHEN r.position = 1 THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN r.position <= 3 THEN 1 ELSE 0 END) as places,
  ROUND(AVG(CASE WHEN r.position = 1 THEN 1.0 ELSE 0.0 END), 4) as win_pct,
  ROUND(AVG(CASE WHEN r.position <= 3 THEN 1.0 ELSE 0.0 END), 4) as place_pct,
  ROUND(AVG(r.odds), 2) as avg_odds
FROM runners r
JOIN races ra ON r.race_id = ra.id
JOIN import_batches b ON ra.batch_id = b.id
WHERE ra.import_date >= NOW() - INTERVAL '365 days'
  AND b.status IN ('validated', 'ready')
  AND r.position IS NOT NULL
GROUP BY r.jockey, r.trainer
HAVING COUNT(*) >= 3;  -- Minimum sample size

-- ============================================================================
-- STEP 5: Create Course/Distance Performance Stats
-- ============================================================================

-- Course bias by distance band (36 months)
CREATE MATERIALIZED VIEW IF NOT EXISTS course_distance_stats_36m AS
SELECT
  ra.course,
  CASE
    WHEN ra.distance IS NULL OR REGEXP_REPLACE(ra.distance, '[^0-9]', '', 'g') = ''
      THEN 'unknown'
    WHEN CAST(REGEXP_REPLACE(ra.distance, '[^0-9]', '', 'g') AS INTEGER) < 1200 THEN 'sprint'
    WHEN CAST(REGEXP_REPLACE(ra.distance, '[^0-9]', '', 'g') AS INTEGER) < 1600 THEN 'mile'
    WHEN CAST(REGEXP_REPLACE(ra.distance, '[^0-9]', '', 'g') AS INTEGER) < 2000 THEN 'middle'
    ELSE 'staying'
  END as distance_band,
  ra.surface,
  COUNT(*) as races,
  AVG(r.odds) as avg_winning_odds,
  STDDEV(r.odds) as odds_volatility
FROM races ra
JOIN runners r ON ra.id = r.race_id
JOIN import_batches b ON ra.batch_id = b.id
WHERE ra.import_date >= NOW() - INTERVAL '36 months'
  AND b.status IN ('validated', 'ready')
  AND r.position = 1
  AND ra.distance IS NOT NULL
  AND REGEXP_REPLACE(ra.distance, '[^0-9]', '', 'g') != ''
GROUP BY ra.course, distance_band, ra.surface;

-- ============================================================================
-- STEP 6: Create Indexes for Performance
-- ============================================================================

-- Trainer lookups
CREATE INDEX IF NOT EXISTS idx_trainer_stats_14d_trainer ON trainer_stats_14d(trainer);
CREATE INDEX IF NOT EXISTS idx_trainer_stats_30d_trainer ON trainer_stats_30d(trainer);
CREATE INDEX IF NOT EXISTS idx_trainer_stats_90d_trainer ON trainer_stats_90d(trainer);

-- Jockey lookups
CREATE INDEX IF NOT EXISTS idx_jockey_stats_14d_jockey ON jockey_stats_14d(jockey);
CREATE INDEX IF NOT EXISTS idx_jockey_stats_30d_jockey ON jockey_stats_30d(jockey);
CREATE INDEX IF NOT EXISTS idx_jockey_stats_90d_jockey ON jockey_stats_90d(jockey);

-- Combo lookups
CREATE INDEX IF NOT EXISTS idx_jt_combo_jockey_trainer ON jt_combo_stats_365d(jockey, trainer);

-- Course lookups
CREATE INDEX IF NOT EXISTS idx_course_distance_course ON course_distance_stats_36m(course, distance_band);

-- ============================================================================
-- STEP 7: Add Comments for Documentation
-- ============================================================================

COMMENT ON MATERIALIZED VIEW trainer_stats_14d IS 
'Trainer performance statistics over 14-day rolling window. Refreshed daily.';

COMMENT ON MATERIALIZED VIEW trainer_stats_30d IS 
'Trainer performance statistics over 30-day rolling window. Refreshed daily.';

COMMENT ON MATERIALIZED VIEW trainer_stats_90d IS 
'Trainer performance statistics over 90-day rolling window. Refreshed daily.';

COMMENT ON MATERIALIZED VIEW jockey_stats_14d IS 
'Jockey performance statistics over 14-day rolling window. Refreshed daily.';

COMMENT ON MATERIALIZED VIEW jockey_stats_30d IS 
'Jockey performance statistics over 30-day rolling window. Refreshed daily.';

COMMENT ON MATERIALIZED VIEW jockey_stats_90d IS 
'Jockey performance statistics over 90-day rolling window. Refreshed daily.';

COMMENT ON MATERIALIZED VIEW jt_combo_stats_365d IS 
'Jockey-Trainer combo performance over 365-day window. Minimum 3 starts. Refreshed daily.';

COMMENT ON MATERIALIZED VIEW course_distance_stats_36m IS 
'Course distance band statistics over 36 months. Winner odds and volatility. Refreshed daily.';

-- ============================================================================
-- ROLLBACK INSTRUCTIONS
-- ============================================================================
-- To rollback this migration:
-- DROP MATERIALIZED VIEW IF EXISTS trainer_stats_14d CASCADE;
-- DROP MATERIALIZED VIEW IF EXISTS trainer_stats_30d CASCADE;
-- DROP MATERIALIZED VIEW IF EXISTS trainer_stats_90d CASCADE;
-- DROP MATERIALIZED VIEW IF EXISTS jockey_stats_14d CASCADE;
-- DROP MATERIALIZED VIEW IF EXISTS jockey_stats_30d CASCADE;
-- DROP MATERIALIZED VIEW IF EXISTS jockey_stats_90d CASCADE;
-- DROP MATERIALIZED VIEW IF EXISTS jt_combo_stats_365d CASCADE;
-- DROP MATERIALIZED VIEW IF EXISTS course_distance_stats_36m CASCADE;
-- ALTER TABLE runners DROP COLUMN IF EXISTS position;
-- ALTER TABLE runners DROP COLUMN IF EXISTS odds;
-- ALTER TABLE races DROP COLUMN IF EXISTS surface;
