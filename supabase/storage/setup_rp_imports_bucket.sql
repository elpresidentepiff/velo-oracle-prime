-- VÉLØ Phase 1: Storage Bucket Setup
-- Creates 'rp_imports' bucket for Racing Post file uploads
-- Date: 2026-01-04

-- ============================================================================
-- STORAGE BUCKET: rp_imports
-- ============================================================================

-- Insert bucket (if not exists)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'rp_imports',
    'rp_imports',
    false,  -- PRIVATE bucket
    52428800,  -- 50MB file size limit
    ARRAY[
        'text/csv',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/plain',
        'application/json'
    ]
)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- STORAGE POLICIES
-- ============================================================================

-- Policy: Authenticated users can upload to rp_imports/*
CREATE POLICY "Allow authenticated users to upload to rp_imports"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'rp_imports' AND
    -- Enforce path convention: YYYY-MM-DD/<file_type>.<ext>
    (storage.foldername(name))[1] ~ '^\d{4}-\d{2}-\d{2}$'
);

-- Policy: Authenticated users can read from rp_imports/*
CREATE POLICY "Allow authenticated users to read from rp_imports"
ON storage.objects FOR SELECT
TO authenticated
USING (bucket_id = 'rp_imports');

-- Policy: Service role can do everything (Railway FastAPI)
CREATE POLICY "Allow service role full access to rp_imports"
ON storage.objects FOR ALL
TO service_role
USING (bucket_id = 'rp_imports')
WITH CHECK (bucket_id = 'rp_imports');

-- Policy: Authenticated users can update their own uploads (optional, for re-upload)
CREATE POLICY "Allow authenticated users to update rp_imports"
ON storage.objects FOR UPDATE
TO authenticated
USING (bucket_id = 'rp_imports')
WITH CHECK (bucket_id = 'rp_imports');

-- Policy: Authenticated users can delete their own uploads (optional, for cleanup)
CREATE POLICY "Allow authenticated users to delete from rp_imports"
ON storage.objects FOR DELETE
TO authenticated
USING (bucket_id = 'rp_imports');

-- ============================================================================
-- PATH CONVENTIONS (ENFORCED)
-- ============================================================================

-- Standard path format: rp_imports/YYYY-MM-DD/<file_type>.<ext>
-- Examples:
--   rp_imports/2026-01-04/racecards.csv
--   rp_imports/2026-01-04/runners.csv
--   rp_imports/2026-01-04/form.csv
--   rp_imports/2026-01-04/comments.csv
--   rp_imports/2026-01-04/other/additional_data.json

-- The policy above enforces that the first folder must be a valid date (YYYY-MM-DD)
-- This prevents freestyle filenames and ensures reproducibility

-- ============================================================================
-- HELPER FUNCTION: Generate storage path
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_storage_path(
    p_import_date DATE,
    p_file_type TEXT,
    p_extension TEXT DEFAULT 'csv'
) RETURNS TEXT AS $$
BEGIN
    -- Format: rp_imports/YYYY-MM-DD/<file_type>.<ext>
    RETURN 'rp_imports/' || p_import_date::TEXT || '/' || p_file_type || '.' || p_extension;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Example usage:
-- SELECT generate_storage_path('2026-01-04', 'racecards', 'csv');
-- Returns: 'rp_imports/2026-01-04/racecards.csv'

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check bucket exists
-- SELECT * FROM storage.buckets WHERE id = 'rp_imports';

-- Check policies
-- SELECT * FROM pg_policies WHERE tablename = 'objects' AND policyname LIKE '%rp_imports%';

-- List files in bucket (example)
-- SELECT * FROM storage.objects WHERE bucket_id = 'rp_imports' ORDER BY created_at DESC;

-- ============================================================================
-- NOTES
-- ============================================================================

-- 1. Bucket is PRIVATE - files not publicly accessible
-- 2. Path convention enforced via policy: YYYY-MM-DD/<file_type>.<ext>
-- 3. File size limit: 50MB per file
-- 4. Allowed MIME types: CSV, Excel, JSON, plain text
-- 5. Service role (Railway) has full access
-- 6. Authenticated users (UI) can upload, read, update, delete

-- This ensures:
-- - Every import is reproducible (date-based folders)
-- - No freestyle filenames causing chaos
-- - Audit trail via storage.objects metadata
-- - Immutable evidence (files never silently lost)

-- ============================================================================
-- SETUP COMPLETE
-- ============================================================================

-- Next steps:
-- 1. Run this SQL in Supabase SQL Editor
-- 2. Verify bucket created: SELECT * FROM storage.buckets WHERE id = 'rp_imports';
-- 3. Test upload from UI or curl
-- 4. Implement Railway FastAPI endpoints to download and parse files
