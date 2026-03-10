# VÉLØ Feature Warehouse - Infrastructure Plan

**Version:** 1.0  
**Date:** 2025-11-03  
**Status:** Design Phase  
**Owner:** VÉLØ Engineering

---

## Problem Statement

Current feature computation is row-by-row, requiring 4.5 minutes for 10K records. This prevents training on datasets >50K records, limiting model quality and generalization.

**Bottleneck:** Trainer/jockey velocity features require millions of SQL queries (one per horse × per window).

**Impact:** Cannot train v1.2.0 on 100K+ records needed for production-grade model.

---

## Solution: Materialized Feature Warehouse

Pre-compute all features once, store in indexed tables, join at race-time.

**Benefits:**
- Feature computation: 4.5 min → <10 seconds for 100K records
- Enables training on full 1.96M dataset
- Daily updates via SQL jobs
- Reusable across model versions

---

## Architecture

### 1. Core Feature Tables

#### `trainer_velocity`
```sql
CREATE TABLE trainer_velocity (
    trainer TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    sr_14d REAL,        -- Strike rate last 14 days (EB shrinkage)
    sr_30d REAL,        -- Strike rate last 30 days
    sr_90d REAL,        -- Strike rate last 90 days
    runs_14d INTEGER,   -- Sample size for shrinkage
    runs_30d INTEGER,
    runs_90d INTEGER,
    PRIMARY KEY (trainer, as_of_date)
);

CREATE INDEX idx_trainer_velocity_date ON trainer_velocity(as_of_date);
```

#### `jockey_velocity`
```sql
CREATE TABLE jockey_velocity (
    jockey TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    sr_14d REAL,
    sr_30d REAL,
    sr_90d REAL,
    runs_14d INTEGER,
    runs_30d INTEGER,
    runs_90d INTEGER,
    PRIMARY KEY (jockey, as_of_date)
);

CREATE INDEX idx_jockey_velocity_date ON jockey_velocity(as_of_date);
```

#### `trainer_jockey_combo`
```sql
CREATE TABLE trainer_jockey_combo (
    trainer TEXT NOT NULL,
    jockey TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    combo_sr REAL,      -- Combined strike rate
    runs INTEGER,       -- Sample size
    uplift REAL,        -- vs individual rates
    PRIMARY KEY (trainer, jockey, as_of_date)
);
```

#### `horse_form`
```sql
CREATE TABLE horse_form (
    horse TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    form_ewma REAL,         -- EWMA of finish percentile
    form_slope REAL,        -- Linear trend (improving/declining)
    form_var REAL,          -- Consistency (variance)
    ts_trend REAL,          -- Topspeed trend
    last_run_days INTEGER,  -- Days since last race
    runs_last_90d INTEGER,  -- Recent activity
    PRIMARY KEY (horse, as_of_date)
);
```

#### `course_going_bias`
```sql
CREATE TABLE course_going_bias (
    course TEXT NOT NULL,
    going TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    win_iv REAL,            -- Impact Value (win rate vs expected)
    place_iv REAL,          -- Place IV
    sample_size INTEGER,    -- Races in window
    persistence_flag INTEGER, -- Z-score > 1.5
    PRIMARY KEY (course, going, as_of_date)
);
```

#### `draw_bias`
```sql
CREATE TABLE draw_bias (
    course TEXT NOT NULL,
    distance INTEGER NOT NULL,
    going TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    draw_iv REAL,           -- Draw Impact Value
    optimal_range TEXT,     -- e.g., "1-3" for low draws
    sample_size INTEGER,
    PRIMARY KEY (course, distance, going, as_of_date)
);
```

---

### 2. Feature Computation Pipeline

#### Daily Update Job
```sql
-- Run daily at 2am
-- Compute features for yesterday's date
-- Window: last 365 days

-- Example: Trainer velocity for 2024-11-02
INSERT INTO trainer_velocity (trainer, as_of_date, sr_14d, sr_30d, sr_90d, ...)
SELECT 
    trainer,
    '2024-11-02' as as_of_date,
    -- 14-day window with EB shrinkage
    (SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) + 0.5) / (COUNT(*) + 10.0) as sr_14d,
    -- 30-day window
    ...,
    -- 90-day window
    ...
FROM racing_data
WHERE date BETWEEN '2024-10-19' AND '2024-11-02'  -- 14 days
GROUP BY trainer;
```

#### Backfill Script
```python
# Backfill historical features for training
# Run once to populate 2015-2025

for date in date_range('2015-01-01', '2025-11-03'):
    compute_trainer_velocity(date)
    compute_jockey_velocity(date)
    compute_horse_form(date)
    compute_bias_maps(date)
```

---

### 3. Feature Join at Race-Time

```sql
-- Generate features for a race
SELECT 
    r.*,
    tv.sr_14d as trainer_sr_14d,
    tv.sr_30d as trainer_sr_30d,
    tv.sr_90d as trainer_sr_90d,
    jv.sr_14d as jockey_sr_14d,
    jv.sr_30d as jockey_sr_30d,
    jv.sr_90d as jockey_sr_90d,
    tjc.uplift as tj_combo_uplift,
    hf.form_ewma,
    hf.form_slope,
    hf.form_var,
    cgb.win_iv as course_going_iv,
    db.draw_iv
FROM racing_data r
LEFT JOIN trainer_velocity tv 
    ON r.trainer = tv.trainer AND tv.as_of_date = r.date
LEFT JOIN jockey_velocity jv 
    ON r.jockey = jv.jockey AND jv.as_of_date = r.date
LEFT JOIN trainer_jockey_combo tjc
    ON r.trainer = tjc.trainer AND r.jockey = tjc.jockey AND tjc.as_of_date = r.date
LEFT JOIN horse_form hf
    ON r.horse = hf.horse AND hf.as_of_date = r.date
LEFT JOIN course_going_bias cgb
    ON r.course = cgb.course AND r.going = cgb.going AND cgb.as_of_date = r.date
LEFT JOIN draw_bias db
    ON r.course = db.course AND r.distance = db.distance 
       AND r.going = db.going AND db.as_of_date = r.date
WHERE r.date BETWEEN '2024-01-01' AND '2024-12-31';
```

**Performance:** <1 second for 100K records (indexed joins)

---

## Implementation Plan

### Phase 1: Schema & Backfill (Week 1)
- [ ] Create feature tables (SQL DDL)
- [ ] Write backfill scripts (Python + SQL)
- [ ] Backfill 2015-2025 (1.96M records)
- [ ] Validate feature distributions
- [ ] Create indexes

**Deliverable:** Populated feature warehouse

### Phase 2: Daily Update Pipeline (Week 1)
- [ ] Write daily update SQL
- [ ] Schedule cron job (2am daily)
- [ ] Test incremental updates
- [ ] Monitor data quality

**Deliverable:** Automated feature updates

### Phase 3: Training Integration (Week 2)
- [ ] Update `FeatureBuilderV12` to use warehouse
- [ ] Benchmark: 100K records in <10 seconds
- [ ] Validate feature parity with v1.1
- [ ] Train v1.2.0 on 100K+ samples

**Deliverable:** v1.2.0 model

### Phase 4: Validation (Week 2)
- [ ] Backtest v1.2.0 on full 90-day OOS
- [ ] Measure A/E by price bucket
- [ ] Calibration analysis
- [ ] Compare vs v1.1.0

**Deliverable:** v1.2.0 validation report

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Feature computation time | <10s for 100K records | Benchmark |
| Training set size | >100K records | Model metadata |
| Backfill coverage | 2015-2025 (1.96M records) | Row count |
| Daily update latency | <5 minutes | Cron log |
| Feature parity | 100% match with v1.1 | Unit tests |

---

## Risk Mitigation

### Disk Space
- **Risk:** Feature tables may be large (GB scale)
- **Mitigation:** Use Parquet for archival, SQLite for active queries
- **Monitoring:** Track DB size daily

### Data Quality
- **Risk:** Backfill errors, missing data
- **Mitigation:** Unit tests, validation queries, null checks
- **Monitoring:** Daily data quality report

### Performance
- **Risk:** Joins may be slow without proper indexes
- **Mitigation:** Index all foreign keys, use EXPLAIN QUERY PLAN
- **Monitoring:** Query performance logs

---

## Technology Stack

- **Database:** SQLite (development), PostgreSQL (production)
- **Compute:** Python 3.11 + pandas + PyArrow
- **Scheduling:** cron (daily updates)
- **Storage:** Parquet (archival), SQLite (active)
- **Version Control:** Git (schema migrations)

---

## Future Enhancements (v1.3+)

- **Sectional pace features** (requires ATR data integration)
- **Market microstructure** (requires Betfair prices_history)
- **Breeding features** (sire/dam performance)
- **Weather features** (rain, wind, temperature)
- **Track condition** (rail position, moisture content)

---

## Appendix: SQL Examples

### Empirical Bayes Shrinkage
```sql
-- Shrink towards global mean with prior strength = 10
(SUM(wins) + 0.5 * 10) / (SUM(runs) + 10)
```

### EWMA Form Curve
```sql
-- Exponential weighted moving average (decay = 0.6)
SELECT 
    horse,
    SUM(finish_pct * POWER(0.6, race_num - 1)) / SUM(POWER(0.6, race_num - 1)) as form_ewma
FROM (
    SELECT 
        horse,
        (CAST(ran AS REAL) - CAST(pos AS REAL)) / CAST(ran AS REAL) as finish_pct,
        ROW_NUMBER() OVER (PARTITION BY horse ORDER BY date DESC) as race_num
    FROM racing_data
    WHERE date < :as_of_date
)
GROUP BY horse;
```

### Impact Value (Bias Detection)
```sql
-- IV = observed_rate / expected_rate
-- Expected = global win rate
SELECT 
    course,
    going,
    (SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) / 
    (SELECT AVG(CASE WHEN pos = '1' THEN 1 ELSE 0 END) FROM racing_data) as win_iv
FROM racing_data
WHERE date BETWEEN :start_date AND :end_date
GROUP BY course, going
HAVING COUNT(*) >= 20;  -- Minimum sample size
```

---

## Status

**Current:** Design complete  
**Next:** Phase 1 implementation (schema + backfill)  
**Timeline:** 2 weeks to v1.2.0 training

---

*"You don't tune horsepower before building fuel injection."*

— VÉLØ Engineering
