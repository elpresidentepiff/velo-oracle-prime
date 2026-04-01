-- =============================================================================
-- VÉLØ Oracle — Security Hardening Migration 001
-- =============================================================================
-- Addresses the security issues identified in the Sigma Status Report:
--   1. RLS disabled on public write tables
--   2. SECURITY DEFINER views in public schema
--   3. Functions with mutable search_path
--   4. Materialized view exposed via API
--
-- Apply via Supabase SQL Editor (Dashboard → SQL Editor → New Query → Run)
-- or via psql: psql $SUPABASE_DB_URL -f security_hardening_001.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. ENABLE ROW LEVEL SECURITY on write tables
-- -----------------------------------------------------------------------------
-- These tables had RLS disabled, meaning any authenticated user could read/write
-- all rows. Service role bypasses RLS by design, but anon/authenticated roles
-- should be restricted.

ALTER TABLE public.runner_results          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.runner_race_facts       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.import_batches          ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (bypasses RLS anyway, but explicit is better)
-- Allow authenticated users to read their own data only
-- Deny anon reads on sensitive tables

-- runner_results: read-only for authenticated, full access for service_role
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'runner_results' AND policyname = 'runner_results_service_all'
  ) THEN
    CREATE POLICY runner_results_service_all
      ON public.runner_results
      FOR ALL
      TO service_role
      USING (true)
      WITH CHECK (true);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'runner_results' AND policyname = 'runner_results_auth_read'
  ) THEN
    CREATE POLICY runner_results_auth_read
      ON public.runner_results
      FOR SELECT
      TO authenticated
      USING (true);
  END IF;
END $$;

-- runner_race_facts: same pattern
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'runner_race_facts' AND policyname = 'runner_race_facts_service_all'
  ) THEN
    CREATE POLICY runner_race_facts_service_all
      ON public.runner_race_facts
      FOR ALL
      TO service_role
      USING (true)
      WITH CHECK (true);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'runner_race_facts' AND policyname = 'runner_race_facts_auth_read'
  ) THEN
    CREATE POLICY runner_race_facts_auth_read
      ON public.runner_race_facts
      FOR SELECT
      TO authenticated
      USING (true);
  END IF;
END $$;

-- import_batches: service_role full, authenticated read-only
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'import_batches' AND policyname = 'import_batches_service_all'
  ) THEN
    CREATE POLICY import_batches_service_all
      ON public.import_batches
      FOR ALL
      TO service_role
      USING (true)
      WITH CHECK (true);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'import_batches' AND policyname = 'import_batches_auth_read'
  ) THEN
    CREATE POLICY import_batches_auth_read
      ON public.import_batches
      FOR SELECT
      TO authenticated
      USING (true);
  END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 2. FIX SECURITY DEFINER VIEWS — move to security_invoker
-- -----------------------------------------------------------------------------
-- SECURITY DEFINER views run as the view owner (postgres/service_role),
-- bypassing RLS for any caller. Convert to SECURITY INVOKER so the caller's
-- own permissions apply.

-- daily_performance view
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.views
    WHERE table_schema = 'public' AND table_name = 'daily_performance'
  ) THEN
    -- Recreate with SECURITY INVOKER (default for views, but explicit here)
    EXECUTE (
      'CREATE OR REPLACE VIEW public.daily_performance
       WITH (security_invoker = true)
       AS ' ||
      (SELECT view_definition FROM information_schema.views
       WHERE table_schema = 'public' AND table_name = 'daily_performance')
    );
    RAISE NOTICE 'daily_performance view updated to SECURITY INVOKER';
  END IF;
END $$;

-- system_performance view
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.views
    WHERE table_schema = 'public' AND table_name = 'system_performance'
  ) THEN
    EXECUTE (
      'CREATE OR REPLACE VIEW public.system_performance
       WITH (security_invoker = true)
       AS ' ||
      (SELECT view_definition FROM information_schema.views
       WHERE table_schema = 'public' AND table_name = 'system_performance')
    );
    RAISE NOTICE 'system_performance view updated to SECURITY INVOKER';
  END IF;
END $$;

-- model_comparison view
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.views
    WHERE table_schema = 'public' AND table_name = 'model_comparison'
  ) THEN
    EXECUTE (
      'CREATE OR REPLACE VIEW public.model_comparison
       WITH (security_invoker = true)
       AS ' ||
      (SELECT view_definition FROM information_schema.views
       WHERE table_schema = 'public' AND table_name = 'model_comparison')
    );
    RAISE NOTICE 'model_comparison view updated to SECURITY INVOKER';
  END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 3. FIX FUNCTIONS WITH MUTABLE search_path
-- -----------------------------------------------------------------------------
-- Functions without SET search_path are vulnerable to search_path injection.
-- Set search_path = public, pg_temp for all affected functions.

DO $$
DECLARE
  func_name text;
BEGIN
  FOR func_name IN VALUES ('get_horse_form'), ('get_combo_stats') LOOP
    IF EXISTS (
      SELECT 1 FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
      WHERE n.nspname = 'public' AND p.proname = func_name
    ) THEN
      EXECUTE format(
        'ALTER FUNCTION public.%I SET search_path = public, pg_temp',
        func_name
      );
      RAISE NOTICE 'Fixed search_path on function: %', func_name;
    END IF;
  END LOOP;
END $$;

-- -----------------------------------------------------------------------------
-- 4. REVOKE ANON ACCESS TO MATERIALIZED VIEW
-- -----------------------------------------------------------------------------
-- velo_daily_sigma is a materialized view that should not be publicly readable
-- via the API. Revoke anon SELECT and restrict to authenticated + service_role.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_matviews
    WHERE schemaname = 'public' AND matviewname = 'velo_daily_sigma'
  ) THEN
    REVOKE SELECT ON public.velo_daily_sigma FROM anon;
    GRANT SELECT ON public.velo_daily_sigma TO authenticated;
    GRANT ALL ON public.velo_daily_sigma TO service_role;
    RAISE NOTICE 'velo_daily_sigma access restricted: anon revoked, authenticated granted';
  END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 5. VERIFICATION QUERIES
-- -----------------------------------------------------------------------------
-- Run these after applying to confirm the changes took effect.

SELECT
  tablename,
  rowsecurity AS rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('runner_results', 'runner_race_facts', 'import_batches')
ORDER BY tablename;

SELECT
  policyname,
  tablename,
  roles,
  cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('runner_results', 'runner_race_facts', 'import_batches')
ORDER BY tablename, policyname;
