# Supabase decision_tier NULL Audit — 2026-05-24

**Classification:** `AUDIT_COMPLETE`  
**Status:** ROOT_CAUSE_CONFIRMED — two separate issues identified  
**Date:** 2026-05-24  
**Authority:** El Presidente  
**Reference:** `docs/engineering/RPDC_GATE_IMPLEMENTATION_CLOSURE.md`  
**Reference:** `docs/engineering/MAY24_SUPABASE_RPDC_INCIDENT_AUDIT.md`

---

## Executive Summary

Two separate issues were found. They are unrelated.

| Issue | Root cause | Severity |
|---|---|---|
| `decision_tier NULL` in all Supabase velo_verdicts rows | `persist_race_predictions` accepts `decision_tier` parameter, validates it, but never puts it in the upsert `row` dict — silent omission, present since the function was written | MEDIUM — affects tier-based Supabase queries on all modern rows |
| Dashboard fallback on May 24 (`source: local_json_top_only`) | Publisher ran locally with Supabase credentials absent from environment (`supabase_skipped:no_credentials`) | LOW — operational issue, not a code bug |

The May 24 dashboard fallback was **NOT caused by `decision_tier NULL`**. The two issues are independent.

---

## Issue 1 — `decision_tier NULL` in velo_verdicts

### Where decision_tier is produced

`scripts/ops/run_prime_today.py:1488`:
```python
tier, reasons = synthesize_decision(top, sec_prob, field_size=len(preds))
```

`synthesize_decision()` is defined at `run_prime_today.py:439`. It returns a canonical tier string (`A`, `B`, `C`, `D`, or `X`) based on velo_prime_prob thresholds and field size.

The tier is stored correctly in the local verdicts file at `run_prime_today.py:1961`:
```python
"tier": tier,
```
Verified in `data/velo_prime_verdicts_2026_05_24.json`: race-level key `tier: "A"` (for the Sun Goddess race). The local file has the data.

### Where Supabase insert/upsert maps fields

`app/services/velo_prime_service.py:762`:
```python
def persist_race_predictions(race: dict, predictions: list[dict], decision_tier: str | None = None) -> bool:
```

The function is called from `run_prime_today.py:1720`:
```python
success = persist_race_predictions(race, preds, decision_tier=tier)
```

The `tier` value IS passed. Inside `persist_race_predictions`:
- Line 771: `if decision_tier is None:` → logs a warning (correctly)
- Line 782: `validate_tier(decision_tier)` → validates it (correctly)
- Lines 830–913: builds the `row` dict for Supabase upsert

### The bug — omission from row dict

The `row` dict built at lines 830–913 does NOT contain `"decision_tier"`. Every field that gets persisted to Supabase is listed there. `decision_tier` is absent.

The data travels this path:
```
synthesize_decision() → tier ✓
persist_race_predictions(decision_tier=tier) → validated ✓
row = { ...830 fields... }  ← decision_tier MISSING HERE ✗
sb.table("velo_verdicts").upsert(row, on_conflict="race_id").execute()
→ Supabase row: decision_tier = NULL
```

This is not a name mismatch. The parameter exists, the validation runs, but the line `"decision_tier": decision_tier` was never added to the `row` dict. One missing line.

### Does decision_tier exist in the Supabase schema?

YES. Evidence:
1. `publish_daily_predictions_to_dashboard.py:301` queries `.select("race_id, decision_tier, generated_at, full_analysis")` without error
2. `archive/legacy/.../sync_verdicts_from_supabase.py:61` reads `decision_tier` from the API without error  
3. `app/main.py:1513` writes `"decision_tier": tier` via its own upsert path — and it succeeds
4. The `20260412_003_a_tier_suspect_cohort.sql` migration references `decision_tier` in WHERE conditions on the live `velo_verdicts` table

The column exists. The write path is broken.

### Does this affect only May 24 or all days?

**All days** that used `run_prime_today.py` for persistence have `decision_tier = NULL` in Supabase. The bug has been present since `persist_race_predictions` was added to the script path.

The `app/main.py` FastAPI endpoint has its own Supabase upsert path (`app/main.py:1513`) which DOES write `"decision_tier": tier`. Any rows written via the FastAPI route (not the batch script) would have correct `decision_tier`.

The daily batch path (`run_prime_today.py` → `persist_race_predictions`) has never written `decision_tier`. This applies to the entire velo_verdicts history from the batch era forward.

### Does the dashboard expect a different field name?

No. `publish_daily_predictions_to_dashboard.py:321`:
```python
"decision_tier": row.get("decision_tier") or "?",
```
The field name matches. When NULL, it falls back to `"?"`. This is the correct graceful degradation — it just means the tier shown in the dashboard is `"?"` when Supabase data is used.

### Impact

- **Supabase-based tier queries** (e.g., `WHERE decision_tier = 'A'`) return 0 results for all modern batch-run rows
- **Dashboard tier display**: shows `"?"` when reading from Supabase (not local JSON)
- **Evidence audit queries** against velo_verdicts tier: return incorrect results for rows written by `run_prime_today.py`
- **Gate 4 (SUPABASE_WRITE_PROOF_REQUIRED)** would detect this post-persist if the proof checks `decision_tier IS NOT NULL`
- **No scoring impact**: tier is computed correctly in memory and used for Telegram output — it's only the Supabase record that has NULL

---

## Issue 2 — Dashboard Fallback on May 24 (`supabase_skipped:no_credentials`)

### Evidence

`data/dashboard_daily_predictions_publish_audit_v1.json`:
```json
"source_table_or_file": "local_json_top_only",
"supabase_source_detail": "supabase_skipped:no_credentials"
```

The publisher ran locally. `SUPABASE_URL` or `SUPABASE_SERVICE_ROLE_KEY`/`SUPABASE_SERVICE_KEY` was not available in the environment at publish time.

`publish_daily_predictions_to_dashboard.py:293–295`:
```python
sb_url = resolve_supabase_url()
sb_key = resolve_supabase_service_key()
if not sb_url or not sb_key:
    return {}, {}, "supabase_skipped:no_credentials"
```

This causes `sb_data = {}` (empty dict), which triggers the local JSON fallback path.

### Was `decision_tier NULL` the cause?

NO. The fallback happens before any Supabase row data is inspected. If credentials had been set, Supabase would have returned 29 rows (written by the scoring run). The publisher would have used those rows. The `decision_tier` would show as `"?"` in the per-race tier field, but the full predictions from `full_analysis.predictions` would be present — `source: "supabase+local_json"` would have been logged, not `"local_json_top_only"`.

### Impact of fallback

- Dashboard shows top-pick-only (1 runner per race, not full field)
- Confirmed: `data/dashboard_daily_predictions_2026_05_24.json` has 29 races, 29 runners (1 per race)
- A Supabase-sourced run would have all runners from `full_analysis.predictions` (241 runners total for May 24)
- **No prediction content change** — the top pick is the same whether sourced from Supabase or local JSON

### Fix

Operational: ensure `.env` credentials are loaded before running `publish_daily_predictions_to_dashboard.py` locally. The script calls `load_optional_env_file(None)` which should pick them up from `.env`. Gate 3 (SUPABASE_PUBLISH_FALLBACK_WARN) will alert the operator when this condition fires — that gate is still pending approval.

---

## Issue 3 — `git_commit_sha` Also Missing from Persist Path

While investigating `decision_tier`, `git_commit_sha` was also found missing from the same write path.

`run_prime_today.py:1247`:
```python
commit_sha = get_commit_sha()
```

The commit SHA is correctly computed and used in local artifacts (`runtime_timing_audit`, `runner_snapshot_store` run_id, Telegram output). But:

- `persist_race_predictions()` has no `commit_sha` parameter
- The `row` dict has no `"git_commit_sha"` key
- All velo_verdicts rows written by the batch script have `git_commit_sha = NULL`

The Supabase schema has this column (evidenced by `audit_railway_supabase_run_status.py:83` reading `latest.get("git_commit_sha")`). The FastAPI path at `app/main.py:1640` writes `"commit_sha": commit` via a different route.

Impact: audit queries against `git_commit_sha` (e.g., "show me all rows from this commit") return NULL for every batch-run row. Traceability gap.

---

## Recommended Fix (operator approval required before implementation)

### Fix 1 — `decision_tier` (one line)

**File:** `app/services/velo_prime_service.py`  
**Location:** `row` dict, after the `"execution_allowed"` entry (~line 912)  
**Change:**
```python
# Add this line:
"decision_tier": decision_tier,
```

The data is already validated at line 782. This is a pure omission fix — no logic change, no schema change, no migration needed (column already exists).

### Fix 2 — `git_commit_sha` (two changes)

**Option A — add parameter to persist function:**

`app/services/velo_prime_service.py:762` — change signature:
```python
def persist_race_predictions(race, predictions, decision_tier=None, commit_sha=None):
```

Add to `row` dict:
```python
"git_commit_sha": commit_sha,
```

`run_prime_today.py:1720` — update call:
```python
success = persist_race_predictions(race, preds, decision_tier=tier, commit_sha=commit_sha)
```

**Option B — read directly in persist function:**
```python
from scripts.ops.runtime_truth_support import get_commit_sha
row["git_commit_sha"] = get_commit_sha()
```
(Simpler — no call-site changes needed. Adds one import.)

Fix 1 is lower risk and has zero call-site changes. Fix 2 Option A is the cleaner architecture but requires updating all callers.

---

## What These Fixes Do NOT Do

- Do not change scoring behavior
- Do not change tier thresholds or formulas
- Do not affect local artifacts (verdicts file already stores `tier` correctly)
- Do not affect Telegram output (tier is used correctly in memory)
- Do not require Supabase schema migration (columns already exist)
- Do not backfill existing NULL rows (historical data remains NULL — acceptable)

---

```
AUDIT_STATUS:              COMPLETE
DECISION_TIER_NULL_CAUSE:  persist_race_predictions never adds decision_tier to row dict
MAY24_FALLBACK_CAUSE:      supabase_skipped:no_credentials (publisher ran without env vars)
TWO_ISSUES_INDEPENDENT:    CONFIRMED — fallback was NOT caused by decision_tier NULL
ALL_DAYS_AFFECTED:         YES — every row written by run_prime_today.py batch path
SCHEMA_COLUMN_EXISTS:      YES — decision_tier and git_commit_sha both in velo_verdicts
FIX_SIZE:                  decision_tier = 1 line; git_commit_sha = 2 lines + 1 call-site update
SCORING_CHANGE:            NONE
MODEL_CHANGE:              NONE
PATCH_APPROVED:            YES — 2026-05-24
PATCH_STATUS:              IMPLEMENTED — see SUPABASE_PERSISTENCE_PATCH_CLOSURE_2026_05_24.md
HISTORICAL_BACKFILL:       NOT DONE — historical NULLs remain as audit evidence
```
