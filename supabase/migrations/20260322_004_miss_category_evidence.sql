-- 20260322_004_miss_category_evidence.sql
-- Adds structured miss taxonomy to velo_post_race_reviews.
-- Enables fusion audit, custom-loss seed data, and G learning spine.

ALTER TABLE velo_post_race_reviews
  ADD COLUMN IF NOT EXISTS miss_category TEXT,
  ADD COLUMN IF NOT EXISTS miss_evidence JSONB,
  ADD COLUMN IF NOT EXISTS learning_ready BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN velo_post_race_reviews.miss_category IS
  'Structured miss family: market_decoy_followed | outsider_hedge_omitted | fusion_suppression | genuine_blind_spot | data_gap | other';

COMMENT ON COLUMN velo_post_race_reviews.miss_evidence IS
  'Structured evidence blob: winner SP, top pick SP, specialist scores, deception signals, fusion flags. Seed data for custom-loss training.';

COMMENT ON COLUMN velo_post_race_reviews.learning_ready IS
  'TRUE only when: result integrity confirmed, miss_category assigned, miss_evidence populated, no unresolved data gap.';
