-- VÉLØ Deterministic Feature Mart Migration
-- Migration: 005_deterministic_feature_mart
-- Created: 2026-01-09
-- Purpose: Replace NOW()-based materialized views with deterministic as_of_date tables
--
-- This migration implements deterministic feature computation to ensure:
-- - Same as_of_date → same features (reproducible)
-- - Different as_of_date → different features (expected)
-- - No time-dependent queries in WHERE clauses
-- - Backtesting, regression testing, and audit trails are reliable

-- ============================================================================
-- DROP OLD MATERIALIZED VIEWS (if they exist)
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS trainer_stats_14d CASCADE;
DROP MATERIALIZED VIEW IF EXISTS trainer_stats_30d CASCADE;
DROP MATERIALIZED VIEW IF EXISTS trainer_stats_90d CASCADE;
DROP MATERIALIZED VIEW IF EXISTS jockey_stats_14d CASCADE;
DROP MATERIALIZED VIEW IF EXISTS jockey_stats_30d CASCADE;
DROP MATERIALIZED VIEW IF EXISTS jockey_stats_90d CASCADE;
DROP MATERIALIZED VIEW IF EXISTS jt_combo_stats_365d CASCADE;
DROP MATERIALIZED VIEW IF EXISTS course_distance_stats_36m CASCADE;

-- ============================================================================
-- CREATE DETERMINISTIC FEATURE TABLES
-- ============================================================================

-- Trainer stats table (deterministic)
CREATE TABLE IF NOT EXISTS trainer_stats_window (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  as_of_date DATE NOT NULL,
  window_days INTEGER NOT NULL,
  trainer TEXT NOT NULL,
  starts INTEGER NOT NULL DEFAULT 0,
  wins INTEGER NOT NULL DEFAULT 0,
  places INTEGER NOT NULL DEFAULT 0,
  win_pct NUMERIC(6,4),
  place_pct NUMERIC(6,4),
  avg_odds NUMERIC(10,2),
  last_run_date DATE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(as_of_date, window_days, trainer)
);

COMMENT ON TABLE trainer_stats_window IS 'Deterministic trainer statistics keyed by as_of_date for reproducible feature computation';
COMMENT ON COLUMN trainer_stats_window.as_of_date IS 'Reference date for feature computation (typically batch import_date)';
COMMENT ON COLUMN trainer_stats_window.window_days IS 'Lookback window in days (e.g., 14, 30, 90)';

-- Jockey stats table (deterministic)
CREATE TABLE IF NOT EXISTS jockey_stats_window (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  as_of_date DATE NOT NULL,
  window_days INTEGER NOT NULL,
  jockey TEXT NOT NULL,
  starts INTEGER NOT NULL DEFAULT 0,
  wins INTEGER NOT NULL DEFAULT 0,
  places INTEGER NOT NULL DEFAULT 0,
  win_pct NUMERIC(6,4),
  place_pct NUMERIC(6,4),
  avg_odds NUMERIC(10,2),
  last_run_date DATE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(as_of_date, window_days, jockey)
);

COMMENT ON TABLE jockey_stats_window IS 'Deterministic jockey statistics keyed by as_of_date for reproducible feature computation';

-- JT combo stats table (deterministic)
CREATE TABLE IF NOT EXISTS jt_combo_stats_window (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  as_of_date DATE NOT NULL,
  window_days INTEGER NOT NULL,
  jockey TEXT NOT NULL,
  trainer TEXT NOT NULL,
  starts INTEGER NOT NULL DEFAULT 0,
  wins INTEGER NOT NULL DEFAULT 0,
  places INTEGER NOT NULL DEFAULT 0,
  win_pct NUMERIC(6,4),
  place_pct NUMERIC(6,4),
  avg_odds NUMERIC(10,2),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(as_of_date, window_days, jockey, trainer)
);

COMMENT ON TABLE jt_combo_stats_window IS 'Deterministic jockey-trainer combination statistics keyed by as_of_date';

-- Course/distance stats table (deterministic)
CREATE TABLE IF NOT EXISTS course_distance_stats_window (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  as_of_date DATE NOT NULL,
  window_days INTEGER NOT NULL,
  course TEXT NOT NULL,
  distance_band TEXT NOT NULL,
  surface TEXT,
  races INTEGER NOT NULL DEFAULT 0,
  avg_winning_odds NUMERIC(10,2),
  odds_volatility NUMERIC(10,2),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(as_of_date, window_days, course, distance_band, surface)
);

COMMENT ON TABLE course_distance_stats_window IS 'Deterministic course/distance statistics keyed by as_of_date';

-- ============================================================================
-- CREATE INDEXES FOR PERFORMANCE
-- ============================================================================

-- Trainer lookups
CREATE INDEX IF NOT EXISTS idx_trainer_stats_window_lookup ON trainer_stats_window(as_of_date, window_days, trainer);
CREATE INDEX IF NOT EXISTS idx_trainer_stats_window_trainer ON trainer_stats_window(trainer);
CREATE INDEX IF NOT EXISTS idx_trainer_stats_window_date ON trainer_stats_window(as_of_date DESC);

-- Jockey lookups
CREATE INDEX IF NOT EXISTS idx_jockey_stats_window_lookup ON jockey_stats_window(as_of_date, window_days, jockey);
CREATE INDEX IF NOT EXISTS idx_jockey_stats_window_jockey ON jockey_stats_window(jockey);
CREATE INDEX IF NOT EXISTS idx_jockey_stats_window_date ON jockey_stats_window(as_of_date DESC);

-- Combo lookups
CREATE INDEX IF NOT EXISTS idx_jt_combo_stats_window_lookup ON jt_combo_stats_window(as_of_date, window_days, jockey, trainer);
CREATE INDEX IF NOT EXISTS idx_jt_combo_stats_window_date ON jt_combo_stats_window(as_of_date DESC);

-- Course lookups
CREATE INDEX IF NOT EXISTS idx_course_distance_stats_window_lookup ON course_distance_stats_window(as_of_date, window_days, course, distance_band);
CREATE INDEX IF NOT EXISTS idx_course_distance_stats_window_date ON course_distance_stats_window(as_of_date DESC);

-- ============================================================================
-- CREATE BUILDER FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION build_feature_mart(p_as_of_date DATE)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_window_days INTEGER;
  v_start_date DATE;
BEGIN
  RAISE NOTICE 'Building feature mart for as_of_date: %', p_as_of_date;
  
  -- ========================================================================
  -- TRAINER STATS (14d, 30d, 90d windows)
  -- ========================================================================
  
  FOREACH v_window_days IN ARRAY ARRAY[14, 30, 90]
  LOOP
    v_start_date := p_as_of_date - (v_window_days || ' days')::INTERVAL;
    
    INSERT INTO trainer_stats_window (
      as_of_date, window_days, trainer, starts, wins, places, 
      win_pct, place_pct, avg_odds, last_run_date
    )
    SELECT
      p_as_of_date,
      v_window_days,
      COALESCE(r.trainer, 'Unknown') as trainer,
      COUNT(*) as starts,
      SUM(CASE WHEN fl.position = '1' THEN 1 ELSE 0 END) as wins,
      SUM(CASE WHEN fl.position IN ('1', '2', '3') THEN 1 ELSE 0 END) as places,
      ROUND(AVG(CASE WHEN fl.position = '1' THEN 1.0 ELSE 0.0 END), 4) as win_pct,
      ROUND(AVG(CASE WHEN fl.position IN ('1', '2', '3') THEN 1.0 ELSE 0.0 END), 4) as place_pct,
      ROUND(AVG(COALESCE((r.raw->>'odds')::NUMERIC, 0)), 2) as avg_odds,
      MAX(ra.import_date) as last_run_date
    FROM runners r
    JOIN races ra ON r.race_id = ra.id
    JOIN import_batches b ON ra.batch_id = b.id
    LEFT JOIN runner_form_lines fl ON fl.runner_id = r.id AND fl.run_date = ra.import_date
    WHERE ra.import_date >= v_start_date
      AND ra.import_date < p_as_of_date
      AND b.status IN ('validated', 'ready')
      AND r.trainer IS NOT NULL
    GROUP BY r.trainer
    HAVING COUNT(*) > 0
    ON CONFLICT (as_of_date, window_days, trainer) DO UPDATE SET
      starts = EXCLUDED.starts,
      wins = EXCLUDED.wins,
      places = EXCLUDED.places,
      win_pct = EXCLUDED.win_pct,
      place_pct = EXCLUDED.place_pct,
      avg_odds = EXCLUDED.avg_odds,
      last_run_date = EXCLUDED.last_run_date;
      
    RAISE NOTICE '  ✓ Trainer stats computed for % day window', v_window_days;
  END LOOP;
  
  -- ========================================================================
  -- JOCKEY STATS (14d, 30d, 90d windows)
  -- ========================================================================
  
  FOREACH v_window_days IN ARRAY ARRAY[14, 30, 90]
  LOOP
    v_start_date := p_as_of_date - (v_window_days || ' days')::INTERVAL;
    
    INSERT INTO jockey_stats_window (
      as_of_date, window_days, jockey, starts, wins, places, 
      win_pct, place_pct, avg_odds, last_run_date
    )
    SELECT
      p_as_of_date,
      v_window_days,
      COALESCE(r.jockey, 'Unknown') as jockey,
      COUNT(*) as starts,
      SUM(CASE WHEN fl.position = '1' THEN 1 ELSE 0 END) as wins,
      SUM(CASE WHEN fl.position IN ('1', '2', '3') THEN 1 ELSE 0 END) as places,
      ROUND(AVG(CASE WHEN fl.position = '1' THEN 1.0 ELSE 0.0 END), 4) as win_pct,
      ROUND(AVG(CASE WHEN fl.position IN ('1', '2', '3') THEN 1.0 ELSE 0.0 END), 4) as place_pct,
      ROUND(AVG(COALESCE((r.raw->>'odds')::NUMERIC, 0)), 2) as avg_odds,
      MAX(ra.import_date) as last_run_date
    FROM runners r
    JOIN races ra ON r.race_id = ra.id
    JOIN import_batches b ON ra.batch_id = b.id
    LEFT JOIN runner_form_lines fl ON fl.runner_id = r.id AND fl.run_date = ra.import_date
    WHERE ra.import_date >= v_start_date
      AND ra.import_date < p_as_of_date
      AND b.status IN ('validated', 'ready')
      AND r.jockey IS NOT NULL
    GROUP BY r.jockey
    HAVING COUNT(*) > 0
    ON CONFLICT (as_of_date, window_days, jockey) DO UPDATE SET
      starts = EXCLUDED.starts,
      wins = EXCLUDED.wins,
      places = EXCLUDED.places,
      win_pct = EXCLUDED.win_pct,
      place_pct = EXCLUDED.place_pct,
      avg_odds = EXCLUDED.avg_odds,
      last_run_date = EXCLUDED.last_run_date;
      
    RAISE NOTICE '  ✓ Jockey stats computed for % day window', v_window_days;
  END LOOP;
  
  -- ========================================================================
  -- JT COMBO STATS (365d window)
  -- ========================================================================
  
  v_window_days := 365;
  v_start_date := p_as_of_date - (v_window_days || ' days')::INTERVAL;
  
  INSERT INTO jt_combo_stats_window (
    as_of_date, window_days, jockey, trainer, starts, wins, places, 
    win_pct, place_pct, avg_odds
  )
  SELECT
    p_as_of_date,
    v_window_days,
    COALESCE(r.jockey, 'Unknown') as jockey,
    COALESCE(r.trainer, 'Unknown') as trainer,
    COUNT(*) as starts,
    SUM(CASE WHEN fl.position = '1' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN fl.position IN ('1', '2', '3') THEN 1 ELSE 0 END) as places,
    ROUND(AVG(CASE WHEN fl.position = '1' THEN 1.0 ELSE 0.0 END), 4) as win_pct,
    ROUND(AVG(CASE WHEN fl.position IN ('1', '2', '3') THEN 1.0 ELSE 0.0 END), 4) as place_pct,
    ROUND(AVG(COALESCE((r.raw->>'odds')::NUMERIC, 0)), 2) as avg_odds
  FROM runners r
  JOIN races ra ON r.race_id = ra.id
  JOIN import_batches b ON ra.batch_id = b.id
  LEFT JOIN runner_form_lines fl ON fl.runner_id = r.id AND fl.run_date = ra.import_date
  WHERE ra.import_date >= v_start_date
    AND ra.import_date < p_as_of_date
    AND b.status IN ('validated', 'ready')
    AND r.jockey IS NOT NULL
    AND r.trainer IS NOT NULL
  GROUP BY r.jockey, r.trainer
  HAVING COUNT(*) >= 3  -- Minimum 3 starts for combo stats
  ON CONFLICT (as_of_date, window_days, jockey, trainer) DO UPDATE SET
    starts = EXCLUDED.starts,
    wins = EXCLUDED.wins,
    places = EXCLUDED.places,
    win_pct = EXCLUDED.win_pct,
    place_pct = EXCLUDED.place_pct,
    avg_odds = EXCLUDED.avg_odds;
    
  RAISE NOTICE '  ✓ JT combo stats computed for % day window', v_window_days;
  
  -- ========================================================================
  -- COURSE/DISTANCE STATS (1095d = ~3 years window)
  -- ========================================================================
  
  v_window_days := 1095;
  v_start_date := p_as_of_date - (v_window_days || ' days')::INTERVAL;
  
  -- Helper function to bucket distances
  INSERT INTO course_distance_stats_window (
    as_of_date, window_days, course, distance_band, surface, 
    races, avg_winning_odds, odds_volatility
  )
  SELECT
    p_as_of_date,
    v_window_days,
    ra.course,
    CASE
      WHEN ra.distance ~ '^\d+$' THEN
        CASE 
          WHEN ra.distance::INTEGER < 1200 THEN '< 1200m'
          WHEN ra.distance::INTEGER < 1600 THEN '1200-1600m'
          WHEN ra.distance::INTEGER < 2000 THEN '1600-2000m'
          WHEN ra.distance::INTEGER < 2400 THEN '2000-2400m'
          ELSE '2400m+'
        END
      WHEN ra.distance ~ '^\d+m' THEN
        CASE 
          WHEN SUBSTRING(ra.distance FROM '^\d+')::INTEGER < 1200 THEN '< 1200m'
          WHEN SUBSTRING(ra.distance FROM '^\d+')::INTEGER < 1600 THEN '1200-1600m'
          WHEN SUBSTRING(ra.distance FROM '^\d+')::INTEGER < 2000 THEN '1600-2000m'
          WHEN SUBSTRING(ra.distance FROM '^\d+')::INTEGER < 2400 THEN '2000-2400m'
          ELSE '2400m+'
        END
      ELSE 'Unknown'
    END as distance_band,
    COALESCE(ra.race_type, 'Flat') as surface,
    COUNT(DISTINCT ra.id) as races,
    ROUND(AVG(CASE WHEN fl.position = '1' THEN COALESCE((r.raw->>'odds')::NUMERIC, 0) ELSE NULL END), 2) as avg_winning_odds,
    ROUND(STDDEV(CASE WHEN fl.position = '1' THEN COALESCE((r.raw->>'odds')::NUMERIC, 0) ELSE NULL END), 2) as odds_volatility
  FROM races ra
  JOIN runners r ON r.race_id = ra.id
  JOIN import_batches b ON ra.batch_id = b.id
  LEFT JOIN runner_form_lines fl ON fl.runner_id = r.id AND fl.run_date = ra.import_date
  WHERE ra.import_date >= v_start_date
    AND ra.import_date < p_as_of_date
    AND b.status IN ('validated', 'ready')
    AND ra.course IS NOT NULL
  GROUP BY ra.course, distance_band, ra.race_type
  HAVING COUNT(DISTINCT ra.id) >= 5  -- Minimum 5 races for stats
  ON CONFLICT (as_of_date, window_days, course, distance_band, surface) DO UPDATE SET
    races = EXCLUDED.races,
    avg_winning_odds = EXCLUDED.avg_winning_odds,
    odds_volatility = EXCLUDED.odds_volatility;
    
  RAISE NOTICE '  ✓ Course/distance stats computed for % day window', v_window_days;
  
  RAISE NOTICE '✅ Feature mart build complete for as_of_date: %', p_as_of_date;
END;
$$;

COMMENT ON FUNCTION build_feature_mart IS 'Build deterministic feature mart for a specific as_of_date. Computes trainer, jockey, JT combo, and course/distance stats using historical data from as_of_date minus window days up to but not including as_of_date.';

-- ============================================================================
-- VERIFY SCHEMA
-- ============================================================================

-- Verify tables exist
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_name IN ('trainer_stats_window', 'jockey_stats_window', 
                          'jt_combo_stats_window', 'course_distance_stats_window')
  ) THEN
    RAISE NOTICE '✅ All feature mart tables created successfully';
  ELSE
    RAISE EXCEPTION 'Feature mart table creation failed';
  END IF;
END $$;
