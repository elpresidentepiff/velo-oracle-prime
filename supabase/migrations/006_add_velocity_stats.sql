-- VÉLØ Velocity Stats Migration
-- Migration: 006_add_velocity_stats
-- Created: 2026-01-10
-- Purpose: Add velocity statistics tables for trainer, jockey, and horse performance tracking

-- ============================================================================
-- TABLE: trainer_velocity
-- Trainer statistics from external Racing Post data
-- ============================================================================

CREATE TABLE IF NOT EXISTS trainer_velocity (
    trainer_name TEXT PRIMARY KEY,
    last_14d_record TEXT,
    last_14d_sr DECIMAL(5,2),
    last_14d_pl DECIMAL(10,2),
    overall_record TEXT,
    overall_sr DECIMAL(5,2),
    overall_pl DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE trainer_velocity IS 'Trainer performance statistics including strike rates and profit/loss';
COMMENT ON COLUMN trainer_velocity.last_14d_record IS 'Win-Run record for last 14 days (e.g., "5-23")';
COMMENT ON COLUMN trainer_velocity.last_14d_sr IS 'Strike rate percentage for last 14 days';
COMMENT ON COLUMN trainer_velocity.last_14d_pl IS 'Profit/Loss for last 14 days (£1 level stake)';
COMMENT ON COLUMN trainer_velocity.overall_record IS 'Overall win-run record (e.g., "123-567")';
COMMENT ON COLUMN trainer_velocity.overall_sr IS 'Overall strike rate percentage';
COMMENT ON COLUMN trainer_velocity.overall_pl IS 'Overall profit/loss (£1 level stake)';

CREATE INDEX idx_trainer_velocity_last_14d_sr ON trainer_velocity(last_14d_sr DESC);
CREATE INDEX idx_trainer_velocity_overall_sr ON trainer_velocity(overall_sr DESC);

-- ============================================================================
-- TABLE: jockey_velocity
-- Jockey statistics from external Racing Post data
-- ============================================================================

CREATE TABLE IF NOT EXISTS jockey_velocity (
    jockey_name TEXT PRIMARY KEY,
    last_14d_record TEXT,
    last_14d_sr DECIMAL(5,2),
    last_14d_pl DECIMAL(10,2),
    overall_record TEXT,
    overall_sr DECIMAL(5,2),
    overall_pl DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE jockey_velocity IS 'Jockey performance statistics including strike rates and profit/loss';
COMMENT ON COLUMN jockey_velocity.last_14d_record IS 'Win-Run record for last 14 days (e.g., "5-23")';
COMMENT ON COLUMN jockey_velocity.last_14d_sr IS 'Strike rate percentage for last 14 days';
COMMENT ON COLUMN jockey_velocity.last_14d_pl IS 'Profit/Loss for last 14 days (£1 level stake)';
COMMENT ON COLUMN jockey_velocity.overall_record IS 'Overall win-run record (e.g., "123-567")';
COMMENT ON COLUMN jockey_velocity.overall_sr IS 'Overall strike rate percentage';
COMMENT ON COLUMN jockey_velocity.overall_pl IS 'Overall profit/loss (£1 level stake)';

CREATE INDEX idx_jockey_velocity_last_14d_sr ON jockey_velocity(last_14d_sr DESC);
CREATE INDEX idx_jockey_velocity_overall_sr ON jockey_velocity(overall_sr DESC);

-- ============================================================================
-- TABLE: horse_velocity
-- Horse course/distance/going statistics
-- ============================================================================

CREATE TABLE IF NOT EXISTS horse_velocity (
    horse_name TEXT NOT NULL,
    stat_type TEXT NOT NULL,
    record TEXT,
    sr DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (horse_name, stat_type)
);

COMMENT ON TABLE horse_velocity IS 'Horse performance by course, distance, and going conditions';
COMMENT ON COLUMN horse_velocity.stat_type IS 'Type of statistic: course_X, distance_Xf, going_X (e.g., "course_kempton", "distance_2m", "going_soft")';
COMMENT ON COLUMN horse_velocity.record IS 'Win-Run record (e.g., "2-5")';
COMMENT ON COLUMN horse_velocity.sr IS 'Strike rate percentage';

CREATE INDEX idx_horse_velocity_horse_name ON horse_velocity(horse_name);
CREATE INDEX idx_horse_velocity_stat_type ON horse_velocity(stat_type);
CREATE INDEX idx_horse_velocity_sr ON horse_velocity(sr DESC);

-- ============================================================================
-- TABLE: agent_executions
-- Audit trail for individual agent executions
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    race_id TEXT NOT NULL,
    horse_name TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    score DECIMAL(5,2),
    confidence DECIMAL(4,3),
    evidence JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE agent_executions IS 'Audit trail of individual agent executions for transparency';
COMMENT ON COLUMN agent_executions.race_id IS 'Race identifier (e.g., "WOL_20260109_1625")';
COMMENT ON COLUMN agent_executions.horse_name IS 'Horse name';
COMMENT ON COLUMN agent_executions.agent_name IS 'Agent name (e.g., "form_analyzer", "connections_analyzer")';
COMMENT ON COLUMN agent_executions.score IS 'Agent score (0-100)';
COMMENT ON COLUMN agent_executions.confidence IS 'Confidence level (0-1)';
COMMENT ON COLUMN agent_executions.evidence IS 'JSON evidence/reasoning from the agent';

CREATE INDEX idx_agent_executions_race_id ON agent_executions(race_id);
CREATE INDEX idx_agent_executions_horse_name ON agent_executions(horse_name);
CREATE INDEX idx_agent_executions_agent_name ON agent_executions(agent_name);
CREATE INDEX idx_agent_executions_created_at ON agent_executions(created_at DESC);

-- ============================================================================
-- TABLE: race_verdicts
-- Final orchestrator verdicts for betting decisions
-- ============================================================================

CREATE TABLE IF NOT EXISTS race_verdicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    race_id TEXT NOT NULL,
    horse_name TEXT NOT NULL,
    final_score DECIMAL(5,2),
    action TEXT NOT NULL,
    stake_pct DECIMAL(4,2),
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE race_verdicts IS 'Final betting verdicts from the orchestrator';
COMMENT ON COLUMN race_verdicts.race_id IS 'Race identifier (e.g., "WOL_20260109_1625")';
COMMENT ON COLUMN race_verdicts.horse_name IS 'Horse name';
COMMENT ON COLUMN race_verdicts.final_score IS 'Final weighted score (0-100)';
COMMENT ON COLUMN race_verdicts.action IS 'Betting action: BACK, LAY, or PASS';
COMMENT ON COLUMN race_verdicts.stake_pct IS 'Stake percentage of bankroll (e.g., 2.0 for 2%)';
COMMENT ON COLUMN race_verdicts.reason IS 'Human-readable reason for the decision';

CREATE INDEX idx_race_verdicts_race_id ON race_verdicts(race_id);
CREATE INDEX idx_race_verdicts_horse_name ON race_verdicts(horse_name);
CREATE INDEX idx_race_verdicts_action ON race_verdicts(action);
CREATE INDEX idx_race_verdicts_created_at ON race_verdicts(created_at DESC);

-- ============================================================================
-- AUTO-UPDATE TRIGGERS
-- ============================================================================

CREATE TRIGGER update_trainer_velocity_updated_at
    BEFORE UPDATE ON trainer_velocity
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jockey_velocity_updated_at
    BEFORE UPDATE ON jockey_velocity
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_horse_velocity_updated_at
    BEFORE UPDATE ON horse_velocity
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

ALTER TABLE trainer_velocity ENABLE ROW LEVEL SECURITY;
ALTER TABLE jockey_velocity ENABLE ROW LEVEL SECURITY;
ALTER TABLE horse_velocity ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE race_verdicts ENABLE ROW LEVEL SECURITY;

-- Allow public read access (authenticated users can query)
CREATE POLICY "Allow read access to trainer_velocity" ON trainer_velocity
    FOR SELECT USING (true);

CREATE POLICY "Allow read access to jockey_velocity" ON jockey_velocity
    FOR SELECT USING (true);

CREATE POLICY "Allow read access to horse_velocity" ON horse_velocity
    FOR SELECT USING (true);

CREATE POLICY "Allow read access to agent_executions" ON agent_executions
    FOR SELECT USING (true);

CREATE POLICY "Allow read access to race_verdicts" ON race_verdicts
    FOR SELECT USING (true);

-- Only service role can write (via backend)
CREATE POLICY "Service role can write to trainer_velocity" ON trainer_velocity
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can write to jockey_velocity" ON jockey_velocity
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can write to horse_velocity" ON horse_velocity
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can write to agent_executions" ON agent_executions
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can write to race_verdicts" ON race_verdicts
    FOR ALL USING (auth.role() = 'service_role');
