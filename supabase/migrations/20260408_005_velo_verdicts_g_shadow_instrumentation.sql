-- Migration: add G Shadow instrumentation columns to velo_verdicts
-- Apply via: Supabase Dashboard > SQL Editor, or supabase db push
--
-- Purpose:
--   Track Playbook G shadow activity per race for evaluation purposes:
--   - Which horses G flagged (pain rules)
--   - Which doctrines fired
--   - What multiplier G applied to the top pick
--   - Top-3 ranking with G-adjusted scores for rank movement analysis
--
-- No live promotion: these columns are WRITE-ONLY observability.
-- They do not change velo_prime_prob or any scoring logic.
--
-- Required for: rank movement, favourite suppression, decoy reduction,
--               shortlist quality, frame-to-win conversion measurement.

ALTER TABLE velo_verdicts
  ADD COLUMN IF NOT EXISTS g_shadow_multiplier   FLOAT,   -- G multiplier applied (1.0 = no change)
  ADD COLUMN IF NOT EXISTS g_shadow_flags         TEXT[],  -- list of flags: pain_rule, doctrine_X, fav_liability
  ADD COLUMN IF NOT EXISTS g_shadow_horse_id      TEXT,    -- horse_id that triggered pain rule (if any)
  ADD COLUMN IF NOT EXISTS g_shadow_mode          TEXT,    -- 'shadow' or 'live'
  ADD COLUMN IF NOT EXISTS g_top3_scores          JSONB;  -- top-3 runners with velo_prime_prob and G-adjusted scores

-- Index: find races where G suppressed the favourite
CREATE INDEX IF NOT EXISTS idx_velo_verdicts_g_shadow_mult
  ON velo_verdicts (g_shadow_multiplier)
  WHERE g_shadow_multiplier IS NOT NULL;

-- Index: find races where G flagged a specific horse
CREATE INDEX IF NOT EXISTS idx_velo_verdicts_g_shadow_horse
  ON velo_verdicts (g_shadow_horse_id)
  WHERE g_shadow_horse_id IS NOT NULL;

-- Index: find races where a pain rule fired
CREATE INDEX IF NOT EXISTS idx_velo_verdicts_g_pain_rule
  ON velo_verdicts USING GIN (g_shadow_flags)
  WHERE array_length(g_shadow_flags, 1) > 0;
