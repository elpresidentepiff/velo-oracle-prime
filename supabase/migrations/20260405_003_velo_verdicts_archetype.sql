-- Migration: add Race Archetype columns to velo_verdicts
-- Apply via: Supabase Dashboard > SQL Editor
-- Context: RaceArchetypeClassifier (Layer 3) classifies each race into one of
--   5 archetypes (Structure, Compression, PrepRelease, PublicTrap, Chaos).
--   These columns make the archetype queryable without reading full_analysis JSON.
--
-- All columns are nullable — scoring succeeds without this migration via
-- graceful fallback in persist_race_predictions().

ALTER TABLE velo_verdicts
  ADD COLUMN IF NOT EXISTS race_archetype       TEXT,      -- Structure | Compression | PrepRelease | PublicTrap | Chaos
  ADD COLUMN IF NOT EXISTS archetype_confidence TEXT,      -- high | medium | low
  ADD COLUMN IF NOT EXISTS archetype_bet_style  TEXT,      -- win | ew | watch | pass
  ADD COLUMN IF NOT EXISTS archetype_suppression BOOLEAN,  -- true = top pick is a trap to fade
  ADD COLUMN IF NOT EXISTS archetype_trap_flag  BOOLEAN;   -- true = explicit false-favourite warning

-- Index for querying by archetype (e.g. all PrepRelease races this week)
CREATE INDEX IF NOT EXISTS idx_velo_verdicts_archetype
  ON velo_verdicts (race_archetype)
  WHERE race_archetype IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_velo_verdicts_trap_flag
  ON velo_verdicts (archetype_trap_flag)
  WHERE archetype_trap_flag = TRUE;
