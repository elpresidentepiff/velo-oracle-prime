-- ============================================================
-- VÉLØ Fix: Runner deduplication + unique constraint
-- Date: 2026-03-15
-- Applied via: Supabase MCP (already live in DB)
-- ============================================================
-- Problem: runners table had no unique constraint on (race_id, horse_id).
-- Pipeline ran ~10 times, inserting duplicates each time.
-- Result: 2,756 rows for 265 real runners (10.4x inflation).
--
-- Fix:
-- 1. Delete duplicates, keep earliest inserted per (race_id, horse_id)
-- 2. Add UNIQUE constraint to prevent future duplication
-- ============================================================

-- Step 1: Remove duplicates
DELETE FROM runners
WHERE id NOT IN (
  SELECT DISTINCT ON (race_id, horse_id) id
  FROM runners
  ORDER BY race_id, horse_id, created_at ASC
);

-- Step 2: Prevent future duplication
ALTER TABLE runners
  ADD CONSTRAINT runners_race_horse_unique UNIQUE (race_id, horse_id);
