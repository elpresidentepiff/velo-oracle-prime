-- Migration: add region column to velo_verdicts for UK/IRE contamination verification
-- Date: 2026-03-23
-- Purpose: Persist region at scoring time so UK/IRE filtering can be verified post-hoc from DB
-- Author: VOX (oracle@velo.ai)

BEGIN;

-- Add region column to velo_verdicts
ALTER TABLE public.velo_verdicts
ADD COLUMN IF NOT EXISTS region TEXT DEFAULT '' NOT NULL;

-- Index for fast contamination checks
CREATE INDEX IF NOT EXISTS idx_velo_verdicts_region ON public.velo_verdicts(region);

-- Verify no non-UK/IRE regions exist (should be none if UK/IRE filter is working)
-- This is informational — uncomment to run:
-- SELECT region, count(*) as count
-- FROM public.velo_verdicts
-- GROUP BY region
-- ORDER BY count DESC;

COMMIT;

-- Grant info only (RLS already restricts writes to service_role)
-- This column is safe to add: never affects scoring logic, only enables post-hoc verification
