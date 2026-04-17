-- migration: 20260413_003_trainer_profile_extended
-- Extends trainer_campaign_profile with stats derivable from racing_horse_runs
-- that were previously NULL placeholders:
--   - win_rate_mark_ready, win_rate_class_drop: now computed
--   - win_rate_days_8_21/22_45/46_plus: corrected computation
--   - NEW: win_rate_first_time_headgear, win_rate_going_good_firm,
--           win_rate_going_soft_plus, win_rate_going_aw, top_courses
-- Added 2026-04-13.

ALTER TABLE trainer_campaign_profile
    ADD COLUMN IF NOT EXISTS win_rate_first_time_headgear  NUMERIC(5,1),
    ADD COLUMN IF NOT EXISTS win_rate_going_good_firm       NUMERIC(5,1),
    ADD COLUMN IF NOT EXISTS win_rate_going_soft_plus       NUMERIC(5,1),
    ADD COLUMN IF NOT EXISTS win_rate_going_aw              NUMERIC(5,1),
    ADD COLUMN IF NOT EXISTS top_courses                    TEXT[];

COMMENT ON COLUMN trainer_campaign_profile.win_rate_first_time_headgear IS 'Win% when horse wears headgear it has never worn before. Derived from racing_horse_runs headgear sequence.';
COMMENT ON COLUMN trainer_campaign_profile.win_rate_going_good_firm     IS 'Win% on Good/Firm or Firm going. Derived from racing_horse_runs.';
COMMENT ON COLUMN trainer_campaign_profile.win_rate_going_soft_plus     IS 'Win% on Soft or Heavy going.';
COMMENT ON COLUMN trainer_campaign_profile.win_rate_going_aw            IS 'Win% on All-Weather (Standard/Standard-to-Slow etc).';
COMMENT ON COLUMN trainer_campaign_profile.top_courses                  IS 'Top 3 courses by win rate (min 10 runs). Derived from racing_horse_runs.';
