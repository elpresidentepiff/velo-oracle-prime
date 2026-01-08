-- VÉLØ Phase 1: Add Validation Support
-- Migration: Add validation_report column and update batch statuses
-- Date: 2026-01-07

-- ============================================================================
-- UPDATE BATCH STATUS ENUM
-- ============================================================================

-- Add new batch statuses for validation workflow
ALTER TYPE batch_status ADD VALUE IF NOT EXISTS 'parsed';
ALTER TYPE batch_status ADD VALUE IF NOT EXISTS 'validated';
ALTER TYPE batch_status ADD VALUE IF NOT EXISTS 'needs_review';

-- ============================================================================
-- ADD VALIDATION REPORT COLUMN
-- ============================================================================

-- Add validation_report column to import_batches table
ALTER TABLE import_batches 
ADD COLUMN IF NOT EXISTS validation_report JSONB;

-- Add index for querying by status
CREATE INDEX IF NOT EXISTS idx_batches_status ON import_batches(status);

-- ============================================================================
-- ADD QUALITY METADATA TO RACES TABLE
-- ============================================================================

-- Add quality metadata columns to races table
ALTER TABLE races
ADD COLUMN IF NOT EXISTS parse_confidence FLOAT DEFAULT 1.0,
ADD COLUMN IF NOT EXISTS quality_score FLOAT DEFAULT 1.0,
ADD COLUMN IF NOT EXISTS quality_flags JSONB DEFAULT '[]'::jsonb;

-- ============================================================================
-- ADD QUALITY METADATA TO RUNNERS TABLE
-- ============================================================================

-- Add quality metadata columns to runners table
ALTER TABLE runners
ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT 1.0,
ADD COLUMN IF NOT EXISTS extraction_method TEXT DEFAULT 'table',
ADD COLUMN IF NOT EXISTS quality_flags JSONB DEFAULT '[]'::jsonb;

-- Add index for quality queries
CREATE INDEX IF NOT EXISTS idx_races_quality_score ON races(quality_score);
CREATE INDEX IF NOT EXISTS idx_runners_confidence ON runners(confidence);
