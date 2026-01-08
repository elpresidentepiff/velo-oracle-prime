-- VÉLØ Phase 1: Add Parse Quality Tracking and Validation Fields
-- Database Migration for Truth Layer MVP
-- Date: 2026-01-08

-- Add validation_report column to import_batches
ALTER TABLE import_batches 
ADD COLUMN IF NOT EXISTS validation_report JSONB;

-- Add quality fields to races table (if they don't exist)
ALTER TABLE races 
ADD COLUMN IF NOT EXISTS parse_confidence DECIMAL(3,2),
ADD COLUMN IF NOT EXISTS quality_score DECIMAL(3,2),
ADD COLUMN IF NOT EXISTS quality_flags TEXT[];

-- Add quality fields to runners table (if they don't exist)
ALTER TABLE runners 
ADD COLUMN IF NOT EXISTS confidence DECIMAL(3,2),
ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(20),
ADD COLUMN IF NOT EXISTS quality_flags TEXT[];

-- Add index for querying by status
CREATE INDEX IF NOT EXISTS idx_batches_status 
ON import_batches(status);

-- Add index for quality scores
CREATE INDEX IF NOT EXISTS idx_races_quality 
ON races(quality_score) 
WHERE quality_score IS NOT NULL;

-- Update batch_status enum to include new statuses
-- Note: PostgreSQL requires special handling for enum modifications
DO $$ 
BEGIN
    -- Add 'parsed' status if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'parsed' AND enumtypid = 'batch_status'::regtype) THEN
        ALTER TYPE batch_status ADD VALUE IF NOT EXISTS 'parsed';
    END IF;
    
    -- Add 'validated' status if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'validated' AND enumtypid = 'batch_status'::regtype) THEN
        ALTER TYPE batch_status ADD VALUE IF NOT EXISTS 'validated';
    END IF;
    
    -- Add 'needs_review' status if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'needs_review' AND enumtypid = 'batch_status'::regtype) THEN
        ALTER TYPE batch_status ADD VALUE IF NOT EXISTS 'needs_review';
    END IF;
END $$;

-- Add comment explaining validation_report structure
COMMENT ON COLUMN import_batches.validation_report IS 
'JSON structure containing validation results: {validated_at, total_races, valid_count, needs_review_count, rejected_count, avg_quality_score, races: [{race_id, status, issues, quality_score}]}';

-- Add comments on quality fields
COMMENT ON COLUMN races.parse_confidence IS 
'Average confidence score of all runners in race (0.0-1.0)';

COMMENT ON COLUMN races.quality_score IS 
'Overall race quality score including metadata and runner quality (0.0-1.0)';

COMMENT ON COLUMN races.quality_flags IS 
'Array of quality issues found during parsing (e.g., missing_course, duplicate_horse_names)';

COMMENT ON COLUMN runners.confidence IS 
'Confidence score for this runner data (0.0-1.0, 1.0 = perfect)';

COMMENT ON COLUMN runners.extraction_method IS 
'Extraction method used: table, text, ocr, or fallback';

COMMENT ON COLUMN runners.quality_flags IS 
'Array of quality issues found for this runner (e.g., missing_odds, suspicious_odds)';
