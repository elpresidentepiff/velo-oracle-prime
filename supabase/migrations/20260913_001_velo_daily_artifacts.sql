-- VELO daily artifacts: tables for data that until 2026-09-13 existed only as local files.
-- Operator-approved 2026-09-13 ("do all 5"). Applied via Supabase MCP apply_migration.
-- Writers: scripts/ops/persist_daily_artifacts.py (idempotent upserts, --execute gated).
-- RLS on, service_role only: app/main.py reads with SUPABASE_SERVICE_ROLE_KEY, the
-- publishable key must not see council text or passports.

-- Council verdict per race day (data/council_runs/council_run_YYYY-MM-DD.json)
CREATE TABLE IF NOT EXISTS public.velo_council_runs (
    run_date         DATE        PRIMARY KEY,
    council_status   TEXT,
    council_verdict  TEXT,
    final_report     TEXT,
    metadata         JSONB,
    evidence_packet  JSONB,
    agent_responses  JSONB,
    verifications    JSONB,
    source_path      TEXT        NOT NULL,
    source_sha256    TEXT        NOT NULL,
    persisted_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Mission Control gate state per race day (data/mission_control/YYYY-MM-DD_mission_control.json)
CREATE TABLE IF NOT EXISTS public.velo_mission_control (
    run_date                DATE        PRIMARY KEY,
    generated_at            TIMESTAMPTZ,
    source_truth            TEXT,
    learning_gate_status    TEXT,
    promotion_gate_status   TEXT,
    council_verdict         TEXT,
    flatline_count          INTEGER,
    identity_failure_count  INTEGER,
    runners_snapshotted     INTEGER,
    gate_reasons            JSONB,
    payload                 JSONB       NOT NULL,
    source_path             TEXT        NOT NULL,
    source_sha256           TEXT        NOT NULL,
    persisted_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Multi-model sigma ledger, one row per race (data/model_comparison_ledger.csv).
-- public.model_comparison is a per-model aggregate with a different shape and stays untouched.
CREATE TABLE IF NOT EXISTS public.velo_model_comparison_ledger (
    run_date              DATE        NOT NULL,
    race_id               TEXT        NOT NULL,
    course                TEXT,
    off_time              TEXT,
    velo_top_pick         TEXT,
    velo_outcome          TEXT,
    velo_assigned_product TEXT,
    velo_ew_outcome       TEXT,
    velo_miss_class       TEXT,
    norpr_top_pick        TEXT,
    norpr_prob            NUMERIC,
    norpr_outcome         TEXT,
    norpr_miss_class      TEXT,
    nb_top_pick           TEXT,
    nb_prob               NUMERIC,
    nb_outcome            TEXT,
    nb_miss_class         TEXT,
    champion_top_pick     TEXT,
    champion_prob         NUMERIC,
    champion_outcome      TEXT,
    champion_miss_class   TEXT,
    mp_top_pick           TEXT,
    mp_prob               NUMERIC,
    mp_outcome            TEXT,
    mp_miss_class         TEXT,
    nbc_top_pick          TEXT,
    nbc_prob              NUMERIC,
    nbc_outcome           TEXT,
    nbc_miss_class        TEXT,
    winner                TEXT,
    winner_sp             NUMERIC,
    top3                  TEXT,
    persisted_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_date, race_id)
);

-- New Build horse passport bank (data/new_build/passports/horse_passports_v1.jsonl).
-- Until now git was this bank's only durable copy (ONE_TRUTH open issue #4).
CREATE TABLE IF NOT EXISTS public.new_build_horse_passports (
    horse_rp_uid   BIGINT      PRIMARY KEY,
    horse_name     TEXT,
    last_run_date  DATE,
    career_runs    INTEGER,
    wins           INTEGER,
    win_rate       NUMERIC,
    passport       JSONB       NOT NULL,
    source_sha256  TEXT        NOT NULL,
    persisted_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Daily JSON report artifacts the dashboard serves (LLM briefs, operator cards, shadow lanes).
CREATE TABLE IF NOT EXISTS public.velo_report_artifacts (
    artifact_type  TEXT        NOT NULL,
    run_date       DATE        NOT NULL,
    payload        JSONB       NOT NULL,
    source_path    TEXT        NOT NULL,
    source_mtime   TIMESTAMPTZ,
    source_sha256  TEXT        NOT NULL,
    persisted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (artifact_type, run_date)
);

CREATE INDEX IF NOT EXISTS idx_vmcl_run_date ON public.velo_model_comparison_ledger (run_date);
CREATE INDEX IF NOT EXISTS idx_nbhp_last_run ON public.new_build_horse_passports (last_run_date);
CREATE INDEX IF NOT EXISTS idx_vra_run_date  ON public.velo_report_artifacts (run_date);

DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['velo_council_runs','velo_mission_control','velo_model_comparison_ledger',
                           'new_build_horse_passports','velo_report_artifacts']
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polname = 'service_role_all_' || t) THEN
      EXECUTE format('CREATE POLICY %I ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true)',
                     'service_role_all_' || t, t);
    END IF;
  END LOOP;
END $$;
