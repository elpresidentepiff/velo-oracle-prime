# VÉLØ HK Research Lane — Build Order
**Date:** 2026-03-23
**Purpose:** Safe, staged build of HK research spine without touching UK production

---

## Build Sequence

### Phase 0 — Today (5 minutes)
**Owner:** El Presidente in Supabase SQL Editor

1. Run `hk_research_schema.sql` in Supabase SQL Editor — creates `hk_research` schema + all 8 tables
2. Verify: `SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'hk_research'` → returns `hk_research`
3. Run contamination check: `SELECT COUNT(*) FROM velo_verdicts WHERE race_id NOT IN (SELECT race_id FROM races WHERE region IN ('GB','IRE'))` → must be 0 (then delete FR rows)
4. Done. Schema is live. No data yet.

---

### Phase 1 — This Week (Data Collection Starts)
**Owner:** VOX / Claude

1. **Wire `hk_daily_ingest.py`** — no deployment, just local test run
   ```bash
   python workers/hk_daily_ingest.py --date 2026-03-23
   ```
2. **Run manually for yesterday** — collect first HK racecard batch
3. **Verify data landed:**
   ```sql
   SELECT COUNT(*) FROM hk_research.hk_races;        -- should be > 0
   SELECT COUNT(*) FROM hk_research.hk_runners;      -- should be > 0
   SELECT COUNT(*) FROM hk_research.hk_ingestion_log; -- should be 1
   ```
4. **Schedule HK ingest** — 08:00 UTC daily via Railway cron (separate from UK pipeline)
   - Service: `hk-research-ingestion`
   - Script: `python workers/hk_daily_ingest.py`
   - Cron: `0 8 * * *` (08:00 UTC = 01:00 HKT)
   - This runs AFTER UK race day ends. HK races on the previous day are final.

---

### Phase 2 — This Month (Historical Backfill)
**Owner:** VOX

1. **Backfill HK historical data** — script: `scripts/backfill_hk_history.py`
   - Fetch as many past HK racecards as API allows
   - Priority: last 90 days minimum, 365 days target
   - Store in `hk_research.hk_*` tables
   - Rate limit: 1 req/s (API allows 5 req/s, use 1 for safety)
2. **Trainer/Jockey entity enrichment** — once horse history is > 30 days:
   - Fetch `/v1/trainers/{id}/analysis/courses` for each HK trainer
   - Fetch `/v1/jockeys/{id}/analysis/courses` for each HK jockey
   - Store in `hk_research.hk_trainer_stats`, `hk_jockey_stats`
3. **Verify backfill quality:**
   ```sql
   SELECT course, COUNT(*) FROM hk_research.hk_races GROUP BY course;
   -- Expect: Happy Valley, Sha Tin only
   SELECT COUNT(DISTINCT horse_id) FROM hk_research.hk_runners;
   -- Expect: growing count, target 500+ horses
   ```

---

### Phase 3 — Month 2 (Research Analysis)
**Owner:** VOX + El Presidente

1. **HK pace shape study** — classify each HK course:
   - Happy Valley: tight circuit, front-runners preferred, draw bias
   - Sha Tin: sweeping bends, strong-finishers, polytrack surface
2. **HK trainer/jockey profiles** — build behavioral models:
   - Which trainers over-perform at specific distances?
   - Which jockeys over-perform on specific courses/surfaces?
   - Are there jockey-trainer combos that fire at specific odds ranges?
3. **Market behavior** — if odds data is available in `hk_market_snapshots`:
   - HK odds are decimilised (1.5, 2.0, etc.)
   - Track favourite strike rate by course, distance, going
   - Identify market inefficiencies vs UK patterns

---

### Phase 4 — Month 3+ (Research Scoring)
**Owner:** VOX (with explicit approval)

1. **Research scoring only** — `scripts/score_hk_research.py`
   - Runs velo_prime_service on HK races
   - Writes to `hk_research.hk_predictions` — NOT `velo_verdicts`
   - No Telegram output. No betting signal. Internal only.
2. **Backtest on known results** — test HK model on historical races where results are known:
   ```
   For each HK race in last 30 days (known results):
     Run velo_prime_service on pre-race snapshot
     Compare predicted winner vs actual winner
     Record: A-tier strike, B-tier strike, miss categories
   ```
3. **Evaluate** — if A-tier strike > 38% on HK:
   - Propose HK live betting in next phase gate review
   - Until then: HK stays in research lane

---

## What Can Be Built NOW vs Later

| What | Now? | How |
|---|---|---|
| HK schema in Supabase | ✅ | Run SQL migration |
| HK racecard ingestion | ✅ | Wire + test `hk_daily_ingest.py` |
| HK results ingestion | ✅ | Same script, results endpoint |
| HK historical backfill | ✅ | Backfill script, 90-day target |
| HK live betting signal | ❌ | Phase 4 only |
| HK doctrine learning | ❌ | Phase 4 only |
| HK Telegram output | ❌ | Never unless HK goes live |

---

## HK Racing API — Available Endpoints (Standard Plan)

| Endpoint | Available for HK? | Notes |
|---|---|---|
| `/v1/racecards` | ✅ | Filter `region=HK` locally |
| `/v1/results` | ✅ | Filter `region=HK` locally |
| `/v1/courses` | ✅ | HK = Happy Valley, Sha Tin |
| `/v1/horses/search` | ✅ | Standard plan |
| `/v1/horses/{id}/standard` | ✅ | Standard plan |
| `/v1/horses/{id}/analysis/distance-times` | ✅ | Standard plan |
| `/v1/horses/{id}/results` | ❌ | **Pro plan only** |
| `/v1/trainers/search` | ✅ | Standard plan |
| `/v1/trainers/{id}/analysis/*` | ✅ | Standard plan |
| `/v1/jockeys/search` | ✅ | Standard plan |
| `/v1/jockeys/{id}/analysis/*` | ✅ | Standard plan |

**Key gap:** Horse historical results (`/v1/horses/{id}/results`) requires Pro plan.
Workaround: build horse history from `hk_results` table incrementally — each race day adds to each horse's history.

---

## HK Race Schedule (UTC Reference)

HK races run HKT = UTC+8.

| HKT | UTC | UK Reference |
|---|---|---|
| 07:00 | 23:00 (prev day) | UK midnight |
| 11:00 | 03:00 | UK early morning |
| 13:00 | 05:00 | UK morning |
| 16:35 | 08:35 | **Best ingest window: 08:00 UTC** |

Best daily ingest time: **08:00 UTC** (16:00 HKT = end of afternoon meeting, early evening race results available)

---

## France — Archive-Only Decision

France is lower priority. If archive-only:
- Same schema, different schema name: `fr_research.*`
- Same table structure as `hk_research.*`
- Ingestion script: `workers/fr_daily_ingest.py` (mirror of HK script)
- **Default filter for production stays: `{'GB', 'IRE'}` — France explicitly excluded**

France 188 courses vs HK 2 courses. France is 94x bigger scope. HK is the right second market.
