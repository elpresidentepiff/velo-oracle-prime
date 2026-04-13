-- Migration: apply pending horse_state + archetype + post_race_reviews columns
-- Applied: 2026-04-13 by audit fix pipeline
-- Context: migrations 002/003 were present in repo but never applied to production Supabase.
--   persist_verdict was silently stripping these columns on every upsert, destroying
--   observability data. This migration was applied via Supabase Management API.
--
-- This file is a record only — the actual DDL was executed directly.
-- Re-running is safe (all statements use IF NOT EXISTS / IF NOT EXISTS).

-- From 20260405_002_velo_verdicts_horse_state.sql
ALTER TABLE velo_verdicts
  ADD COLUMN IF NOT EXISTS top_horse_readiness_state  TEXT,
  ADD COLUMN IF NOT EXISTS top_horse_release_state    TEXT,
  ADD COLUMN IF NOT EXISTS top_horse_rest_pattern     TEXT,
  ADD COLUMN IF NOT EXISTS top_horse_class_move_state TEXT,
  ADD COLUMN IF NOT EXISTS top_horse_stable_heat      TEXT,
  ADD COLUMN IF NOT EXISTS top_horse_jockey_signal    TEXT,
  ADD COLUMN IF NOT EXISTS top_horse_market_state     TEXT,
  ADD COLUMN IF NOT EXISTS top_horse_race_fit_state   TEXT,
  ADD COLUMN IF NOT EXISTS top_horse_chaos_exposure   TEXT,
  ADD COLUMN IF NOT EXISTS top_horse_signal_count     INTEGER,
  ADD COLUMN IF NOT EXISTS top_horse_state_evidence   TEXT[];

CREATE INDEX IF NOT EXISTS idx_velo_verdicts_release_state
  ON velo_verdicts (top_horse_release_state)
  WHERE top_horse_release_state IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_velo_verdicts_readiness_state
  ON velo_verdicts (top_horse_readiness_state)
  WHERE top_horse_readiness_state IS NOT NULL;

-- From 20260405_003_velo_verdicts_archetype.sql
ALTER TABLE velo_verdicts
  ADD COLUMN IF NOT EXISTS race_archetype       TEXT,
  ADD COLUMN IF NOT EXISTS archetype_confidence TEXT,
  ADD COLUMN IF NOT EXISTS archetype_bet_style  TEXT,
  ADD COLUMN IF NOT EXISTS archetype_suppression BOOLEAN,
  ADD COLUMN IF NOT EXISTS archetype_trap_flag  BOOLEAN;

CREATE INDEX IF NOT EXISTS idx_velo_verdicts_archetype
  ON velo_verdicts (race_archetype)
  WHERE race_archetype IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_velo_verdicts_trap_flag
  ON velo_verdicts (archetype_trap_flag)
  WHERE archetype_trap_flag = TRUE;

-- Fix: velo_post_race_reviews missing created_at (truth-loop query dependency)
ALTER TABLE velo_post_race_reviews
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
