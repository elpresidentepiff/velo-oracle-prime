-- VÉLØ Racing Database Schema
-- Created: October 15, 2025

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

-- Summary statistics view
CREATE OR REPLACE VIEW race_summary AS
SELECT 
    date,
    course,
    COUNT(DISTINCT race_id) as num_races,
    COUNT(*) as num_runners,
    COUNT(DISTINCT horse) as unique_horses,
    COUNT(DISTINCT jockey) as unique_jockeys,
    COUNT(DISTINCT trainer) as unique_trainers
FROM racing_data
GROUP BY date, course
ORDER BY date DESC;

-- Horse performance view
CREATE OR REPLACE VIEW horse_performance AS
SELECT 
    horse,
    COUNT(*) as total_runs,
    SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN pos IN ('1','2','3') THEN 1 ELSE 0 END) as places,
    ROUND(100.0 * SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_pct,
    ROUND(100.0 * SUM(CASE WHEN pos IN ('1','2','3') THEN 1 ELSE 0 END) / COUNT(*), 2) as place_pct,
    MAX(date) as last_run
FROM racing_data
WHERE pos ~ '^[0-9]+$'
GROUP BY horse
HAVING COUNT(*) >= 3
ORDER BY wins DESC, total_runs DESC;

-- Jockey performance view
CREATE OR REPLACE VIEW jockey_performance AS
SELECT 
    jockey,
    COUNT(*) as total_rides,
    SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_pct,
    MAX(date) as last_ride
FROM racing_data
WHERE pos ~ '^[0-9]+$'
  AND jockey IS NOT NULL
  AND jockey != ''
GROUP BY jockey
HAVING COUNT(*) >= 10
ORDER BY wins DESC;

-- Trainer performance view
CREATE OR REPLACE VIEW trainer_performance AS
SELECT 
    trainer,
    COUNT(*) as total_runners,
    SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_pct,
    MAX(date) as last_runner
FROM racing_data
WHERE pos ~ '^[0-9]+$'
  AND trainer IS NOT NULL
  AND trainer != ''
GROUP BY trainer
HAVING COUNT(*) >= 10
ORDER BY wins DESC;

-- Course statistics view
CREATE OR REPLACE VIEW course_stats AS
SELECT 
    course,
    COUNT(DISTINCT race_id) as total_races,
    COUNT(*) as total_runners,
    MIN(date) as first_race,
    MAX(date) as last_race
FROM racing_data
GROUP BY course
ORDER BY total_races DESC;

