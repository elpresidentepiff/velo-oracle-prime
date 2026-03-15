-- ============================================================
-- VÉLØ Ingestion Spine Schema Fix
-- Date: 2026-03-15
-- Applied via: Supabase MCP (already live)
-- ============================================================
-- Problems fixed:
-- 1. races.race_id had no default — inserts would NULL-violate
-- 2. races missing columns: batch_id, race_name, join_key, raw
-- 3. races column name mismatches: off_time→time, import_date→date,
--    distance→distance_f, class_band→class, field_size→runners_count
-- 4. runners missing columns: cloth_no, raw
-- 5. runners.ts renamed to ts_rating (column already existed)
-- 6. import_files table was missing entirely
-- 7. runner_form_lines table was missing entirely
-- ============================================================

-- Fix races table
ALTER TABLE races
  ALTER COLUMN race_id SET DEFAULT gen_random_uuid()::text;

ALTER TABLE races
  ADD COLUMN IF NOT EXISTS batch_id UUID REFERENCES import_batches(id),
  ADD COLUMN IF NOT EXISTS race_name TEXT,
  ADD COLUMN IF NOT EXISTS join_key TEXT,
  ADD COLUMN IF NOT EXISTS raw JSONB;

-- Fix runners table
ALTER TABLE runners
  ADD COLUMN IF NOT EXISTS cloth_no TEXT,
  ADD COLUMN IF NOT EXISTS raw JSONB;

-- Create import_files table
CREATE TABLE IF NOT EXISTS import_files (
  id                UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  batch_id          UUID NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
  file_type         TEXT NOT NULL,
  storage_path      TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  mime_type         TEXT,
  checksum_sha256   TEXT,
  size_bytes        INTEGER,
  parsed_at         TIMESTAMPTZ,
  error             TEXT,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS import_files_batch_id_idx ON import_files(batch_id);

-- Create runner_form_lines table
CREATE TABLE IF NOT EXISTS runner_form_lines (
  id         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  runner_id  BIGINT NOT NULL REFERENCES runners(id) ON DELETE CASCADE,
  run_date   DATE,
  course     TEXT,
  distance   TEXT,
  going      TEXT,
  position   TEXT,
  rpr        INTEGER,
  ts         INTEGER,
  or_rating  INTEGER,
  notes      TEXT,
  raw        JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS runner_form_lines_runner_id_idx ON runner_form_lines(runner_id);
