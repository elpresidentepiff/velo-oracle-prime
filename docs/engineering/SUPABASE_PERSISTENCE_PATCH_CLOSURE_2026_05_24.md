# Supabase Persistence Patch Closure — 2026-05-24

**Classification:** `PATCH_CLOSURE`  
**Status:** IMPLEMENTED  
**Date:** 2026-05-24  
**Authority:** El Presidente  
**Reference:** `docs/engineering/SUPABASE_DECISION_TIER_NULL_AUDIT_2026_05_24.md`

---

## Root Cause (from audit)

`persist_race_predictions()` in `app/services/velo_prime_service.py` accepted `decision_tier` as a parameter, validated it, but never wrote it to the Supabase row dict. Same silent omission for `git_commit_sha` (no parameter existed at all). Dashboard publisher had no warning when it fell back to local JSON due to missing credentials.

---

## Patch Summary

### Fix 1 — `decision_tier` in velo_verdicts

**File:** `app/services/velo_prime_service.py`  
**Change:** Added `"decision_tier": decision_tier` to the `row` dict in `persist_race_predictions`.  
**Location:** After `"execution_allowed"` at end of row dict construction.  
**Lines changed:** 2 (the entry + a comment)

No logic change. The `decision_tier` parameter was already accepted and validated. The data was always there. It was just never written.

### Fix 2 — `git_commit_sha` in velo_verdicts

**File:** `app/services/velo_prime_service.py`  
**Change:** Added `commit_sha: str | None = None` to function signature. Added `"git_commit_sha": commit_sha` to row dict.

**File:** `scripts/ops/run_prime_today.py`  
**Change:** Updated call to `persist_race_predictions(race, preds, decision_tier=tier, commit_sha=commit_sha)`. The `commit_sha` variable was already computed at line 1247 via `get_commit_sha()` — it just wasn't being passed.

**Lines changed:** 4 (signature, row entry, call-site, comment)

Architecture used: Option A (add parameter) — cleaner than reading commit inside the persist function.

### Fix 3 — Publisher fallback warning

**File:** `scripts/ops/publish_daily_predictions_to_dashboard.py`  
**Change:** When `sb_data` is empty (Supabase read skipped or failed), prints:

```
⚠ SUPABASE_PUBLISH_FALLBACK_WARN — <date>
  reason         = supabase_skipped:no_credentials
  dashboard_source = local_json_top_only
  Dashboard will publish top-pick only (1 runner per race, not full field).
  To fix: ensure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are in environment.
  Rerun after scoring completes: python scripts/ops/publish_daily_predictions_to_dashboard.py --date <date>
```

Also echoed in the summary print block. Added `supabase_fallback_warn` and `supabase_fallback_reason` to the audit JSON for queryability.

Does NOT block publish. Does NOT redesign dashboard logic. Warns loudly only.

---

## Test Results

**Syntax test (py_compile):** ALL_SYNTAX_OK
```
python -m py_compile app/services/velo_prime_service.py scripts/ops/run_prime_today.py scripts/ops/publish_daily_predictions_to_dashboard.py
```

**Function signature verification:**
```
Signature: (race, predictions, decision_tier=None, commit_sha=None) -> bool
decision_tier in row dict: True
git_commit_sha in row dict: True
```

**Dry-run persistence test:** NO_SAFE_DRY_PERSIST_TEST_FOUND — `--dry-run` mode disables all persistence, so no partial safe test path exists without writing to Supabase. The fix is verified by code inspection only.

---

## Behavior After Patch

**Before patch:**
- `velo_verdicts.decision_tier` = NULL for all rows from batch script
- `velo_verdicts.git_commit_sha` = NULL for all rows from batch script
- Dashboard publisher silently fell back to local JSON with no operator warning

**After patch:**
- `velo_verdicts.decision_tier` = canonical tier (`A`, `B`, `C`, `D`, `X`) for every row
- `velo_verdicts.git_commit_sha` = 40-char commit SHA for every row
- Dashboard publisher prints `⚠ SUPABASE_PUBLISH_FALLBACK_WARN` when credentials missing

Active from next scoring run (2026-05-25 morning).

---

## Historical Rows

Historical velo_verdicts rows (all days before this patch) remain with NULL `decision_tier` and NULL `git_commit_sha`. These are preserved as-is as historical audit evidence. Backfilling historical rows is a separate operation requiring its own Council approval — it mutates the prediction history record.

The correct interpretation: any velo_verdicts row with NULL `decision_tier` was written by the batch script before this patch. Any row with a non-NULL `decision_tier` was written after, or by the FastAPI path.

---

## What This Patch Does NOT Do

- Does not change scoring behavior
- Does not change tier thresholds or formulas
- Does not affect prediction output (tiers are still computed correctly in memory and Telegram)
- Does not require a Supabase schema migration (columns already existed)
- Does not backfill historical NULL rows
- Does not change the dashboard's data source decision logic
- Does not change Telegram pick format
- Does not alter any model, router, or staking logic
- Does not touch Playbook G or live state

---

```
PATCH_STATUS:             IMPLEMENTED
FILES_CHANGED:            app/services/velo_prime_service.py
                          scripts/ops/run_prime_today.py
                          scripts/ops/publish_daily_predictions_to_dashboard.py
MIGRATION_REQUIRED:       NO — columns already existed in velo_verdicts schema
HISTORICAL_BACKFILL:      NOT DONE — NULLs preserved as audit evidence
SCORING_CHANGE:           NONE
MODEL_CHANGE:             NONE
ROUTER_CHANGE:            NONE
STAKING_CHANGE:           NONE
TELEGRAM_PICK_CHANGE:     NONE
PLAYBOOK_G_CHANGE:        NONE
LIVE_STATE_MUTATION:      NONE
SYNTAX_TEST:              ALL_SYNTAX_OK
SAFE_PERSIST_TEST:        NO_SAFE_DRY_PERSIST_TEST_FOUND — code inspection only
ACTIVE_FROM:              2026-05-25 morning run
```
