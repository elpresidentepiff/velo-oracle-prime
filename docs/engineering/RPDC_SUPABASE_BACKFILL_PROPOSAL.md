# RPDC Supabase Backfill Architecture Proposal

**Classification:** `ARCHITECTURE_PROPOSAL`  
**Status:** PENDING_COUNCIL_APPROVAL  
**Date:** 2026-05-24  
**Authority:** El Presidente  
**Reference:** `docs/engineering/RPDC_TAGGING_ASSET_INVENTORY.md`  
**Reference:** `docs/engineering/RPDC_DEGRADATION_SCOPE_AUDIT_2026_05_08_TO_2026_05_24.md`

---

## Problem Statement

RPDC (Racing Post Data Context) is horse-career memory. It answers: "Is this horse at a release point in its career cycle?" The current architecture treats it as a daily ephemeral artifact built from scratch each morning:

```
build_rpdc_daily.py → runner_release_candidates (one day, overwritten)
```

This creates two structural failures:
1. **No career continuity**: each build only has history that was ingested into `racing_horse_runs` the night before. If the ingest chain breaks, RPDC has no history.
2. **No auditability**: once the day passes, what RPDC context the scoring run used is gone unless explicitly preserved.

The correct architecture is a persistent horse-career memory layer, queried at scoring time.

---

## Audit Evidence

From `scripts/audit_rpdc_historical_coverage.py` (run 2026-05-24):

| Metric | Value |
|---|---|
| Scored dates with RPDC fully working | 1 (2026-05-07 only) |
| Scored dates with horse history in DB, RPDC never built | 51 |
| Scored dates needing Supabase ingest first | 9 |
| racing_horse_runs total rows | 91,804 (211 dates, back to 2025-10-13) |
| runner_release_candidates rows | 20,969 (48 dates, bulk-loaded 2026-05-08 only) |

The `runner_release_candidates` table is the wrong design. It stores RPDC output indexed by `run_date` — so every scoring day rebuilds from scratch. If `racing_horse_runs` is stale (as it has been since May 9), there is no fallback.

---

## Proposed Architecture

### Option A — `rpdc_horse_memory` table (recommended)

A new Supabase table that stores the **current RPDC snapshot per horse**, updated after each ingest run. Scoring reads from this table instead of rebuilding each day.

```sql
CREATE TABLE rpdc_horse_memory (
    horse_id           TEXT PRIMARY KEY,
    horse              TEXT,
    last_run_date      DATE,
    last_ingest_date   DATE,      -- when this row was last updated
    campaign_run_no    INTEGER,   -- runs in current year
    days_since_run     INTEGER,
    last_winning_or    INTEGER,
    current_or         INTEGER,
    or_delta_to_win    INTEGER,
    course_return_ids  TEXT[],    -- course_ids where horse has won
    distance_wins      NUMERIC[], -- distances where horse has won
    trainer_id         TEXT,
    stable_heat        NUMERIC,   -- trainer win rate last 30d
    win_count_recent   INTEGER,   -- wins in last 5 runs
    found_place_recent BOOLEAN,   -- placed on most recent run
    run_count_history  INTEGER,   -- total runs in our data window
    provenance         TEXT,      -- LOCAL_ONLY | SUPABASE_FULL | HYBRID
    generated_at       TIMESTAMPTZ DEFAULT NOW()
);
```

**Write path:** `ingest_results_to_horse_runs.py` → after writing `racing_horse_runs`, upserts `rpdc_horse_memory` rows for all horses in that day's results.

**Read path:** `build_rpdc_daily.py` reads from `rpdc_horse_memory` instead of building history per-horse. Falls back to `racing_horse_runs` query if memory row is stale (>7 days).

**Conflict key:** `horse_id` (one row per horse, updated in-place).

### Option B — Local JSONL canonical file (simpler, already built)

`data/rpdc_backfill/rpdc_tags_historical.jsonl` is the local artifact produced by `backfill_rpdc_historical_local.py`. This file covers 44 scored dates, 18,554 runner rows, and can be queried directly by scoring scripts.

**Read path:** `run_prime_today.py` loads this file at startup, builds a lookup dict `{horse_id → latest_row}`, and falls back to Supabase if not found.

**Limitation:** Stale between scoring runs. Requires daily re-generation after results ingest.

### Recommended path

**Immediate (no migration, no approval needed):** Use the local JSONL as a query layer in run_prime_today.py. This gives RPDC history to the scoring run without touching Supabase.

**Medium term (requires Council approval):** Migrate to `rpdc_horse_memory` Supabase table. Write on ingest, read at scoring time. This gives persistent career memory that survives daily restarts and Railway deployments.

---

## Supabase Ingest Backfill Plan (9 dates)

The coverage audit identified 9 scored dates with results files but zero horse_runs rows:

| Date | Results Races | Verdict Races |
|---|---|---|
| 2026-05-09 | 64 | 64 |
| 2026-05-10 | 29 | 29 |
| 2026-05-12 | 39 | 39 |
| 2026-05-13 | 42 | 42 |
| 2026-05-14 | 35 | 35 |
| 2026-05-15 | 52 | 52 |
| 2026-05-16 | 60 | 60 |
| 2026-05-18 | 31 | 34 |
| 2026-05-20 | 32 | 33 |

**Tables that would be written:** `racing_horse_runs` only (conflict key: `race_id, horse_id`).

**No other tables touched.** `runner_release_candidates` and `velo_verdicts` are NOT mutated.

**Run command (once per date, requires operator approval per date):**
```bash
source venv/bin/activate && PYTHONPATH=. python scripts/ops/ingest_results_to_horse_runs.py --date YYYY-MM-DD
```

**Safety:** The script uses `upsert` with `on_conflict=race_id,horse_id` — re-running is idempotent. No overwrite of existing rows.

**Approval status:** NOT YET APPROVED — each date requires separate operator sign-off before running.

---

## Rollback Plan

**For Option A (rpdc_horse_memory table):**
- Delete the table: `DROP TABLE IF EXISTS rpdc_horse_memory;`
- Revert `ingest_results_to_horse_runs.py` to remove the upsert call
- Revert `build_rpdc_daily.py` to use `racing_horse_runs` queries
- `runner_release_candidates` is unchanged throughout — rollback is zero-risk

**For Option B (local JSONL):**
- Delete `data/rpdc_backfill/rpdc_tags_historical.jsonl`
- Revert `run_prime_today.py` to not load the file
- Zero Supabase impact

---

## What This Proposal Does NOT Do

- Does not backfill `velo_verdicts` historical rows (separate Council decision)
- Does not change scoring formulas, thresholds, or tier logic
- Does not change Telegram output format
- Does not change Playbook G or live staking
- Does not retroactively alter any prediction record
- The `rpdc_horse_memory` table stores career context, not prediction output

---

## Implementation Gate Requirements

Before Option A can be executed:

| Gate | Requirement | Status |
|---|---|---|
| Supabase migration approved | Council approval for new table | PENDING |
| Ingest safety review | Confirm `ingest_results_to_horse_runs.py` idempotency | CONFIRMED |
| Daily backfill run approved | Operator must approve each of the 9 SUPABASE_INGEST_ELIGIBLE dates | PENDING |
| Local JSONL validated | `backfill_rpdc_historical_local.py` outputs verified | DONE (2026-05-24) |
| RPDC_MISSION_CONTROL requirements | Chain status fields added to mission control | SEE REQUIREMENTS DOC |

---

```
PROPOSAL_STATUS:              PENDING_COUNCIL_APPROVAL
MIGRATION_REQUIRED:           YES (Option A) / NO (Option B)
SUPABASE_TABLES_AFFECTED:     racing_horse_runs (ingest), rpdc_horse_memory (new, Option A only)
HISTORICAL_VERDICTS_AFFECTED: NONE
SCORING_CHANGE:               NONE
MODEL_CHANGE:                 NONE
TELEGRAM_CHANGE:              NONE
LOCAL_ARTIFACT_AVAILABLE:     YES — data/rpdc_backfill/rpdc_tags_historical.jsonl
INGEST_ELIGIBLE_DATES:        9 — requires operator approval per date
```
