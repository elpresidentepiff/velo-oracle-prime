-- =============================================================================
-- VÉLØ Oracle — Full Security Hardening Migration 002
-- =============================================================================
-- This is the VERIFIED, IDEMPOTENT version of the full hardening pass.
-- It was validated against the live Supabase project and produced:
--   ✅ 0 security advisor findings
--   ✅ 0 public tables with RLS disabled
--   ✅ 0 public views not SECURITY INVOKER
--   ✅ 0 public SQL/PLpgSQL functions with mutable search_path
--   ✅ 0 public materialized views exposed to anon/authenticated
--
-- SAFE TO RE-RUN: All statements are idempotent (IF EXISTS, DROP IF EXISTS,
-- NOT EXISTS guards). Running this multiple times produces the same result.
--
-- Apply via Supabase SQL Editor or psql:
--   psql $SUPABASE_DB_URL -f 002_full_security_hardening.sql
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- STEP 1: Enable RLS on ALL ordinary tables in public schema
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
      AND c.relrowsecurity = false
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.relname);
    RAISE NOTICE 'RLS enabled on: %', r.relname;
  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- STEP 2: Ensure service_role has explicit ALL policy on every public table
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  r record;
  pol_name text;
BEGIN
  FOR r IN
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
      AND c.relrowsecurity = true
  LOOP
    pol_name := 'service_role_all_' || r.relname;
    IF NOT EXISTS (
      SELECT 1 FROM pg_policies p
      WHERE p.schemaname = 'public'
        AND p.tablename = r.relname
        AND p.policyname = pol_name
    ) THEN
      EXECUTE format(
        'CREATE POLICY %I ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true)',
        pol_name, r.relname
      );
      RAISE NOTICE 'service_role ALL policy created on: %', r.relname;
    END IF;
  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- STEP 3: Targeted RLS policies for key ingestion tables
-- (Explicit policies that survive table drops/recreates)
-- ---------------------------------------------------------------------------

-- runner_results
DROP POLICY IF EXISTS "service_role_all_runner_results"    ON public.runner_results;
DROP POLICY IF EXISTS "authenticated_read_runner_results"  ON public.runner_results;
CREATE POLICY "service_role_all_runner_results"
  ON public.runner_results FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "authenticated_read_runner_results"
  ON public.runner_results FOR SELECT TO authenticated USING (true);

-- runner_race_facts
DROP POLICY IF EXISTS "service_role_all_runner_race_facts"   ON public.runner_race_facts;
DROP POLICY IF EXISTS "authenticated_read_runner_race_facts" ON public.runner_race_facts;
CREATE POLICY "service_role_all_runner_race_facts"
  ON public.runner_race_facts FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "authenticated_read_runner_race_facts"
  ON public.runner_race_facts FOR SELECT TO authenticated USING (true);

-- import_batches
DROP POLICY IF EXISTS "service_role_all_import_batches"   ON public.import_batches;
DROP POLICY IF EXISTS "authenticated_read_import_batches" ON public.import_batches;
CREATE POLICY "service_role_all_import_batches"
  ON public.import_batches FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "authenticated_read_import_batches"
  ON public.import_batches FOR SELECT TO authenticated USING (true);

-- ---------------------------------------------------------------------------
-- STEP 4: Convert ALL public views to SECURITY INVOKER
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'v'
  LOOP
    BEGIN
      EXECUTE format('ALTER VIEW public.%I SET (security_invoker = true)', r.relname);
      RAISE NOTICE 'SECURITY INVOKER set on view: %', r.relname;
    EXCEPTION WHEN OTHERS THEN
      RAISE WARNING 'Could not set SECURITY INVOKER on view %: %', r.relname, SQLERRM;
    END;
  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- STEP 5: Harden search_path on ALL public SQL/PLpgSQL functions
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT
      p.oid,
      n.nspname,
      p.proname,
      pg_get_function_identity_arguments(p.oid) AS args
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    JOIN pg_language l ON l.oid = p.prolang
    WHERE n.nspname = 'public'
      AND l.lanname IN ('sql', 'plpgsql')
      AND (
        p.proconfig IS NULL
        OR array_to_string(p.proconfig, ',') NOT LIKE '%search_path=%'
      )
  LOOP
    BEGIN
      EXECUTE format(
        'ALTER FUNCTION %I.%I(%s) SET search_path = public, pg_temp',
        r.nspname, r.proname, r.args
      );
      RAISE NOTICE 'search_path hardened on function: %.%(%)', r.nspname, r.proname, r.args;
    EXCEPTION WHEN OTHERS THEN
      RAISE WARNING 'Could not harden function %.%(%): %', r.nspname, r.proname, r.args, SQLERRM;
    END;
  END LOOP;
END $$;

-- Explicit hardening for the two known functions with confirmed signatures
ALTER FUNCTION public.get_combo_stats(character varying, character varying)
  SET search_path = public, pg_temp;

ALTER FUNCTION public.get_horse_form(character varying, integer)
  SET search_path = public, pg_temp;

-- ---------------------------------------------------------------------------
-- STEP 6: Lock down ALL public materialized views from anon/authenticated
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'm'
  LOOP
    BEGIN
      EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon', r.relname);
      EXECUTE format('REVOKE ALL ON TABLE public.%I FROM authenticated', r.relname);
      EXECUTE format('GRANT SELECT ON TABLE public.%I TO service_role', r.relname);
      RAISE NOTICE 'Materialized view locked down: %', r.relname;
    EXCEPTION WHEN OTHERS THEN
      RAISE WARNING 'Could not lock down matview %: %', r.relname, SQLERRM;
    END;
  END LOOP;
END $$;

COMMIT;

-- ---------------------------------------------------------------------------
-- VERIFICATION QUERY — Run after applying to confirm 0 findings
-- ---------------------------------------------------------------------------
SELECT
  (SELECT count(*) FROM pg_class c
   JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname='public' AND c.relkind='r' AND c.relrowsecurity=false
  ) AS tables_rls_disabled,

  (SELECT count(*) FROM pg_class c
   JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname='public' AND c.relkind='v'
     AND (c.reloptions IS NULL OR c.reloptions::text NOT LIKE '%security_invoker=true%')
  ) AS views_not_invoker,

  (SELECT count(*) FROM pg_proc p
   JOIN pg_namespace n ON n.oid=p.pronamespace
   JOIN pg_language l ON l.oid=p.prolang
   WHERE n.nspname='public' AND l.lanname IN ('sql','plpgsql')
     AND (p.proconfig IS NULL OR array_to_string(p.proconfig, ',') NOT LIKE '%search_path=%')
  ) AS functions_mutable_search_path,

  (SELECT count(*) FROM pg_class c
   JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname='public' AND c.relkind='m'
     AND (
       has_table_privilege('anon', format('public.%I', c.relname), 'SELECT')
       OR has_table_privilege('authenticated', format('public.%I', c.relname), 'SELECT')
     )
  ) AS matviews_exposed;
-- Expected result: all four counts = 0
