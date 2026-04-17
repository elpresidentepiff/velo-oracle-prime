# Feature Mart Architecture

## Overview

The VÉLØ feature mart provides **deterministic, reproducible features** for machine learning and backtesting. All features are keyed by `as_of_date` to ensure that queries on the same date always return the same results, regardless of when the query is executed.

## Determinism Guarantee

### Core Principle

**Every aggregate must be computed "as-of" a reference date** (batch import_date), not "as-of NOW()".

**Pattern:** Compute stats using **[as_of_date - window, as_of_date)** time range.

### Why This Matters

- **Backtesting:** Same race analyzed on different days must return identical features
- **Regression Testing:** Model results must be reproducible for debugging
- **Audit Trails:** Historical predictions must be verifiable
- **Fair Evaluation:** Model performance metrics must be stable

### What Changed

#### Before (Non-Deterministic) ❌
```sql
-- Materialized view with NOW() - different results each day!
CREATE MATERIALIZED VIEW trainer_stats_30d AS
SELECT 
  trainer,
  COUNT(*) as starts,
  AVG(CASE WHEN position = 1 THEN 1.0 ELSE 0.0 END) as win_pct
FROM races
WHERE race_date >= NOW() - INTERVAL '30 days'  -- ⚠️ Changes every day!
GROUP BY trainer;
```

#### After (Deterministic) ✅
```sql
-- Table keyed by as_of_date - same date, same results!
CREATE TABLE trainer_stats_window (
  as_of_date DATE NOT NULL,
  window_days INTEGER NOT NULL,
  trainer TEXT NOT NULL,
  starts INTEGER NOT NULL,
  win_pct NUMERIC(6,4),
  UNIQUE(as_of_date, window_days, trainer)
);

-- Computed using explicit date range
SELECT * FROM trainer_stats_window 
WHERE as_of_date = '2026-01-07'  -- ✅ Always returns same data
  AND window_days = 30;
```

## Feature Tables

### 1. Trainer Stats Window

**Table:** `trainer_stats_window`

Trainer performance statistics over multiple lookback windows.

**Columns:**
- `as_of_date` (DATE): Reference date for feature computation
- `window_days` (INTEGER): Lookback window (14, 30, or 90 days)
- `trainer` (TEXT): Trainer name
- `starts` (INTEGER): Number of starts in window
- `wins` (INTEGER): Number of wins in window
- `places` (INTEGER): Number of top-3 finishes in window
- `win_pct` (NUMERIC): Win percentage
- `place_pct` (NUMERIC): Top-3 percentage
- `avg_odds` (NUMERIC): Average odds
- `last_run_date` (DATE): Most recent race date

**Windows:** 14d, 30d, 90d

### 2. Jockey Stats Window

**Table:** `jockey_stats_window`

Jockey performance statistics over multiple lookback windows.

**Columns:** Same as trainer stats, with `jockey` instead of `trainer`

**Windows:** 14d, 30d, 90d

### 3. Jockey-Trainer Combo Stats Window

**Table:** `jt_combo_stats_window`

Performance of jockey-trainer partnerships.

**Columns:**
- `as_of_date` (DATE): Reference date
- `window_days` (INTEGER): Lookback window (365 days)
- `jockey` (TEXT): Jockey name
- `trainer` (TEXT): Trainer name
- `starts` (INTEGER): Combo starts
- `wins` (INTEGER): Combo wins
- `places` (INTEGER): Combo top-3 finishes
- `win_pct` (NUMERIC): Win percentage
- `place_pct` (NUMERIC): Top-3 percentage
- `avg_odds` (NUMERIC): Average odds

**Windows:** 365d

**Minimum:** 3 starts required for combo stats

### 4. Course/Distance Stats Window

**Table:** `course_distance_stats_window`

Course and distance band statistics for market context.

**Columns:**
- `as_of_date` (DATE): Reference date
- `window_days` (INTEGER): Lookback window (1095 days = ~3 years)
- `course` (TEXT): Course name
- `distance_band` (TEXT): Distance bucket (< 1200m, 1200-1600m, etc.)
- `surface` (TEXT): Race type (Flat, Jump, etc.)
- `races` (INTEGER): Number of races
- `avg_winning_odds` (NUMERIC): Average odds of winners
- `odds_volatility` (NUMERIC): Standard deviation of winning odds

**Windows:** 1095d (~36 months)

**Distance Bands:**
- `< 1200m`
- `1200-1600m`
- `1600-2000m`
- `2000-2400m`
- `2400m+`
- `Unknown`

## Build Schedule

Features are built automatically in two scenarios:

### 1. On Batch Validation (Automatic)

When a batch is validated via `POST /imports/{batch_id}/validate`:

```python
# Validation endpoint automatically triggers feature build
if validation_passed:
    as_of_date = batch.import_date
    await db.build_feature_mart(as_of_date)
```

### 2. On Demand (Manual)

You can manually trigger feature building for any date:

```sql
SELECT build_feature_mart('2026-01-07'::DATE);
```

## Query Pattern

### Python API

```python
from app.engine.features import get_features_for_racecard

# Always specify as_of_date for determinism
df = await get_features_for_racecard(
    db, 
    race_id='550e8400-e29b-41d4-a716-446655440000',
    as_of_date='2026-01-07'
)

# Or let it default to race import_date
df = await get_features_for_racecard(db, race_id)
```

### Direct SQL

```sql
-- Get features for a race as of 2026-01-07
SELECT
    r.horse_name,
    t30.win_pct as trainer_win_pct_30d,
    j30.win_pct as jockey_win_pct_30d,
    jt.win_pct as jt_combo_win_pct_365d
FROM runners r
JOIN races ra ON r.race_id = ra.id
LEFT JOIN trainer_stats_window t30 
    ON r.trainer = t30.trainer 
    AND t30.as_of_date = '2026-01-07'
    AND t30.window_days = 30
LEFT JOIN jockey_stats_window j30 
    ON r.jockey = j30.jockey 
    AND j30.as_of_date = '2026-01-07'
    AND j30.window_days = 30
LEFT JOIN jt_combo_stats_window jt 
    ON r.jockey = jt.jockey 
    AND r.trainer = jt.trainer 
    AND jt.as_of_date = '2026-01-07'
    AND jt.window_days = 365
WHERE ra.id = '550e8400-e29b-41d4-a716-446655440000';
```

## Rebuild Procedures

### Rebuild Single Date

```sql
SELECT build_feature_mart('2026-01-07'::DATE);
```

### Rebuild Date Range

```sql
DO $$
DECLARE
  d DATE;
BEGIN
  FOR d IN SELECT DISTINCT import_date 
           FROM races 
           WHERE import_date >= '2024-01-01'
           ORDER BY import_date
  LOOP
    PERFORM build_feature_mart(d);
    RAISE NOTICE 'Built features for %', d;
  END LOOP;
END $$;
```

### Rebuild All Historical Data

```sql
DO $$
DECLARE
  d DATE;
BEGIN
  FOR d IN SELECT DISTINCT import_date 
           FROM races 
           ORDER BY import_date
  LOOP
    PERFORM build_feature_mart(d);
    COMMIT;  -- Commit after each date to avoid long transactions
  END LOOP;
END $$;
```

## Performance Characteristics

### Build Performance

- **Single as_of_date:** < 30 seconds (target)
- **Features per runner:** 30+ columns
- **Windows computed:** 14d, 30d, 90d, 365d, 1095d

### Query Performance

- **Racecard feature join (15 runners):** < 1 second (target)
- **Indexes:** Covering indexes on (as_of_date, window_days, entity_id)
- **JOIN strategy:** LEFT JOIN to handle missing history gracefully

## Data Quality

### Missing History Handling

When a trainer/jockey has no history in the lookback window:
- Numeric stats default to `0` (not NULL)
- Ensures consistent feature schema
- Models can handle zero-history cases

### Minimum Thresholds

- **Trainer/Jockey stats:** No minimum (all data included)
- **JT combo stats:** Minimum 3 starts
- **Course/distance stats:** Minimum 5 races

## Monitoring

### Feature Freshness

Check when features were last built:

```sql
SELECT 
  as_of_date,
  COUNT(*) as records,
  MAX(created_at) as built_at
FROM trainer_stats_window
WHERE window_days = 30
GROUP BY as_of_date
ORDER BY as_of_date DESC
LIMIT 10;
```

### Coverage Check

Verify all batches have features built:

```sql
SELECT 
  b.import_date,
  b.status,
  COUNT(DISTINCT t.trainer) as trainers_with_stats
FROM import_batches b
LEFT JOIN trainer_stats_window t 
  ON b.import_date = t.as_of_date 
  AND t.window_days = 30
WHERE b.status = 'validated'
GROUP BY b.import_date, b.status
HAVING COUNT(DISTINCT t.trainer) = 0
ORDER BY b.import_date DESC;
```

## Troubleshooting

### Features Not Building

**Symptom:** `features_built: false` in validation response

**Check:**
1. Is the batch status `validated`?
2. Does the database user have execute permission on `build_feature_mart`?
3. Are there errors in the PostgreSQL logs?

```sql
-- Check function exists
SELECT proname FROM pg_proc WHERE proname = 'build_feature_mart';

-- Test manually
SELECT build_feature_mart('2026-01-07'::DATE);
```

### Empty Feature Results

**Symptom:** All feature columns are 0

**Possible Causes:**
1. No historical data in the lookback window
2. Batch statuses not set to `validated` or `ready`
3. Runner names don't match (case sensitivity)

```sql
-- Check historical data availability
SELECT 
  COUNT(*) as race_count,
  MIN(import_date) as earliest,
  MAX(import_date) as latest
FROM races
WHERE import_date < '2026-01-07'
  AND import_date >= '2026-01-07'::DATE - INTERVAL '30 days';
```

### Performance Issues

**Symptom:** Feature builds take > 30 seconds

**Solutions:**
1. Check index usage: `EXPLAIN ANALYZE SELECT build_feature_mart(...)`
2. Verify indexes exist: `\di` in psql
3. Consider partitioning if data volume is very high

## Migration Guide

The migration `005_deterministic_feature_mart.sql` includes:

1. **DROP** old materialized views (if they existed)
2. **CREATE** new feature tables with as_of_date keys
3. **CREATE** indexes for performance
4. **CREATE** build_feature_mart function

To apply:

```bash
# Via Supabase CLI
supabase db push

# Or manually via psql
psql -h <host> -U postgres -d postgres -f supabase/migrations/005_deterministic_feature_mart.sql
```

## Best Practices

### Always Use as_of_date

```python
# ✅ GOOD: Explicit as_of_date
df = await get_features_for_racecard(db, race_id, as_of_date='2026-01-07')

# ⚠️ OK: Defaults to race import_date (still deterministic)
df = await get_features_for_racecard(db, race_id)

# ❌ BAD: Don't query based on NOW()
# (Feature tables don't support this pattern)
```

### Batch Feature Builds

Build features in batch validation, not on-demand:

```python
# ✅ GOOD: Build during validation
@app.post("/imports/{batch_id}/validate")
async def validate_batch(batch_id: str):
    # ... validation logic ...
    if validation_passed:
        await db.build_feature_mart(batch.import_date)
    
# ❌ BAD: Build on every prediction request
# (Too slow, use pre-built features)
```

### Testing Determinism

Always include determinism tests in your CI:

```python
@pytest.mark.asyncio
async def test_determinism():
    df1 = await get_features_for_racecard(db, race_id, '2026-01-07')
    df2 = await get_features_for_racecard(db, race_id, '2026-01-07')
    pd.testing.assert_frame_equal(df1, df2)
```

## Acceptance Criteria

- ✅ No `NOW()` or `CURRENT_DATE` in feature definitions (except build timestamp audit)
- ✅ All feature tables keyed by `(as_of_date, window_days, entity_id)`
- ✅ `build_feature_mart(as_of_date)` function works
- ✅ Determinism test passes: same as_of_date → same features
- ✅ Indexes optimized for `<1s` racecard feature join
- ✅ Documentation includes refresh schedule and rebuild procedure
- ✅ Integration with batch validation endpoint

## Version History

- **v1.0** (2026-01-09): Initial deterministic feature mart implementation
  - Replaced NOW()-based materialized views with as_of_date tables
  - Added trainer, jockey, JT combo, and course/distance stats
  - Integrated with batch validation endpoint
