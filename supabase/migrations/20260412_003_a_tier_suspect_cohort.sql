-- migration: 20260412_003_a_tier_suspect_cohort
--
-- Adds a_tier_weak_place_flag to velo_verdicts.
--
-- Purpose: passive shadow monitor for the A-tier inflation suspect cohort.
--   Cohort: decision_tier = 'A' AND place_prob < 0.75
--   These are A calls where win-side signals are carrying the tier without
--   strong place confirmation. Win rate in this cohort is 28.6% vs 50.0%
--   for place_prob >= 0.90 (audit: 2026-04-12, 30-day window).
--
-- No gate logic is changed. This flag exists solely so the cohort can be
-- queried by date, race type, archetype, readiness_state, and market_state
-- over the next 30 days to build the sample needed for a conditional tighten.
--
-- Promotion path:
--   After 30+ verified outcomes in the flagged cohort, evaluate:
--     IF win_rate < 35% AND place_rate < 50%:
--       Tighten A gate for place_prob < 0.75 (e.g. raise gap or prob floor)
--     ELSE:
--       Remove flag or raise monitoring threshold

ALTER TABLE velo_verdicts
    ADD COLUMN IF NOT EXISTS a_tier_weak_place_flag BOOLEAN DEFAULT FALSE;

-- Backfill historical rows
UPDATE velo_verdicts
SET a_tier_weak_place_flag = (decision_tier = 'A' AND place_prob < 0.75)
WHERE a_tier_weak_place_flag IS NULL
   OR a_tier_weak_place_flag = FALSE AND decision_tier = 'A' AND place_prob < 0.75;

COMMENT ON COLUMN velo_verdicts.a_tier_weak_place_flag IS
    'TRUE when decision_tier=A and place_prob < 0.75. '
    'Shadow suspect cohort — A called on win signal alone without strong place confirmation. '
    'Monitor 30 days before any gate change. Added 2026-04-12.';
