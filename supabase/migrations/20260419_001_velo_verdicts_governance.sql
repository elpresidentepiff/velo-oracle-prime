-- Migration: 20260419_001_velo_verdicts_governance
-- Adds ProductRouter governance columns to velo_verdicts.
-- These are computed in run_prime_today.py via ProductRouter.route_verdict()
-- and were being silently stripped on every upsert due to missing schema.

ALTER TABLE velo_verdicts
  ADD COLUMN IF NOT EXISTS assigned_product    TEXT,       -- VeloProduct: WIN_ONLY | FRAME_ONLY | EW_CANDIDATE | VISION_ONLY | PASS
  ADD COLUMN IF NOT EXISTS router_reasons      TEXT[],     -- routing policy codes that triggered assignment
  ADD COLUMN IF NOT EXISTS execution_allowed   BOOLEAN;    -- true = action permitted (WIN_ONLY / FRAME_ONLY / EW_CANDIDATE)

CREATE INDEX IF NOT EXISTS idx_velo_verdicts_assigned_product
  ON velo_verdicts (assigned_product);

CREATE INDEX IF NOT EXISTS idx_velo_verdicts_execution_allowed
  ON velo_verdicts (execution_allowed);

COMMENT ON COLUMN velo_verdicts.assigned_product IS 'Product assignment from ProductRouter.route_verdict() — betting vehicle.';
COMMENT ON COLUMN velo_verdicts.router_reasons   IS 'Array of routing policy codes (e.g. GOLD_STANDARD_ALIGNMENT).';
COMMENT ON COLUMN velo_verdicts.execution_allowed IS 'True if assigned_product permits execution; false for VISION_ONLY or PASS.';
