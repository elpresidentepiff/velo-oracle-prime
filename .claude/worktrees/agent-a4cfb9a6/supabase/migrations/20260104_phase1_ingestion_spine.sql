-- VÉLØ Phase 1: Daily Awareness Ingestion Spine
-- Database Schema for Truth Ledger
-- Date: 2026-01-04
-- 
-- Prime Rule: If VÉLØ can't point to a row in Supabase, it doesn't get to "know" it.

-- ============================================================================
-- ENUMS
-- ============================================================================

CREATE TYPE batch_status AS ENUM ('uploaded', 'parsing', 'ready', 'failed');
CREATE TYPE file_type AS ENUM ('racecards', 'runners', 'form', 'comments', 'other');

-- ============================================================================
-- TABLE: import_batches
-- One record per day import
-- ============================================================================

CREATE TABLE IF NOT EXISTS import_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_date DATE NOT NULL,
    source TEXT NOT NULL DEFAULT 'racing_post',
    status batch_status NOT NULL DEFAULT 'uploaded',
    notes TEXT,
    error_summary TEXT,
    counts JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Enforce uniqueness: one batch per date per source
    CONSTRAINT unique_batch_per_date_source UNIQUE (import_date, source)
);

-- Index for fast date lookups
CREATE INDEX idx_import_batches_date ON import_batches(import_date DESC);
CREATE INDEX idx_import_batches_status ON import_batches(status);

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_import_batches_updated_at
    BEFORE UPDATE ON import_batches
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- TABLE: import_files
-- One record per uploaded file
-- ============================================================================

CREATE TABLE IF NOT EXISTS import_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
    file_type file_type NOT NULL,
    storage_path TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type TEXT,
    checksum_sha256 TEXT,
    size_bytes BIGINT,
    parsed_at TIMESTAMPTZ,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Ensure no duplicate files per batch
    CONSTRAINT unique_file_per_batch UNIQUE (batch_id, file_type)
);

-- Index for batch lookups
CREATE INDEX idx_import_files_batch ON import_files(batch_id);
CREATE INDEX idx_import_files_type ON import_files(file_type);

-- ============================================================================
-- TABLE: races (canonical)
-- The truth state for race data
-- ============================================================================

CREATE TABLE IF NOT EXISTS races (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_date DATE NOT NULL,
    batch_id UUID REFERENCES import_batches(id) ON DELETE SET NULL,
    
    -- Core race data
    course TEXT NOT NULL,
    off_time TIME NOT NULL,
    race_name TEXT,
    race_type TEXT,
    distance TEXT,
    class_band TEXT,
    going TEXT,
    field_size INTEGER,
    prize TEXT,
    
    -- The join_key: deterministic linking for runners
    -- Format: "{import_date}|{course}|{off_time}|{race_name_or_distance}|{race_type}"
    join_key TEXT NOT NULL,
    
    -- Raw source data (immutable evidence)
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Enforce uniqueness per import date
    CONSTRAINT unique_race_join_key UNIQUE (join_key, import_date)
);

-- Indexes for fast lookups
CREATE INDEX idx_races_import_date ON races(import_date DESC);
CREATE INDEX idx_races_course ON races(course);
CREATE INDEX idx_races_off_time ON races(off_time);
CREATE INDEX idx_races_join_key ON races(join_key);
CREATE INDEX idx_races_batch ON races(batch_id);

-- ============================================================================
-- TABLE: runners (canonical)
-- The truth state for runner data
-- ============================================================================

CREATE TABLE IF NOT EXISTS runners (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    race_id UUID NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    
    -- Core runner data
    cloth_no INTEGER,
    horse_name TEXT NOT NULL,
    age INTEGER,
    sex TEXT,
    weight TEXT,
    or_rating INTEGER,
    rpr INTEGER,
    ts INTEGER,
    trainer TEXT,
    jockey TEXT,
    owner TEXT,
    draw INTEGER,
    headgear TEXT,
    form_figures TEXT,
    
    -- Raw source data (immutable evidence)
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Ensure no duplicate cloth numbers per race
    CONSTRAINT unique_runner_per_race UNIQUE (race_id, cloth_no)
);

-- Indexes for fast lookups
CREATE INDEX idx_runners_race ON runners(race_id);
CREATE INDEX idx_runners_horse_name ON runners(horse_name);
CREATE INDEX idx_runners_trainer ON runners(trainer);
CREATE INDEX idx_runners_jockey ON runners(jockey);

-- ============================================================================
-- TABLE: runner_form_lines (optional in Phase 1, recommended)
-- Historical form data per runner
-- ============================================================================

CREATE TABLE IF NOT EXISTS runner_form_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    runner_id UUID NOT NULL REFERENCES runners(id) ON DELETE CASCADE,
    
    -- Form line data
    run_date DATE,
    course TEXT,
    distance TEXT,
    going TEXT,
    position TEXT,
    rpr INTEGER,
    ts INTEGER,
    or_rating INTEGER,
    notes TEXT,
    
    -- Raw source data (immutable evidence)
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX idx_form_lines_runner ON runner_form_lines(runner_id);
CREATE INDEX idx_form_lines_date ON runner_form_lines(run_date DESC);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- Clean security model: UI reads, Service writes
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE races ENABLE ROW LEVEL SECURITY;
ALTER TABLE runners ENABLE ROW LEVEL SECURITY;
ALTER TABLE runner_form_lines ENABLE ROW LEVEL SECURITY;

-- Policy: Authenticated users can SELECT (read-only from UI)
CREATE POLICY "Allow authenticated users to read import_batches"
    ON import_batches FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow authenticated users to read import_files"
    ON import_files FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow authenticated users to read races"
    ON races FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow authenticated users to read runners"
    ON runners FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow authenticated users to read runner_form_lines"
    ON runner_form_lines FOR SELECT
    TO authenticated
    USING (true);

-- Policy: Service role can do everything (Railway FastAPI)
-- Note: Service role bypasses RLS by default, but we document the intent

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to generate join_key for races
CREATE OR REPLACE FUNCTION generate_race_join_key(
    p_import_date DATE,
    p_course TEXT,
    p_off_time TIME,
    p_race_name TEXT,
    p_distance TEXT,
    p_class_band TEXT,
    p_race_type TEXT
) RETURNS TEXT AS $$
DECLARE
    race_identifier TEXT;
BEGIN
    -- Use race_name if available, else use distance|class_band
    IF p_race_name IS NOT NULL AND p_race_name != '' THEN
        race_identifier := p_race_name;
    ELSE
        race_identifier := COALESCE(p_distance, '') || '|' || COALESCE(p_class_band, '');
    END IF;
    
    -- Format: "{import_date}|{course}|{off_time}|{race_identifier}|{race_type}"
    RETURN p_import_date::TEXT || '|' || 
           COALESCE(p_course, '') || '|' || 
           COALESCE(p_off_time::TEXT, '') || '|' || 
           race_identifier || '|' || 
           COALESCE(p_race_type, '');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to get batch statistics
CREATE OR REPLACE FUNCTION get_batch_stats(p_batch_id UUID)
RETURNS JSONB AS $$
DECLARE
    stats JSONB;
BEGIN
    SELECT jsonb_build_object(
        'races_count', COUNT(DISTINCT r.id),
        'runners_count', COUNT(ru.id),
        'files_count', COUNT(DISTINCT f.id),
        'files_parsed', COUNT(DISTINCT f.id) FILTER (WHERE f.parsed_at IS NOT NULL)
    )
    INTO stats
    FROM import_batches b
    LEFT JOIN import_files f ON f.batch_id = b.id
    LEFT JOIN races r ON r.batch_id = b.id
    LEFT JOIN runners ru ON ru.race_id = r.id
    WHERE b.id = p_batch_id
    GROUP BY b.id;
    
    RETURN COALESCE(stats, '{}'::jsonb);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEWS FOR CONVENIENCE
-- ============================================================================

-- View: Daily race summary
CREATE OR REPLACE VIEW daily_race_summary AS
SELECT 
    r.import_date,
    r.course,
    r.off_time,
    r.race_name,
    r.race_type,
    r.distance,
    r.class_band,
    r.going,
    r.field_size,
    r.prize,
    COUNT(ru.id) as runner_count,
    r.id as race_id,
    r.batch_id
FROM races r
LEFT JOIN runners ru ON ru.race_id = r.id
GROUP BY r.id, r.import_date, r.course, r.off_time, r.race_name, 
         r.race_type, r.distance, r.class_band, r.going, r.field_size, 
         r.prize, r.batch_id
ORDER BY r.import_date DESC, r.off_time ASC;

-- View: Batch status overview
CREATE OR REPLACE VIEW batch_status_overview AS
SELECT 
    b.id,
    b.import_date,
    b.source,
    b.status,
    b.notes,
    b.error_summary,
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
         b.error_summary, b.counts, b.created_at, b.updated_at
ORDER BY b.import_date DESC;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE import_batches IS 'One record per day import. Enforces uniqueness per date/source.';
COMMENT ON TABLE import_files IS 'One record per uploaded file with metadata and checksums.';
COMMENT ON TABLE races IS 'Canonical race data with deterministic join_key for linking.';
COMMENT ON TABLE runners IS 'Canonical runner data linked to races via race_id.';
COMMENT ON TABLE runner_form_lines IS 'Historical form data per runner (optional Phase 1).';

COMMENT ON COLUMN races.join_key IS 'Deterministic key: {import_date}|{course}|{off_time}|{race_name_or_distance}|{race_type}';
COMMENT ON COLUMN races.raw IS 'Immutable evidence: original source row as JSONB for debugging.';
COMMENT ON COLUMN runners.raw IS 'Immutable evidence: original source row as JSONB for debugging.';

COMMENT ON FUNCTION generate_race_join_key IS 'Generates deterministic join_key for race matching.';
COMMENT ON FUNCTION get_batch_stats IS 'Returns statistics for a given batch_id.';

-- ============================================================================
-- GRANT PERMISSIONS
-- ============================================================================

-- Grant SELECT to authenticated users (UI read access)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated;

-- Grant ALL to service_role (Railway FastAPI full access)
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO service_role;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

-- Phase 1 schema deployed successfully
-- Next: Create storage bucket 'rp_imports' via Supabase dashboard or API
-- Next: Implement Railway FastAPI endpoints
-- Next: Build Next.js Ops Console UI

-- Verification queries:
-- SELECT * FROM batch_status_overview;
-- SELECT * FROM daily_race_summary WHERE import_date = CURRENT_DATE;
