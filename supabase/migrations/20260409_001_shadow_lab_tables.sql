-- ============================================================
-- VELO Shadow Lab Tables
-- Migration: 20260409_shadow_lab_tables
-- Purpose: Shadow-only persistence for G shadow evaluation,
--           rank movement analysis, and audit logging.
-- ============================================================

BEGIN;

-- ── Shadow watermarks ────────────────────────────────────────
-- Idempotency table: tracks which pipeline_run_ids have been
-- fully processed by the shadow lab.
CREATE TABLE IF NOT EXISTS public.shadow_watermarks (
    id                  BIGSERIAL PRIMARY KEY,
    service_name        TEXT NOT NULL,
    pipeline_run_id      TEXT NOT NULL,
    last_processed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rows_processed      INTEGER NOT NULL DEFAULT 0,
    UNIQUE(service_name, pipeline_run_id)
);

COMMENT ON TABLE public.shadow_watermarks IS
    'Idempotency watermark: records each pipeline_run_id processed by shadow lab.';


-- ── Shadow audit log ────────────────────────────────────────
-- Per-row processing log for observability and debugging.
CREATE TABLE IF NOT EXISTS public.shadow_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL,
    race_id         TEXT NOT NULL,
    pipeline_run_id TEXT NOT NULL,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          TEXT NOT NULL,  -- 'success' | 'error' | 'skipped'
    error_message   TEXT,
    rows_evaluated  INTEGER DEFAULT 0
);

COMMENT ON TABLE public.shadow_audit_log IS
    'Per-row audit trail for shadow lab processing.';


-- ── G shadow results ─────────────────────────────────────────
-- Stores the G shadow evaluation for each processed verdict.
CREATE TABLE IF NOT EXISTS public.velo_shadow_results (
    id                   BIGSERIAL PRIMARY KEY,
    race_id              TEXT NOT NULL,
    pipeline_run_id      TEXT NOT NULL,
    generated_at         TIMESTAMPTZ NOT NULL,
    g_shadow_multiplier  REAL,
    g_shadow_flags       TEXT[],
    g_shadow_horse_id    TEXT,
    g_shadow_mode        TEXT,   -- 'pain' | 'triumph' | 'anger' | 'neutral' | 'noop' | 'underpopulated'
    doctrines_fired      TEXT[],
    sentiment_score      REAL,
    processed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(race_id, pipeline_run_id)
);

COMMENT ON TABLE public.velo_shadow_results IS
    'G shadow evaluation per verdict row — shadow lab output only.';


-- ── Top-3 rank movement ─────────────────────────────────────
-- Stores top-3 analysis and rank movement for each processed verdict.
CREATE TABLE IF NOT EXISTS public.velo_shadow_rank_movement (
    id                    BIGSERIAL PRIMARY KEY,
    race_id               TEXT NOT NULL,
    pipeline_run_id       TEXT NOT NULL,
    generated_at          TIMESTAMPTZ NOT NULL,
    top3_scores           JSONB,   -- [{rank, horse_id, base_prob, g_shadow_mult, adjusted_prob, doctrines_fired}]
    rank_1_base_prob      REAL,
    rank_1_shadow_prob    REAL,
    shortlist_changed     BOOLEAN,
    favourite_overturned  BOOLEAN,
    processed_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(race_id, pipeline_run_id)
);

COMMENT ON TABLE public.velo_shadow_rank_movement IS
    'Top-3 rank movement analysis per verdict — measures G impact on shortlist.';


-- ── Row-Level Security ────────────────────────────────────────
-- Shadow lab service role can read production tables, write shadow tables.
-- Production service role can read shadow tables (for observability), write production tables.

ALTER TABLE public.shadow_watermarks        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shadow_audit_log         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.velo_shadow_results     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.velo_shadow_rank_movement ENABLE ROW LEVEL SECURITY;

-- Shadow lab policies (service_role_key holder = shadow lab)
CREATE POLICY "shadow_lab_full ON shadow_watermarks FOR ALL TO service_role
    USING (true) WITH CHECK (true);

CREATE POLICY "shadow_lab_full ON shadow_audit_log FOR ALL TO service_role
    USING (true) WITH CHECK (true);

CREATE POLICY "shadow_lab_full ON velo_shadow_results FOR ALL TO service_role
    USING (true) WITH CHECK (true);

CREATE POLICY "shadow_lab_full ON velo_shadow_rank_movement FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- Production observability: read shadow tables
CREATE POLICY "prod_read ON shadow_watermarks FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "prod_read ON velo_shadow_results FOR SELECT TO authenticated
    USING (true);

COMMIT;
