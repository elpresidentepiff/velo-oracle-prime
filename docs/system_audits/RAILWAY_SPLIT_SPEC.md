# VÉLØ Railway Split Spec
**Status:** APPROVED — DO NOT IMPLEMENT UNTIL THIS DOCUMENT IS COMPLETE
**Version:** 1.0
**Date:** 2026-04-09
**Architecture:** Two-Lane Production + Shadow Lab

---

## 1. Production Service

### Service Identity
| Field | Value |
|-------|-------|
| Railway service name | `velo-prime-scoring-prod` |
| Git branch | `main` (locked — no experimental merges) |
| Entrypoint | `python scripts/run_prime_today.py` |
| Cron schedule | `0 9 * * 1-6` (09:00 UTC Mon–Sat) |

### What Production Writes
| Table | Access |
|-------|--------|
| `public.velo_verdicts` | Write (upsert, top pick per race) |
| `public.pipeline_runs` | Write (run state + status) |
| `public.sigma_audits` | Write (existing) |

### Production Boundaries (Hard Rules)
- MUST NOT import any G/sentient/analog shadow modules
- MUST NOT write to shadow tables
- MUST NOT depend on `velo_shadow_*` tables existing
- G state is not loaded in production path
- Telegram output is production-only, not shadow-driven

### Rollback Commitment
- Production is pinned to last-known-good: **March 28 deploy** (commit `8552700b`, deployment `3dfdb43a`)
- No promotion to production without a shadow-to-production handoff artifact
- Any production change requires sign-off: verifiable scoring + Telegram + velo_verdicts persist

---

## 2. Shadow Service

### Service Identity
| Field | Value |
|-------|-------|
| Railway service name | `velo-shadow-lab` |
| Git branch | `shadow-lab` (fast-moving experimentation) |
| Entrypoint | `python scripts/shadow_lab.py` |
| Cron schedule | `30 9 * * 1-6` (09:30 UTC Mon–Sat, 30 min after production) |

### Entrypoint Contract: `scripts/shadow_lab.py`
```
Input:   None (self-determines what to process via watermark)
Output:  Shadow enrichment rows written to shadow tables
Side effect: High watermark updated in shadow_state table
```

### Trigger Logic
Shadow lab does NOT run the scoring pipeline. It follows production:

1. Query `pipeline_runs` for `velo-prime-scoring-prod` with `status = 'completed'`
2. Find the most recent completed `pipeline_run_id`
3. Query `velo_verdicts` where `pipeline_run_id = <latest completed>`
4. If no new completed batch since last watermark → exit silently
5. If new batch exists → process full batch atomically

### Watermark / Idempotency
| Field | Value |
|-------|-------|
| Storage table | `public.shadow_watermarks` |
| Key columns | `service_name`, `pipeline_run_id`, `last_processed_at` |
| Idempotency | `pipeline_run_id` is unique per scoring run; re-running same run is a no-op |
| Composite key | `race_id + pipeline_run_id` ensures no row processed twice |

```sql
CREATE TABLE IF NOT EXISTS public.shadow_watermarks (
    id          BIGSERIAL PRIMARY KEY,
    service_name TEXT NOT NULL,
    pipeline_run_id TEXT NOT NULL,
    last_processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rows_processed  INTEGER NOT NULL DEFAULT 0,
    UNIQUE(service_name, pipeline_run_id)
);
```

### Failure Isolation
- Shadow lab failure MUST NOT affect production scoring
- Shadow lab runs independently; production does not depend on it
- Shadow failures write to `shadow_audit_log` with error state, do not block
- If shadow crashes mid-batch: watermark not advanced; next run picks up at last successful commit

### What Shadow Reads (Read-Only)
| Table | Access |
|-------|--------|
| `public.velo_verdicts` | Read (consume production output) |
| `public.pipeline_runs` | Read (detect batch completion) |
| `public.sigma_audits` | Read (optional enrichment) |
| `public.learned_patterns` | Read (G state for restore) |
| `public.race_fingerprint_*` | Read (historical analog) |

### What Shadow Writes (Write-Only)
| Table | Access |
|-------|--------|
| `public.shadow_watermarks` | Write (idempotency state) |
| `public.shadow_audit_log` | Write (per-row processing log) |
| `public.velo_shadow_results` | Write (G shadow evaluation per verdict) |
| `public.velo_shadow_rank_movement` | Write (top-3 rank movement analysis) |

---

## 3. Database Contract

### Credential Separation
| Service | Supabase Key Type | Access Scope |
|---------|------------------|--------------|
| `velo-prime-scoring-prod` | Service role key (existing) | Full write to production tables |
| `velo-shadow-lab` | **Separate** service role key | Read production tables + write shadow tables |

> **Rule:** Shadow lab must have its own Supabase service role key with restricted table policies. It must NOT use the production service role key.

### Supabase Row-Level Security Notes
- Production tables (`velo_verdicts`, `pipeline_runs`): shadow lab role = `SELECT` only
- Shadow tables: shadow lab role = `SELECT, INSERT, UPDATE`; prod role = `SELECT` only

### Table Creation for Shadow Lab
```sql
-- Shadow watermarks (idempotency)
CREATE TABLE IF NOT EXISTS public.shadow_watermarks (
    id              BIGSERIAL PRIMARY KEY,
    service_name    TEXT NOT NULL,
    pipeline_run_id  TEXT NOT NULL,
    last_processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rows_processed   INTEGER NOT NULL DEFAULT 0,
    UNIQUE(service_name, pipeline_run_id)
);

-- Per-row processing audit log
CREATE TABLE IF NOT EXISTS public.shadow_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL,
    race_id         TEXT NOT NULL,
    pipeline_run_id TEXT NOT NULL,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          TEXT NOT NULL,  -- 'success' | 'error' | 'skipped'
    error_message   TEXT,
    rows_evaluated  INTEGER
);

-- G shadow evaluation results
CREATE TABLE IF NOT EXISTS public.velo_shadow_results (
    id               BIGSERIAL PRIMARY KEY,
    race_id          TEXT NOT NULL,
    pipeline_run_id  TEXT NOT NULL,
    generated_at     TIMESTAMPTZ NOT NULL,
    g_shadow_multiplier REAL,
    g_shadow_flags   TEXT[],
    g_shadow_horse_id TEXT,
    g_shadow_mode    TEXT,
    doctrines_fired  TEXT[],
    sentiment_score  REAL,
    processed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(race_id, pipeline_run_id)
);

-- Top-3 rank movement analysis
CREATE TABLE IF NOT EXISTS public.velo_shadow_rank_movement (
    id               BIGSERIAL PRIMARY KEY,
    race_id          TEXT NOT NULL,
    pipeline_run_id  TEXT NOT NULL,
    generated_at     TIMESTAMPTZ NOT NULL,
    top3_scores      JSONB,  -- [{horse_id, velo_prime_prob, g_shadow_multiplier, ...}]
    rank_1_base_prob REAL,
    rank_1_shadow_prob REAL,
    rank_shift       INTEGER,  -- positive = moved up, negative = moved down
    shortlist_changed BOOLEAN,
    favourite_overturned BOOLEAN,
    processed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(race_id, pipeline_run_id)
);
```

---

## 4. Batch Completeness Rule

**Shadow must NOT process incomplete production batches.**

Completion detection method:

```
1. Poll: SELECT * FROM pipeline_runs
   WHERE service_name = 'velo-prime-scoring-prod'
   AND status = 'completed'
   ORDER BY started_at DESC LIMIT 1;

2. Compare pipeline_run_id against shadow_watermarks.last_processed_at

3. Only process if:
   a) pipeline_run_id is new (not in shadow_watermarks for velo-shadow-lab)  AND
   b) pipeline_run.status = 'completed'  AND
   c) All velo_verdicts for that pipeline_run_id are written
       (count check: velo_verdicts WHERE pipeline_run_id = X must equal expected race count)
```

**Timeout:** If pipeline_run is not `completed` within 2 hours of `started_at`, shadow skips that batch. It will retry on next cron wake.

**In-progress detection:** Shadow reads `velo_verdicts.generated_at` as the real completion signal. If new rows keep arriving (within 5 min of each other), shadow waits until the batch stabilizes.

---

## 5. Deployment Sequence

### Phase 1 — Lock Production (DONE)
- [x] velo-prime-scoring rolled back to March 28 deploy (`3dfdb43a`)
- [x] Production service confirmed writing fresh rows at 06:25
- [x] Telegram output confirmed working

### Phase 2 — Create Shadow Infrastructure
- [ ] Create `shadow-lab` branch from current `main`
- [ ] Add `scripts/shadow_lab.py` to shadow-lab branch
- [ ] Add shadow tables to Supabase (migration file)
- [ ] Create separate Supabase service role key for shadow lab
- [ ] Add row-level security policies for shadow tables

### Phase 3 — Create velo-shadow-lab Railway Service
- [ ] Create new Railway service: `velo-shadow-lab`
- [ ] Branch: `shadow-lab`
- [ ] Start command: `python scripts/shadow_lab.py`
- [ ] Cron: `30 9 * * 1-6`
- [ ] Env vars: separate shadow Supabase key, G state restore vars
- [ ] Deploy velo-shadow-lab (initial empty implementation that just logs and exits)

### Phase 4 — Implement Shadow Logic
- [ ] Implement watermark detection
- [ ] Implement G shadow evaluation (port from existing `_g_shadow_adjustment`)
- [ ] Implement rank movement analysis
- [ ] Implement audit logging per row
- [ ] Verify: shadow writes only to shadow tables

### Phase 5 — Verify Boundaries
- [ ] Production still scoring normally
- [ ] Shadow reads production rows (confirmed via logs)
- [ ] Shadow writes only to shadow tables
- [ ] Shadow failure does not appear in production logs
- [ ] Idempotency confirmed: re-running same pipeline_run_id is a no-op

### Phase 6 — Documentation
- [ ] Update `docs/live_state/MASTER_STATE.md` with two-lane architecture
- [ ] Create `docs/system_audits/RAILWAY_SPLIT_PLAN.md`
- [ ] Record deployment IDs and commit SHAs for both services

---

## 6. Hard Constraints (Do Not Violate)

| Rule | Reason |
|------|--------|
| No G/sentient imports in production scoring | Blast radius isolation |
| No shadow writes to production tables | Data integrity |
| No Telegram output from shadow at launch | Operational simplicity |
| No merge of shadow deps into production startup | Prevents repeat of Apr 9 failure |
| Shadow cron runs 30 min after production | Allows batch completion |
| Shadow has own Supabase key | Credential isolation |
| Production promotion requires handoff artifact | No intuition-only deploys |

---

## 7. Known Working Baseline

| Item | Value |
|------|-------|
| Last good production deploy | `3dfdb43a` (rollback of `8552700b`, March 28 image) |
| Last confirmed scoring | `rac_11922846` at `2026-04-09T06:25:51` |
| Telegram output | Confirmed working |
| velo_verdicts persist | Confirmed working |
| G shadow code (unstable) | On `main` at commits `753c608`–`acf7c0c` — DO NOT use in production |
| Shadow lab | Not yet created |

---

*Next action: Phase 2 — Create shadow infrastructure. Do not touch production.*
