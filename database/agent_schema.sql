-- LangGraph Agent Orchestration Database Schema
-- Migration: Add engine_runs and learning_events tables
-- Version: 1.0.0
-- Date: 2026-01-08

-- ============================================================================
-- ENGINE RUNS TABLE
-- ============================================================================

-- Engine execution records
CREATE TABLE IF NOT EXISTS engine_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  race_id VARCHAR(255) NOT NULL,
  predictions JSONB NOT NULL,
  confidence FLOAT,
  execution_time_ms INT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for engine_runs
CREATE INDEX IF NOT EXISTS idx_engine_runs_race_id ON engine_runs(race_id);
CREATE INDEX IF NOT EXISTS idx_engine_runs_created_at ON engine_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_engine_runs_confidence ON engine_runs(confidence);

-- Comments
COMMENT ON TABLE engine_runs IS 'Stores engine execution results for race predictions';
COMMENT ON COLUMN engine_runs.id IS 'Unique identifier for this engine run';
COMMENT ON COLUMN engine_runs.race_id IS 'Reference to the race that was analyzed';
COMMENT ON COLUMN engine_runs.predictions IS 'JSON object with predictions per runner';
COMMENT ON COLUMN engine_runs.confidence IS 'Overall confidence score (0.0 to 1.0)';
COMMENT ON COLUMN engine_runs.execution_time_ms IS 'Execution time in milliseconds';
COMMENT ON COLUMN engine_runs.created_at IS 'Timestamp when the run was created';

-- ============================================================================
-- LEARNING EVENTS TABLE
-- ============================================================================

-- Learning feedback loop
CREATE TABLE IF NOT EXISTS learning_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID REFERENCES engine_runs(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,  -- 'prediction_accuracy', 'data_quality', 'anomaly'
  feedback JSONB NOT NULL,
  severity TEXT,  -- 'info', 'warning', 'error'
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for learning_events
CREATE INDEX IF NOT EXISTS idx_learning_events_run_id ON learning_events(run_id);
CREATE INDEX IF NOT EXISTS idx_learning_events_event_type ON learning_events(event_type);
CREATE INDEX IF NOT EXISTS idx_learning_events_severity ON learning_events(severity);
CREATE INDEX IF NOT EXISTS idx_learning_events_created_at ON learning_events(created_at);

-- Comments
COMMENT ON TABLE learning_events IS 'Stores learning events for agent feedback loop';
COMMENT ON COLUMN learning_events.id IS 'Unique identifier for this event';
COMMENT ON COLUMN learning_events.run_id IS 'Reference to the engine run that generated this event';
COMMENT ON COLUMN learning_events.event_type IS 'Type of event: prediction_accuracy, data_quality, anomaly';
COMMENT ON COLUMN learning_events.feedback IS 'JSON object with event details and metrics';
COMMENT ON COLUMN learning_events.severity IS 'Severity level: info, warning, error';
COMMENT ON COLUMN learning_events.created_at IS 'Timestamp when the event was created';

-- ============================================================================
-- SAMPLE QUERIES
-- ============================================================================

-- Get recent engine runs with their learning events
-- SELECT 
--   er.id as run_id,
--   er.race_id,
--   er.confidence,
--   er.execution_time_ms,
--   er.created_at as run_time,
--   le.event_type,
--   le.severity,
--   le.feedback
-- FROM engine_runs er
-- LEFT JOIN learning_events le ON le.run_id = er.id
-- ORDER BY er.created_at DESC
-- LIMIT 100;

-- Get statistics by event type
-- SELECT 
--   event_type,
--   severity,
--   COUNT(*) as count,
--   AVG((feedback->>'confidence')::float) as avg_confidence
-- FROM learning_events
-- WHERE created_at > NOW() - INTERVAL '7 days'
-- GROUP BY event_type, severity
-- ORDER BY event_type, severity;

-- Find anomalies
-- SELECT 
--   er.race_id,
--   er.confidence,
--   le.feedback
-- FROM engine_runs er
-- JOIN learning_events le ON le.run_id = er.id
-- WHERE le.event_type = 'anomaly'
-- AND le.severity IN ('warning', 'error')
-- ORDER BY er.created_at DESC
-- LIMIT 50;
