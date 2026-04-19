-- Migration: 20260418_001_velo_verdicts_honesty_labels
--
-- Consolidates missing honesty and observability labels identified during
-- the Lane 4 Ingestion Sequencing and Training Sigma audits.
--
-- Columns enable:
--   1. Mutation Detection (fetch_timestamp, predicted_field_size)
--   2. Calibration (confidence_level_raw, confidence_level_effective)
--   3. Ensemble Audit (active_components, excluded_from_ensemble)
--   4. Sentient Bridge Audit (g_shadow_multiplier)

ALTER TABLE velo_verdicts
  ADD COLUMN IF NOT EXISTS fetch_timestamp           TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS predicted_field_size      INTEGER,
  ADD COLUMN IF NOT EXISTS confidence_level_raw      TEXT,
  ADD COLUMN IF NOT EXISTS confidence_level_effective TEXT,
  ADD COLUMN IF NOT EXISTS active_components         TEXT[],
  ADD COLUMN IF NOT EXISTS excluded_from_ensemble    TEXT[],
  ADD COLUMN IF NOT EXISTS g_shadow_multiplier       FLOAT,
  ADD COLUMN IF NOT EXISTS a_tier_weak_place_flag    BOOLEAN DEFAULT FALSE;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_velo_verdicts_fetch_time
  ON velo_verdicts (fetch_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_velo_verdicts_mutated_field
  ON velo_verdicts (predicted_field_size);

COMMENT ON COLUMN velo_verdicts.fetch_timestamp IS 'Exact timestamp of Racing API fetch to detect ground-shift mutations.';
COMMENT ON COLUMN velo_verdicts.predicted_field_size IS 'Number of runners at scoring time (06:00 UTC) to reconcile against actual field size.';
