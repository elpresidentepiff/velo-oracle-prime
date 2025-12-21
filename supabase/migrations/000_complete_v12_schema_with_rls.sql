-- VELO v12 Complete Schema with RLS
-- Migration: 000_complete_v12_schema_with_rls
-- Created: 2025-01-21
-- This creates all tables with RLS enabled from the start

-- ============================================================================
-- DROP EXISTING TABLES (if any)
-- ============================================================================

DROP TABLE IF EXISTS learning_events CASCADE;
DROP TABLE IF EXISTS verdicts CASCADE;
DROP TABLE IF EXISTS engine_runs CASCADE;
DROP TABLE IF EXISTS market_snapshots CASCADE;
DROP TABLE IF EXISTS runners CASCADE;
DROP TABLE IF EXISTS races CASCADE;

-- ============================================================================
-- CREATE TABLES
-- ============================================================================

-- Races table
CREATE TABLE races (
    race_id VARCHAR(100) PRIMARY KEY,
    race_date DATE NOT NULL,
    course VARCHAR(100) NOT NULL,
    race_time TIME NOT NULL,
    race_name VARCHAR(200),
    distance_yards INTEGER,
    going VARCHAR(50),
    race_class INTEGER,
    prize_money DECIMAL(12,2),
    num_runners INTEGER,
    race_type VARCHAR(50),
    age_band VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Runners table
CREATE TABLE runners (
    runner_id VARCHAR(100) PRIMARY KEY,
    race_id VARCHAR(100) REFERENCES races(race_id) ON DELETE CASCADE,
    horse_name VARCHAR(200) NOT NULL,
    draw INTEGER,
    age INTEGER,
    weight_lbs INTEGER,
    jockey_name VARCHAR(200),
    trainer_name VARCHAR(200),
    owner_name VARCHAR(200),
    sire_name VARCHAR(200),
    dam_name VARCHAR(200),
    form_string VARCHAR(100),
    days_since_last_run INTEGER,
    official_rating INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Market snapshots table
CREATE TABLE market_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    race_id VARCHAR(100) REFERENCES races(race_id) ON DELETE CASCADE,
    runner_id VARCHAR(100) REFERENCES runners(runner_id) ON DELETE CASCADE,
    snapshot_time TIMESTAMP NOT NULL,
    back_price DECIMAL(10,2),
    lay_price DECIMAL(10,2),
    back_volume DECIMAL(15,2),
    lay_volume DECIMAL(15,2),
    total_matched DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Engine runs table
CREATE TABLE engine_runs (
    run_id VARCHAR(100) PRIMARY KEY,
    race_id VARCHAR(100) REFERENCES races(race_id) ON DELETE CASCADE,
    mode VARCHAR(50) NOT NULL,
    decision_timestamp TIMESTAMP NOT NULL,
    input_hash VARCHAR(64),
    data_version VARCHAR(20),
    chaos_score DECIMAL(5,3),
    mof_state VARCHAR(50),
    icm_hard_constraints INTEGER,
    entropy DECIMAL(5,3),
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Verdicts table
CREATE TABLE verdicts (
    verdict_id SERIAL PRIMARY KEY,
    run_id VARCHAR(100) REFERENCES engine_runs(run_id) ON DELETE CASCADE,
    race_id VARCHAR(100) REFERENCES races(race_id) ON DELETE CASCADE,
    top4_chassis JSONB,
    win_candidate VARCHAR(100),
    win_overlay DECIMAL(10,4),
    stake_cap DECIMAL(10,2),
    stake_used DECIMAL(10,2),
    kill_list_triggers TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

-- Learning events table
CREATE TABLE learning_events (
    event_id SERIAL PRIMARY KEY,
    run_id VARCHAR(100) REFERENCES engine_runs(run_id) ON DELETE CASCADE,
    race_id VARCHAR(100) REFERENCES races(race_id) ON DELETE CASCADE,
    gate_passed BOOLEAN NOT NULL,
    signal_convergence DECIMAL(5,3),
    manipulation_state VARCHAR(50),
    ablation_robust BOOLEAN,
    outcome_verified BOOLEAN,
    post_race_critique JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- CREATE INDEXES
-- ============================================================================

CREATE INDEX idx_races_date ON races(race_date);
CREATE INDEX idx_races_course ON races(course);
CREATE INDEX idx_runners_race_id ON runners(race_id);
CREATE INDEX idx_runners_horse ON runners(horse_name);
CREATE INDEX idx_market_snapshots_race_id ON market_snapshots(race_id);
CREATE INDEX idx_market_snapshots_runner_id ON market_snapshots(runner_id);
CREATE INDEX idx_market_snapshots_time ON market_snapshots(snapshot_time);
CREATE INDEX idx_engine_runs_race_id ON engine_runs(race_id);
CREATE INDEX idx_engine_runs_timestamp ON engine_runs(decision_timestamp);
CREATE INDEX idx_verdicts_run_id ON verdicts(run_id);
CREATE INDEX idx_verdicts_race_id ON verdicts(race_id);
CREATE INDEX idx_learning_events_run_id ON learning_events(run_id);
CREATE INDEX idx_learning_events_race_id ON learning_events(race_id);

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
-- CREATE POLICIES
-- ============================================================================

-- service_role: Full access to all tables
CREATE POLICY "service_role_all_races" ON races FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_runners" ON runners FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_market_snapshots" ON market_snapshots FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_engine_runs" ON engine_runs FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_verdicts" ON verdicts FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_learning_events" ON learning_events FOR ALL TO service_role USING (true) WITH CHECK (true);

-- anon: Read-only access to races and runners (public data)
CREATE POLICY "anon_read_races" ON races FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read_runners" ON runners FOR SELECT TO anon USING (true);

-- anon: NO access to market_snapshots, engine_runs, verdicts, learning_events (sensitive data)
-- No policies = no access

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Check RLS status
SELECT 
    tablename, 
    CASE WHEN rowsecurity THEN 'ENABLED' ELSE 'DISABLED' END as rls_status
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('races', 'runners', 'market_snapshots', 'engine_runs', 'verdicts', 'learning_events')
ORDER BY tablename;

-- Check policies
SELECT 
    tablename,
    policyname,
    ARRAY_AGG(roles::text) as roles,
    cmd as command
FROM pg_policies 
WHERE tablename IN ('races', 'runners', 'market_snapshots', 'engine_runs', 'verdicts', 'learning_events')
GROUP BY tablename, policyname, cmd
ORDER BY tablename, policyname;
