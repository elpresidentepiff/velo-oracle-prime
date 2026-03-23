# VÉLØ HK Research Lane — "HK Ready" Gate
**Date:** 2026-03-23
**Purpose:** Define exactly what "ready for HK research scoring" means — before building starts

---

## The Problem With "Interesting Forever"

Without a defined gate, HK research becomes a permanent sandbox. It ingests every day, never produces anything usable, and nobody can say when it's "done." This document prevents that.

---

## The Gate — 6 Criteria That Must All Pass

Before ANY research scoring is run on HK data, ALL 6 criteria must be met:

### Gate HK-1: Racecard Completeness
```
Target: 90 consecutive days of HK racecards collected
Current: 0 days
Measure: SELECT COUNT(DISTINCT meeting_date) FROM hk_research.hk_races
Gate: ≥ 90 distinct meeting dates
Status: NOT READY
```

### Gate HK-2: Results Completeness
```
Target: 90 consecutive days of HK results with SP and finish positions
Current: 0 days
Measure: SELECT COUNT(DISTINCT meeting_date) FROM hk_research.hk_races WHERE race_id IN (SELECT DISTINCT race_id FROM hk_research.hk_results)
Gate: ≥ 90 distinct meeting dates with results
Status: NOT READY
```

### Gate HK-3: Horse History Depth
```
Target: Active HK horses have ≥ 5 historical runs in hk_horse_history
Current: 0 rows
Measure: SELECT AVG(run_count) FROM (SELECT horse_id, COUNT(*) as run_count FROM hk_research.hk_horse_history GROUP BY horse_id) sub
Gate: Average runs per horse ≥ 5 for horses seen in last 30 days
Status: NOT READY
```

### Gate HK-4: Trainer/Jockey Coverage
```
Target: ≥ 80% of trainers in last 30 days have profile in hk_trainer_stats
Current: 0 rows
Measure: Check coverage ratio
Gate: ≥ 80% coverage
Status: NOT READY
```

### Gate HK-5: Market Data Coverage
```
Target: ≥ 70% of runners have odds data in hk_market_snapshots
Current: 0 rows
Measure: SELECT COUNT(*) FROM hk_market_snapshots vs SELECT COUNT(*) FROM hk_runners WHERE meeting_date > 30d ago
Gate: ≥ 70% odds coverage
Status: NOT READY
```

### Gate HK-6: No Major Ingestion Gaps
```
Target: Zero days with >10% missing runners (vs expected field size)
Current: N/A
Measure: Check hk_ingestion_log for gaps > 3 consecutive missing days
Gate: ≤ 3 missing days in 90-day window
Status: NOT READY
```

---

## Gate Review Schedule

| Milestone | Target Date | Gate Check |
|---|---|---|
| 30 days collected | 2026-04-22 | Pre-check: HK-1, HK-2 only |
| 60 days collected | 2026-05-22 | Mid-check: All 6 |
| 90 days collected | 2026-06-21 | Full gate review |

Gate review is conducted by VOX and presented to El Presidente. HK goes to Phase 4 (research scoring) ONLY if all 6 gates pass.

---

## Research Health Metrics (Before Gate)

While accumulating data, monitor these weekly:

```sql
-- Daily ingestion health
SELECT run_date, races_fetched, runners_fetched, status
FROM hk_research.hk_ingestion_log
ORDER BY run_date DESC LIMIT 30;

-- Course distribution (should be only Happy Valley + Sha Tin)
SELECT course, COUNT(*)
FROM hk_research.hk_races
GROUP BY course;

-- Average field size (should be 10-14 for HK)
SELECT AVG(field_size) FROM hk_research.hk_races;

-- Ingestion gaps
SELECT DATE_TRUNC('day', generate_series) as missing_date
FROM generate_series('2026-03-23'::date, CURRENT_DATE, '1 day'::interval)
EXCEPT
SELECT meeting_date FROM hk_research.hk_races;
```

---

## What Happens If a Gate Fails

| Gate | If It Fails | Action |
|---|---|---|
| HK-1 Racecards | Ingestion broken or API issue | Fix ingestion before continuing |
| HK-2 Results | Results not available for that day | Investigate — HK may not publish all results |
| HK-3 Horse History | Horses not running enough | Accept — HK horses may have < 5 runs, lower threshold to 3 |
| HK-4 Trainer/Jockey | Coverage gap | Enrich via trainer/jockey analysis endpoints |
| HK-5 Market Data | Odds not captured | Fix ingestion script odds extraction |
| HK-6 Ingestion Gaps | Pipeline missed days | Investigate Railway cron, fix, backfill if possible |

---

## The Decision Point

When all 6 gates pass (estimated ~June 2026):

1. VOX runs research scoring on last 30 days of HK (backtest)
2. VOX produces: HK A-tier strike rate, miss categories, comparison to UK baseline
3. El Presidente reviews: Is HK A-tier strike ≥ 38%?
   - **YES →** Propose HK as Lane 3 in next Phase Gate review
   - **NO →** Stay in research. Identify why. Fix. Re-gate at 90 more days.

HK never moves to production without explicit El Presidente sign-off.

---

## Anti-Pattern: The Fake Ready

Watch for these signs that HK is being artificially marked ready:
- "We have some data, close enough"
- "The model should work — it worked on UK"
- "Let's just enable it and see"
- "We can backfill later"

Real readiness: all 6 gates pass on actual accumulated data.
