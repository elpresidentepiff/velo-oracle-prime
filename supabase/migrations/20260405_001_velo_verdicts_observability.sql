-- Migration: add ensemble observability columns to velo_verdicts
-- Apply via: Supabase Dashboard > SQL Editor, or supabase db push
-- Context: active_components + excluded_from_ensemble are computed by
--   VeloPrimeEnsemble.predict() and stored for every race so the live
--   state of the ensemble is queryable without reading source code.
--
-- "stored ≠ live" enforcement:
--   improvement_score, release_window_score, comment_intel_score are
--   stored as raw float columns for observability but will appear in
--   excluded_from_ensemble on every row, confirming they are NOT used.

ALTER TABLE velo_verdicts
  ADD COLUMN IF NOT EXISTS active_components   TEXT[],   -- components that entered the weighted average
  ADD COLUMN IF NOT EXISTS excluded_from_ensemble TEXT[]; -- components present but excluded (_DISABLED or zero-variance)

-- Index for auditing: find any race where improvement_score slipped back in
CREATE INDEX IF NOT EXISTS idx_velo_verdicts_excluded
  ON velo_verdicts USING GIN (excluded_from_ensemble);
