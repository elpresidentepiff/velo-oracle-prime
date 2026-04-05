-- Migration: add Horse State Brain compact columns to velo_verdicts
-- Apply via: Supabase Dashboard > SQL Editor
-- Context: HorseStateEngine tags every runner after ensemble scoring.
--   The full raw state lives in full_analysis[*].horse_state (per runner).
--   These columns provide compact queryable state for the top selection
--   so horse condition can be audited without reading JSON.
--
-- All columns are nullable — scoring succeeds without this migration via
-- graceful fallback in persist_race_predictions().

ALTER TABLE velo_verdicts
  ADD COLUMN IF NOT EXISTS top_horse_readiness_state  TEXT,   -- cold / warming / primed
  ADD COLUMN IF NOT EXISTS top_horse_release_state    TEXT,   -- conditioning / hidden / release_candidate
  ADD COLUMN IF NOT EXISTS top_horse_rest_pattern     TEXT,   -- neutral / fresh / over_rested / rebound
  ADD COLUMN IF NOT EXISTS top_horse_class_move_state TEXT,   -- rise / neutral / drop / engineered_drop
  ADD COLUMN IF NOT EXISTS top_horse_stable_heat      TEXT,   -- cold / warm / hot
  ADD COLUMN IF NOT EXISTS top_horse_jockey_signal    TEXT,   -- neutral / positive / strong_positive / negative
  ADD COLUMN IF NOT EXISTS top_horse_market_state     TEXT,   -- ignored / drifting / quietly_backed / obvious
  ADD COLUMN IF NOT EXISTS top_horse_race_fit_state   TEXT,   -- weak / adequate / strong
  ADD COLUMN IF NOT EXISTS top_horse_chaos_exposure   TEXT,   -- low / medium / high
  ADD COLUMN IF NOT EXISTS top_horse_signal_count     INTEGER,  -- count of active (non-neutral) state tags
  ADD COLUMN IF NOT EXISTS top_horse_state_evidence   TEXT[];   -- tag:rule pairs that fired

-- Index for querying release candidates and primed horses
CREATE INDEX IF NOT EXISTS idx_velo_verdicts_release_state
  ON velo_verdicts (top_horse_release_state)
  WHERE top_horse_release_state IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_velo_verdicts_readiness_state
  ON velo_verdicts (top_horse_readiness_state)
  WHERE top_horse_readiness_state IS NOT NULL;
