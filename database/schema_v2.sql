-- VÉLØ Oracle 2.0 - Enhanced Database Schema
-- Created: October 18, 2025
-- This extends the original schema with tables for ML, predictions, and API data

-- ============================================================================
-- CORE RACING DATA (from existing schema.sql)
-- ============================================================================

-- Main racing data table (from Kaggle datasets)
CREATE TABLE IF NOT EXISTS racing_data (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    course VARCHAR(100),
    race_id VARCHAR(50),
    off_time VARCHAR(10),
    race_name TEXT,
    type VARCHAR(20),  -- Flat, Chase, Hurdle
    class VARCHAR(20),
    pattern VARCHAR(50),
    rating_band VARCHAR(30),
    age_band VARCHAR(30),
    sex_rest VARCHAR(30),
    dist VARCHAR(20),
    going VARCHAR(50),
    ran INTEGER,
    num DECIMAL(5,1),
    pos VARCHAR(10),
    draw INTEGER,
    ovr_btn DECIMAL(10,2),
    btn DECIMAL(10,2),
    horse VARCHAR(150),
    age INTEGER,
    sex CHAR(1),
    wgt VARCHAR(20),
    hg VARCHAR(10),
    time VARCHAR(20),
    sp VARCHAR(30),
    jockey VARCHAR(150),
    trainer VARCHAR(150),
    prize VARCHAR(50),
    official_rating VARCHAR(10),
    rpr VARCHAR(10),
    ts VARCHAR(10),
    sire VARCHAR(150),
    dam VARCHAR(150),
    damsire VARCHAR(150),
    owner TEXT,
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_date ON racing_data(date);
CREATE INDEX IF NOT EXISTS idx_course ON racing_data(course);
CREATE INDEX IF NOT EXISTS idx_race_id ON racing_data(race_id);
CREATE INDEX IF NOT EXISTS idx_horse ON racing_data(horse);
CREATE INDEX IF NOT EXISTS idx_jockey ON racing_data(jockey);
CREATE INDEX IF NOT EXISTS idx_trainer ON racing_data(trainer);
CREATE INDEX IF NOT EXISTS idx_type ON racing_data(type);
CREATE INDEX IF NOT EXISTS idx_date_course ON racing_data(date, course);

-- Sectional data table (from ATR)
CREATE TABLE IF NOT EXISTS sectional_data (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(50),
    horse VARCHAR(150),
    date DATE,
    course VARCHAR(100),
    
    -- Furlong times
    f1 DECIMAL(5,2), f2 DECIMAL(5,2), f3 DECIMAL(5,2),
    f4 DECIMAL(5,2), f5 DECIMAL(5,2), f6 DECIMAL(5,2),
    f7 DECIMAL(5,2), f8 DECIMAL(5,2), f9 DECIMAL(5,2),
    f10 DECIMAL(5,2), f11 DECIMAL(5,2), f12 DECIMAL(5,2),
    f13 DECIMAL(5,2), f14 DECIMAL(5,2), f15 DECIMAL(5,2),
    f16 DECIMAL(5,2),
    
    -- Calculated metrics
    finishing_speed_pct DECIMAL(5,2),
    efficiency_grade CHAR(1),
    early_speed_mph DECIMAL(5,2),
    mid_speed_mph DECIMAL(5,2),
    late_speed_mph DECIMAL(5,2),
    
    -- Race context
    total_time DECIMAL(6,2),
    race_finishing_speed_pct DECIMAL(5,2),
    pace_scenario VARCHAR(20),
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sect_race_id ON sectional_data(race_id);
CREATE INDEX IF NOT EXISTS idx_sect_horse ON sectional_data(horse);
CREATE INDEX IF NOT EXISTS idx_sect_date ON sectional_data(date);

-- Racecards table (from rpscrape daily)
CREATE TABLE IF NOT EXISTS racecards (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(50),
    date DATE NOT NULL,
    course VARCHAR(100),
    off_time VARCHAR(10),
    race_name TEXT,
    distance VARCHAR(20),
    going VARCHAR(50),
    horse VARCHAR(150),
    jockey VARCHAR(150),
    trainer VARCHAR(150),
    weight VARCHAR(20),
    draw INTEGER,
    age INTEGER,
    official_rating INTEGER,
    last_run_date DATE,
    form VARCHAR(50),
    odds DECIMAL(10,2),
    scraped_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rc_date ON racecards(date);
CREATE INDEX IF NOT EXISTS idx_rc_course ON racecards(course);
CREATE INDEX IF NOT EXISTS idx_rc_horse ON racecards(horse);

-- ============================================================================
-- ORACLE 2.0 - BETFAIR MARKET DATA
-- ============================================================================

-- Betfair market snapshots
CREATE TABLE IF NOT EXISTS betfair_markets (
    id SERIAL PRIMARY KEY,
    market_id VARCHAR(50) UNIQUE NOT NULL,
    event_name VARCHAR(200),
    course VARCHAR(100),
    race_time TIMESTAMP,
    country_code VARCHAR(5),
    market_type VARCHAR(20),
    total_matched DECIMAL(15,2),
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bf_market_id ON betfair_markets(market_id);
CREATE INDEX IF NOT EXISTS idx_bf_race_time ON betfair_markets(race_time);
CREATE INDEX IF NOT EXISTS idx_bf_course ON betfair_markets(course);

-- Betfair runner odds history
CREATE TABLE IF NOT EXISTS betfair_odds (
    id SERIAL PRIMARY KEY,
    market_id VARCHAR(50) NOT NULL,
    selection_id BIGINT NOT NULL,
    runner_name VARCHAR(150),
    back_price DECIMAL(10,2),
    back_size DECIMAL(15,2),
    lay_price DECIMAL(10,2),
    lay_size DECIMAL(15,2),
    total_matched DECIMAL(15,2),
    last_price_traded DECIMAL(10,2),
    snapshot_time TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bf_odds_market ON betfair_odds(market_id);
CREATE INDEX IF NOT EXISTS idx_bf_odds_selection ON betfair_odds(selection_id);
CREATE INDEX IF NOT EXISTS idx_bf_odds_time ON betfair_odds(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_bf_odds_market_time ON betfair_odds(market_id, snapshot_time);

-- Market manipulation detection log
CREATE TABLE IF NOT EXISTS manipulation_alerts (
    id SERIAL PRIMARY KEY,
    market_id VARCHAR(50) NOT NULL,
    selection_id BIGINT NOT NULL,
    runner_name VARCHAR(150),
    manipulation_score INTEGER,
    odds_drift DECIMAL(10,2),
    volume_surge BOOLEAN,
    smart_money BOOLEAN,
    alert_type VARCHAR(50),
    message TEXT,
    detected_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_manip_market ON manipulation_alerts(market_id);
CREATE INDEX IF NOT EXISTS idx_manip_score ON manipulation_alerts(manipulation_score);
CREATE INDEX IF NOT EXISTS idx_manip_time ON manipulation_alerts(detected_at);

-- ============================================================================
-- ORACLE 2.0 - PREDICTIONS & ML
-- ============================================================================

-- ML model predictions
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(50),
    market_id VARCHAR(50),
    date DATE NOT NULL,
    course VARCHAR(100),
    race_time TIMESTAMP,
    horse VARCHAR(150),
    
    -- Model predictions
    model_version VARCHAR(20),
    win_probability DECIMAL(5,4),
    place_probability DECIMAL(5,4),
    expected_position DECIMAL(5,2),
    confidence_score DECIMAL(5,2),
    
    -- VÉLØ analysis scores
    sqpe_score DECIMAL(5,2),
    v9pm_score DECIMAL(5,2),
    tie_score DECIMAL(5,2),
    ssm_score DECIMAL(5,2),
    bop_score DECIMAL(5,2),
    manipulation_risk DECIMAL(5,2),
    value_score DECIMAL(5,2),
    
    -- Recommendation
    recommended_bet VARCHAR(20),  -- WIN, EW, PLACE, PASS
    recommended_stake DECIMAL(10,2),
    odds_at_prediction DECIMAL(10,2),
    
    -- Actual outcome (filled post-race)
    actual_position INTEGER,
    actual_sp DECIMAL(10,2),
    result VARCHAR(20),  -- WON, PLACED, LOST
    profit_loss DECIMAL(10,2),
    
    predicted_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pred_race_id ON predictions(race_id);
CREATE INDEX IF NOT EXISTS idx_pred_market_id ON predictions(market_id);
CREATE INDEX IF NOT EXISTS idx_pred_date ON predictions(date);
CREATE INDEX IF NOT EXISTS idx_pred_horse ON predictions(horse);
CREATE INDEX IF NOT EXISTS idx_pred_result ON predictions(result);

-- Model training history
CREATE TABLE IF NOT EXISTS model_versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) UNIQUE NOT NULL,
    model_type VARCHAR(50),
    features_used TEXT[],
    training_data_size INTEGER,
    validation_accuracy DECIMAL(5,4),
    test_accuracy DECIMAL(5,4),
    
    -- Performance metrics
    win_strike_rate DECIMAL(5,2),
    place_strike_rate DECIMAL(5,2),
    roi DECIMAL(10,2),
    profit_loss DECIMAL(15,2),
    total_bets INTEGER,
    
    -- Model parameters (JSON)
    hyperparameters JSONB,
    feature_importance JSONB,
    
    trained_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_model_version ON model_versions(version);
CREATE INDEX IF NOT EXISTS idx_model_active ON model_versions(is_active);

-- ============================================================================
-- ORACLE 2.0 - GENESIS PROTOCOL (LEARNING)
-- ============================================================================

-- Post-race analysis and learning
CREATE TABLE IF NOT EXISTS race_analysis (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(50),
    market_id VARCHAR(50),
    date DATE NOT NULL,
    course VARCHAR(100),
    
    -- Pre-race expectations vs reality
    favorite_expected VARCHAR(150),
    favorite_actual VARCHAR(150),
    favorite_trap BOOLEAN,
    
    -- Pattern analysis
    pace_scenario VARCHAR(50),
    pace_advantage VARCHAR(50),
    draw_bias_detected BOOLEAN,
    going_impact VARCHAR(50),
    
    -- Lessons learned
    key_insights TEXT[],
    mistakes_made TEXT[],
    patterns_confirmed TEXT[],
    patterns_rejected TEXT[],
    
    -- Performance
    predictions_correct INTEGER,
    predictions_total INTEGER,
    accuracy DECIMAL(5,2),
    profit_loss DECIMAL(10,2),
    
    analyzed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_race ON race_analysis(race_id);
CREATE INDEX IF NOT EXISTS idx_analysis_date ON race_analysis(date);
CREATE INDEX IF NOT EXISTS idx_analysis_course ON race_analysis(course);

-- Pattern library (learned patterns)
CREATE TABLE IF NOT EXISTS learned_patterns (
    id SERIAL PRIMARY KEY,
    pattern_name VARCHAR(100) UNIQUE NOT NULL,
    pattern_type VARCHAR(50),
    description TEXT,
    
    -- Pattern conditions
    conditions JSONB,
    
    -- Pattern performance
    occurrences INTEGER DEFAULT 0,
    successful_predictions INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2),
    avg_roi DECIMAL(10,2),
    confidence_level DECIMAL(5,2),
    
    -- Pattern evolution
    first_observed TIMESTAMP,
    last_observed TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pattern_name ON learned_patterns(pattern_name);
CREATE INDEX IF NOT EXISTS idx_pattern_type ON learned_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_pattern_active ON learned_patterns(is_active);

-- ============================================================================
-- ORACLE 2.0 - BETTING LEDGER
-- ============================================================================

-- Betting history and bankroll tracking
CREATE TABLE IF NOT EXISTS betting_ledger (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(50),
    market_id VARCHAR(50),
    date DATE NOT NULL,
    course VARCHAR(100),
    race_time TIMESTAMP,
    
    -- Bet details
    horse VARCHAR(150),
    bet_type VARCHAR(20),  -- WIN, EW, PLACE
    stake DECIMAL(10,2),
    odds DECIMAL(10,2),
    
    -- Outcome
    result VARCHAR(20),  -- WON, PLACED, LOST, VOID
    returns DECIMAL(10,2),
    profit_loss DECIMAL(10,2),
    
    -- Context
    bankroll_before DECIMAL(15,2),
    bankroll_after DECIMAL(15,2),
    confidence_level DECIMAL(5,2),
    reasoning TEXT,
    
    placed_at TIMESTAMP DEFAULT NOW(),
    settled_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ledger_date ON betting_ledger(date);
CREATE INDEX IF NOT EXISTS idx_ledger_horse ON betting_ledger(horse);
CREATE INDEX IF NOT EXISTS idx_ledger_result ON betting_ledger(result);
CREATE INDEX IF NOT EXISTS idx_ledger_placed ON betting_ledger(placed_at);

-- ============================================================================
-- VIEWS - PERFORMANCE ANALYTICS
-- ============================================================================

-- Overall system performance
CREATE OR REPLACE VIEW system_performance AS
SELECT 
    COUNT(*) as total_bets,
    SUM(CASE WHEN result = 'WON' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN result IN ('WON', 'PLACED') THEN 1 ELSE 0 END) as places,
    ROUND(100.0 * SUM(CASE WHEN result = 'WON' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate,
    ROUND(100.0 * SUM(CASE WHEN result IN ('WON', 'PLACED') THEN 1 ELSE 0 END) / COUNT(*), 2) as place_rate,
    SUM(stake) as total_staked,
    SUM(returns) as total_returns,
    SUM(profit_loss) as net_profit,
    ROUND(100.0 * SUM(profit_loss) / NULLIF(SUM(stake), 0), 2) as roi
FROM betting_ledger
WHERE result IS NOT NULL;

-- Daily performance
CREATE OR REPLACE VIEW daily_performance AS
SELECT 
    date,
    COUNT(*) as bets,
    SUM(CASE WHEN result = 'WON' THEN 1 ELSE 0 END) as wins,
    SUM(stake) as staked,
    SUM(returns) as returns,
    SUM(profit_loss) as profit_loss,
    ROUND(100.0 * SUM(profit_loss) / NULLIF(SUM(stake), 0), 2) as roi
FROM betting_ledger
WHERE result IS NOT NULL
GROUP BY date
ORDER BY date DESC;

-- Model comparison
CREATE OR REPLACE VIEW model_comparison AS
SELECT 
    model_version,
    COUNT(*) as predictions_made,
    SUM(CASE WHEN result = 'WON' THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN result = 'WON' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate,
    AVG(confidence_score) as avg_confidence,
    SUM(profit_loss) as total_profit,
    ROUND(100.0 * SUM(profit_loss) / NULLIF(SUM(odds_at_prediction * recommended_stake), 0), 2) as roi
FROM predictions
WHERE actual_position IS NOT NULL
GROUP BY model_version
ORDER BY total_profit DESC;

-- Manipulation detection effectiveness
CREATE OR REPLACE VIEW manipulation_effectiveness AS
SELECT 
    DATE(m.detected_at) as date,
    COUNT(*) as alerts_triggered,
    AVG(m.manipulation_score) as avg_score,
    COUNT(DISTINCT m.market_id) as markets_flagged,
    SUM(CASE WHEN p.result = 'LOST' AND m.manipulation_score > 70 THEN 1 ELSE 0 END) as traps_avoided,
    SUM(CASE WHEN p.result = 'WON' AND m.manipulation_score < 30 THEN 1 ELSE 0 END) as values_captured
FROM manipulation_alerts m
LEFT JOIN predictions p ON m.market_id = p.market_id AND m.runner_name = p.horse
GROUP BY DATE(m.detected_at)
ORDER BY date DESC;

-- Course profitability
CREATE OR REPLACE VIEW course_profitability AS
SELECT 
    course,
    COUNT(*) as bets,
    SUM(CASE WHEN result = 'WON' THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN result = 'WON' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate,
    SUM(profit_loss) as total_profit,
    ROUND(100.0 * SUM(profit_loss) / NULLIF(SUM(stake), 0), 2) as roi
FROM betting_ledger
WHERE result IS NOT NULL
GROUP BY course
HAVING COUNT(*) >= 5
ORDER BY roi DESC;

-- ============================================================================
-- FUNCTIONS - UTILITY QUERIES
-- ============================================================================

-- Function to get horse recent form
CREATE OR REPLACE FUNCTION get_horse_form(horse_name VARCHAR, num_races INTEGER DEFAULT 5)
RETURNS TABLE (
    date DATE,
    course VARCHAR,
    distance VARCHAR,
    going VARCHAR,
    position VARCHAR,
    btn DECIMAL,
    jockey VARCHAR,
    odds VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        rd.date,
        rd.course,
        rd.dist,
        rd.going,
        rd.pos,
        rd.btn,
        rd.jockey,
        rd.sp
    FROM racing_data rd
    WHERE rd.horse = horse_name
    ORDER BY rd.date DESC
    LIMIT num_races;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate jockey/trainer combo stats
CREATE OR REPLACE FUNCTION get_combo_stats(jockey_name VARCHAR, trainer_name VARCHAR)
RETURNS TABLE (
    total_runs BIGINT,
    wins BIGINT,
    places BIGINT,
    win_rate DECIMAL,
    place_rate DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_runs,
        SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN pos IN ('1','2','3') THEN 1 ELSE 0 END) as places,
        ROUND(100.0 * SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate,
        ROUND(100.0 * SUM(CASE WHEN pos IN ('1','2','3') THEN 1 ELSE 0 END) / COUNT(*), 2) as place_rate
    FROM racing_data
    WHERE jockey = jockey_name
      AND trainer = trainer_name
      AND pos ~ '^[0-9]+$';
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert default model version
INSERT INTO model_versions (version, model_type, is_active)
VALUES ('v1.0-baseline', 'multinomial_logit', TRUE)
ON CONFLICT (version) DO NOTHING;

-- Insert initial learned patterns
INSERT INTO learned_patterns (pattern_name, pattern_type, description, conditions)
VALUES 
    ('favorite_drift_trap', 'manipulation', 'Favorite drifting significantly before race - potential trap', '{"min_drift": 20, "min_odds": 2.0, "max_odds": 5.0}'::jsonb),
    ('smart_money_late', 'value', 'Late money coming for outsider - smart money signal', '{"min_odds": 8.0, "time_before_race": 15, "min_volume": 10000}'::jsonb),
    ('course_specialist', 'form', 'Horse with exceptional course record', '{"min_course_runs": 3, "min_course_win_rate": 33}'::jsonb)
ON CONFLICT (pattern_name) DO NOTHING;

