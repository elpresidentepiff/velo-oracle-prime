-- PR #22: Add Hard Validation Gates
-- Add rejected_bad_output status and validation fields
-- Date: 2026-01-09

-- ============================================================================
-- 1. Add rejected_bad_output to batch_status enum
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'rejected_bad_output' AND enumtypid = 'batch_status'::regtype) THEN
        ALTER TYPE batch_status ADD VALUE IF NOT EXISTS 'rejected_bad_output';
    END IF;
END$$;

-- ============================================================================
-- 2. Add validation_errors column to import_batches
-- ============================================================================

ALTER TABLE import_batches
ADD COLUMN IF NOT EXISTS validation_errors JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN import_batches.validation_errors IS 'Array of validation error messages when status is rejected_bad_output';

-- ============================================================================
-- 3. Add distance columns to races table
-- ============================================================================

-- Add canonical distance columns
ALTER TABLE races
ADD COLUMN IF NOT EXISTS distance_yards INTEGER,
ADD COLUMN IF NOT EXISTS distance_furlongs NUMERIC(5,2),
ADD COLUMN IF NOT EXISTS distance_meters INTEGER;

-- Add indexes for distance lookups
CREATE INDEX IF NOT EXISTS idx_races_distance_yards ON races(distance_yards);
CREATE INDEX IF NOT EXISTS idx_races_distance_furlongs ON races(distance_furlongs);

-- Add comments
COMMENT ON COLUMN races.distance_yards IS 'Canonical distance in yards (source of truth)';
COMMENT ON COLUMN races.distance_furlongs IS 'Distance in furlongs (derived from yards)';
COMMENT ON COLUMN races.distance_meters IS 'Distance in meters (derived from yards)';

-- ============================================================================
-- 4. Add age validation constraint to runners table
-- ============================================================================

-- Add constraint: age must be between 2 and 15 (realistic for horses)
ALTER TABLE runners
DROP CONSTRAINT IF EXISTS check_age_range;

ALTER TABLE runners
ADD CONSTRAINT check_age_range CHECK (age IS NULL OR (age >= 2 AND age <= 15));

COMMENT ON CONSTRAINT check_age_range ON runners IS 'Horses racing age must be between 2 and 15 years';

-- ============================================================================
-- 5. Add days_since_run to runners (to separate from age)
-- ============================================================================

ALTER TABLE runners
ADD COLUMN IF NOT EXISTS days_since_run INTEGER;

COMMENT ON COLUMN runners.days_since_run IS 'Days since last run (separate from age to fix parsing bug)';

-- ============================================================================
-- 6. Update batch_status_overview view to include validation_errors
-- ============================================================================

CREATE OR REPLACE VIEW batch_status_overview AS
SELECT 
    b.id,
    b.import_date,
    b.source,
    b.status,
    b.notes,
    b.error_summary,
    b.validation_errors,
    b.counts,
    b.created_at,
    b.updated_at,
    COUNT(DISTINCT f.id) as files_count,
    COUNT(DISTINCT f.id) FILTER (WHERE f.parsed_at IS NOT NULL) as files_parsed,
    COUNT(DISTINCT r.id) as races_count,
    COUNT(ru.id) as runners_count
FROM import_batches b
LEFT JOIN import_files f ON f.batch_id = b.id
LEFT JOIN races r ON r.batch_id = b.id
LEFT JOIN runners ru ON ru.race_id = r.id
GROUP BY b.id, b.import_date, b.source, b.status, b.notes, 
         b.error_summary, b.validation_errors, b.counts, b.created_at, b.updated_at
ORDER BY b.import_date DESC;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

-- PR #22 schema updates deployed successfully
-- Next: Implement racingpost_pdf parser module
-- Next: Implement hard validation gates
-- Next: Update ingestion endpoint to use new validation
