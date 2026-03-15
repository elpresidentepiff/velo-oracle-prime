# VÉLØ Production Fix Report — 2026-03-15

**Author:** Claude Code (Sonnet 4.6)
**Commit:** `2490218`
**Branch:** `main` → pushed to `origin/main`
**Status:** FIXES COMMITTED AND PUSHED. RAILWAY REDEPLOY IN PROGRESS.

---

## 1. What Was Broken

### BUG 1 — Parser import crash (ingestion-spine)
**File:** `workers/ingestion_spine/parsers/__init__.py`

Both `parsers.py` (flat file) and `parsers/` (directory/package) existed at
`workers/ingestion_spine/`. Python always resolves the directory first, making
`parsers.py` invisible to normal imports. The old `__init__.py` worked around
this with a 20-line `importlib.util.spec_from_file_location` hack — loading
`parsers.py` by absolute file path. This broke silently in Docker containers
where the absolute path assumption doesn't hold.

Manus had added `_parsers_base.py` (identical content to `parsers.py`) as the
correct fix, but never updated `__init__.py` to use it. The hack stayed live.

### BUG 2 — Runner duplication (x10 inflation)
**File:** `workers/daily_pipeline.py`
**Table:** `runners`

`supabase_upsert("runners", runner_rows)` was called without `conflict_keys`.
Supabase's `Prefer: resolution=merge-duplicates` requires an `?on_conflict=`
URL parameter to know which columns to deduplicate on. Without it, every run
inserted fresh rows (each with a new UUID primary key — no conflict ever
triggered). The `runners` table also had no unique constraint.

Result: 2,756 rows for 265 real runners (10.4× inflation).
`runners_processed` reported 0 in pipeline_runs because the upsert was
returning HTTP errors on conflict.

### BUG 3 — Stacked in_progress pipeline runs
**File:** `workers/daily_pipeline.py`

No guard existed to prevent concurrent runs. When Railway triggered the cron
while a run was still executing, a second (and third, fourth…) run started
immediately. Today's run history showed 5 ghost runs stuck `in_progress`
simultaneously with 0 rows processed.

---

## 2. Exact Fixes Applied

### Fix 1 — `workers/ingestion_spine/parsers/__init__.py`

**Before (37 lines, fragile):**
```python
import importlib, importlib.util, sys, os
_parsers_path = os.path.join(os.path.dirname(os.path.dirname(...)), "parsers.py")
_spec = importlib.util.spec_from_file_location("_ingestion_parsers_base", _parsers_path)
_mod = importlib.util.module_from_spec(_spec)
import ingestion_spine.models
_mod.__package__ = "ingestion_spine"
_spec.loader.exec_module(_mod)
RacecardsParser = _mod.RacecardsParser
...
```

**After (3 lines, correct):**
```python
from ingestion_spine._parsers_base import RacecardsParser, RunnersParser, FormParser
from .quality import calculate_race_quality, calculate_runner_confidence
```

`_parsers_base.py` is already in the container at `/app/ingestion_spine/_parsers_base.py`,
importable as `ingestion_spine._parsers_base`. Direct import. No hacks.

---

### Fix 2 — `workers/daily_pipeline.py` — runners conflict key

**Before:**
```python
ok = supabase_upsert("runners", runner_rows, run_id=run_id, stats=stats)
```

**After:**
```python
ok = supabase_upsert("runners", runner_rows,
                     conflict_keys=["race_id", "horse_id"],
                     run_id=run_id, stats=stats)
```

Now generates `POST .../runners?on_conflict=race_id,horse_id` — Supabase
deduplicates correctly. Combined with the `UNIQUE(race_id, horse_id)` constraint
added via migration `20260315_fix_runner_dedup_unique_constraint.sql`.

---

### Fix 3 — `workers/daily_pipeline.py` — single-run guard

Added `check_already_running(target_date)` before `open_pipeline_run()`:

```python
def check_already_running(target_date):
    """Return True if an in_progress daily_ingestion run exists for this date."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/pipeline_runs",
        params={"source_date": f"eq.{target_date}", "status": "eq.in_progress",
                "run_type": "eq.daily_ingestion", "select": "id,started_at"},
        ...
    )
    if rows: log.warning("[guard] Active run already in_progress..."); return True
    return False

def run_pipeline(target_date=None):
    ...
    if check_already_running(target_date):
        return {"status": "SKIPPED", "reason": "run already in_progress for this date"}
```

If a run is active, the new invocation logs a warning and exits cleanly —
no new `pipeline_run` row, no duplicate data.

---

### DB Fix — Runner deduplication (applied directly via Supabase MCP)

Migration: `supabase/migrations/20260315_fix_runner_dedup_unique_constraint.sql`

```sql
DELETE FROM runners
WHERE id NOT IN (
  SELECT DISTINCT ON (race_id, horse_id) id
  FROM runners ORDER BY race_id, horse_id, created_at ASC
);

ALTER TABLE runners
  ADD CONSTRAINT runners_race_horse_unique UNIQUE (race_id, horse_id);
```

Applied live. 2,756 rows → 265 rows. Unique constraint now enforced at DB level.

---

## 3. Commit Record

| Commit | Description |
|---|---|
| `e053c33` | Dockerfile build context fix + CLAUDE.md sync |
| `599db2b` | Runner dedup migration file added to repo |
| `2490218` | **Parser import fix + single-run guard + runners conflict key** |

All pushed to `origin/main`. Railway auto-deploys from `main`.

---

## 4. Supabase State — Post-Fix Snapshot

| Table | Rows | Status |
|---|---|---|
| `runners` | 265 | Clean — deduplicated, unique constraint live |
| `races` | 32 | Correct |
| `runner_race_facts` | 243 | Correct (from first clean run) |
| `horse_profiles` | 243 | Correct |
| `raw_payload_archive` | 25 | Active |
| `race_results` | 0 | Expected — today's races haven't finished yet |
| `runner_results` | 0 | Expected — depends on race_results |
| Active `in_progress` runs | 0 | Clean |

---

## 5. What Next Run Should Look Like

A successful post-fix run at 06:00 UTC tomorrow should produce:

- `pipeline_runs`: 1 row, `status=success`, `runners_processed=~240`
- `runners`: same 265 rows (upsert updates, no new rows)
- `runner_race_facts`: same 243 rows (upsert updates)
- `race_results`: populated after races finish (~17:00–20:00 UTC)
- `runner_results`: populated alongside `race_results`
- No `in_progress` stacking

---

## 6. Remaining Risks

| ID | Severity | Issue | Action Needed |
|---|---|---|---|
| R-01 | HIGH | `race_results` / `runner_results` empty | Wait for today's races to finish; verify results reconciliation runs |
| R-02 | MEDIUM | Cron schedule `0 10 *` instead of `0 6 *` | Railway UI → ingestion-spine cron → change to `0 6 * * *` |
| R-03 | MEDIUM | Verdict `horse_name` stores `horse_id` | Verdict generator code not found in repo — source unknown |
| R-04 | LOW | `ingestion_anomalies` column mismatch | `_log_anomaly` writes `table_name`/`detail` — columns don't exist in schema. Silent fail only. |
| R-05 | LOW | `market_snapshots` not polling | `job_market_snapshot` exists in `ingestion_scheduler.py` but not scheduled in Railway |

---

## 7. Victory Conditions (per doctrine)

- [ ] No import crash on Railway deploy
- [ ] One clean deploy succeeds
- [ ] One manual run succeeds
- [ ] `pipeline_runs` closes with `status=success`, `runners_processed > 0`
- [ ] `race_results` and `runner_results` start populating after races finish
- [ ] No stacked `in_progress` runs

Items 1–4 should be verifiable at next cron fire (06:00 UTC tomorrow).
Items 5–6 require today's races to complete.
