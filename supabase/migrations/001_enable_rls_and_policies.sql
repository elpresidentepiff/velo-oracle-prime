-- VELO v12 Row Level Security (RLS) and Policies
-- This migration enables RLS on all tables and creates appropriate policies

-- ============================================================================
-- ENABLE ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE races ENABLE ROW LEVEL SECURITY;
ALTER TABLE runners ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE engine_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE verdicts ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_events ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- POLICIES FOR service_role (Full Access)
-- ============================================================================

-- Races table policies
CREATE POLICY "service_role_all_races" ON races
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Runners table policies
CREATE POLICY "service_role_all_runners" ON runners
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Market snapshots table policies
CREATE POLICY "service_role_all_market_snapshots" ON market_snapshots
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Engine runs table policies
CREATE POLICY "service_role_all_engine_runs" ON engine_runs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Verdicts table policies
CREATE POLICY "service_role_all_verdicts" ON verdicts
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Learning events table policies
CREATE POLICY "service_role_all_learning_events" ON learning_events
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- POLICIES FOR anon (Read-Only for Public Data)
-- ============================================================================

-- Races: anon can read all races
CREATE POLICY "anon_read_races" ON races
    FOR SELECT
    TO anon
    USING (true);

-- Runners: anon can read all runners
CREATE POLICY "anon_read_runners" ON runners
    FOR SELECT
    TO anon
    USING (true);

-- Market snapshots: anon CANNOT read (sensitive pricing data)
-- No policy = no access

-- Engine runs: anon CANNOT read (internal engine data)
-- No policy = no access

-- Verdicts: anon CANNOT read (betting decisions)
-- No policy = no access

-- Learning events: anon CANNOT read (internal learning data)
-- No policy = no access

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify RLS is enabled
-- SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('races', 'runners', 'market_snapshots', 'engine_runs', 'verdicts', 'learning_events');

-- Verify policies exist
-- SELECT schemaname, tablename, policyname, roles, cmd FROM pg_policies WHERE tablename IN ('races', 'runners', 'market_snapshots', 'engine_runs', 'verdicts', 'learning_events');
