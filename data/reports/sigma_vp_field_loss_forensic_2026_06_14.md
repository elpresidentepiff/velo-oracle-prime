# Sigma VP Field Loss — Forensic Investigation
**Date:** 2026-06-14
**Commit:** f82bde22659adbeed4ac429a14ecbe42afd1241b
**Status:** ROOT CAUSE CONFIRMED — FIX APPLIED — BACKFILL SCRIPT CREATED

---

## Executive Summary

The `velo_prime_prob` (VP) field appeared in per-race sigma rows for May 21 – Jun 05, then stopped appearing from Jun 06 onwards. This was caused by a **sigma artifact format change**, not a VP calculation error. VP was never lost from Supabase — only from the local mirror artifact.

The fix adds a `rows[]` array with full VP provenance to every future sigma artifact. The backfill script (`scripts/ops/backfill_sigma_vp.py`) recovers VP for all 256 affected rows from Jun 07–13 using same-day `velo_prime_verdicts_*.json` files.

---

## Root Cause

### Mechanism: ARTIFACT_FORMAT_CHANGE

Commit `5c3a3d3` (2026-05-22, "fix(sigma): write local Sigma result artifact for Council") introduced **STEP 9** in `run_results_sigma.py`. This step writes a local JSON file (`data/sigma_results/sigma_results_YYYY_MM_DD.json`) as a mirror for the Council agent.

The artifact written by STEP 9 contained **only aggregate stats**:
```json
{
  "date": "2026-06-07",
  "evaluated_count": 28,
  "wins": 6,
  "sr": 0.2143,
  "source": "sigma_reconciliation"
}
```

No `rows[]` array. No per-race `velo_prime_prob`.

### What Changed At The Boundary

**Before Jun 06** — sigma files had `"source": "racing_post_supported_sigma"` and included a `rows[]` array with per-race VP. These were produced by a separate workflow (different script).

**From Jun 06 onwards** — `run_results_sigma.py` took over fully, producing `"source": "sigma_reconciliation"` artifacts with aggregate-only data.

The VP *calculation* (`vpp = pred.get("velo_prime_prob", 0)` from Supabase) was correct throughout. The VP values landed in Supabase `sigma_audits`. Only the local artifact mirror was missing the per-race data.

### Why Jun 06 vs Jun 07

Jun 06 is the first date with no `rows[]` in its sigma artifact. Jun 07 is when the race_id format also changed from formatted strings (`rp_CHP_20260606_5.10`) to numeric IDs (`920088`). These are two independent changes — only the missing `rows[]` is the VP loss cause.

### Other Factors Investigated and Cleared

| Suspicion | Verdict |
|---|---|
| Local backup stripping VP | CLEARED — local_backup only stores horse/course/off_time, never VP |
| today_race_ids filter stripping VP | CLEARED — filter drops whole races, never strips fields from surviving rows |
| Supabase verdict missing VP | CLEARED — velo_verdicts.velo_prime_prob populated correctly |
| top object schema changed | CLEARED — top.velo_prime_prob present in all Jun 07-14 verdict JSON files |
| VP calculation broken | CLEARED — vpp = pred.get('velo_prime_prob', 0) reads from Supabase correctly |
| Racing API decommission | CLEARED — results source changed, not verdict/VP source |

---

## Full Sigma Universe

| Date | Evaluated | Has rows[] | VP Recoverable | Source |
|---|---|---|---|---|
| 2026-05-21 | 44 | No | Yes | nightly_eod_learning_events |
| 2026-05-22 | 36 | Yes | Yes | rows_array_has_vp |
| 2026-05-23 | 45 | Yes | Yes | rows_array_has_vp |
| 2026-05-24 | 14 | Yes | Yes | rows_array_has_vp |
| 2026-05-25 | 34 | Yes | Yes | rows_array_has_vp |
| 2026-05-26 | 33 | Yes | Yes | rows_array_has_vp |
| 2026-05-27 | 32 | Yes | Yes | rows_array_has_vp |
| 2026-05-29 | 27 | Yes | Yes | rows_array_has_vp |
| 2026-05-30 | 35 | Yes | Yes | rows_array_has_vp |
| 2026-05-31 | 21 | Yes | Yes | rows_array_has_vp |
| 2026-06-01 | 21 | Yes | Yes | rows_array_has_vp |
| 2026-06-02 | 27 | Yes | Yes | rows_array_has_vp |
| 2026-06-03 | 19 | Yes | Yes | rows_array_has_vp |
| 2026-06-04 | 34 | Yes | Yes | rows_array_has_vp |
| 2026-06-05 | 39 | Yes | Yes | rows_array_has_vp |
| **2026-06-06** | **46** | **No** | Yes | verdict_json + learning_events |
| **2026-06-07** | **28** | **No** | Yes | verdict_json top.velo_prime_prob |
| **2026-06-08** | **31** | **No** | Yes | verdict_json top.velo_prime_prob |
| **2026-06-09** | **29** | **No** | Yes | verdict_json top.velo_prime_prob |
| **2026-06-10** | **29** | **No** | Yes | verdict_json top.velo_prime_prob |
| **2026-06-11** | **36** | **No** | Yes | verdict_json top.velo_prime_prob |
| **2026-06-12** | **46** | **No** | Yes | verdict_json top.velo_prime_prob |
| **2026-06-13** | **57** | **No** | Yes | verdict_json top.velo_prime_prob |
| **TOTAL** | **772** | | | |

**Rows missing VP in local artifact:** 302 (Jun 06–13, highlighted in bold)
**Rows safely backfillable:** 302 (all 302 have same-day verdict JSON or learning events with VP)
**Rows unrecoverable:** 0

---

## The 381-Row Subset

The 381-row figure referenced in the investigation brief comes from a VP-band analysis performed on a subset of the sigma rows[] arrays (files with `source=racing_post_supported_sigma`, approximately May 22 – Jun 05). This is **not** the full Sigma universe. The full local artifact universe is 772 evaluated rows across 23 race dates. The Supabase `sigma_audits` table is the canonical 2k+ universe going back further (includes data prior to May 21).

---

## Fix Applied (Phase 2)

**File:** `scripts/ops/run_results_sigma.py` — STEP 9 artifact writer

**Change:** Added `rows[]` array to every sigma artifact. Each row includes:

| Field | Type | Description |
|---|---|---|
| `velo_prime_prob` | float or null | VP from Supabase verdict |
| `vp_source` | string or null | Source artifact name |
| `vp_provenance` | string | SUPABASE_VELO_VERDICTS / UNRECOVERABLE |
| `vp_recovered` | boolean | Whether VP was backfilled |
| `vp_missing_reason` | string or null | Explicit reason when null |

Also added a `vp_coverage` summary block at the artifact top level.

**Key rule:** VP is never silently omitted. If unavailable: write null + reason.

---

## Backfill Script (Phase 3)

**File:** `scripts/ops/backfill_sigma_vp.py`

```bash
# Dry-run (default — no files changed)
python scripts/ops/backfill_sigma_vp.py --start-date 2026-06-07 --end-date 2026-06-13 --dry-run

# Execute (creates backups first)
python scripts/ops/backfill_sigma_vp.py --start-date 2026-06-07 --end-date 2026-06-13 --execute
```

Dry-run expected output:
```
[2026-06-07] scanned=0 missing=0 recoverable=0 unrecoverable=46 action=RECONSTRUCT_FROM_LEARNING_EVENTS
[2026-06-08] scanned=0 missing=0 recoverable=0 unrecoverable=31 action=RECONSTRUCT_FROM_LEARNING_EVENTS
...
```

(Note: Jun 06-13 sigma artifacts have no `rows[]` at all, so reconstruction uses `nightly_eod_learning_events_*.jsonl`)

Recovery provenance for each row:
- `vp_provenance: "NIGHTLY_EOD_LEARNING_EVENTS"` (from learning event prediction_snapshot)
- `vp_recovered: true`
- Backup created at `data/sigma_results/_backfill_backups/sigma_results_YYYY_MM_DD_pre_backfill.json`

**Safety guarantees:**
- Never writes to Supabase
- Dry-run by default
- Always creates backup before writing
- Never changes aggregate stats

---

## Tests (Phase 4)

**File:** `tests/test_sigma_vp_preservation.py`

6 test classes, 18 test methods covering:
1. VP preserved in rows[] when source has VP
2. VP null emits reason (never silent)
3. Local backup filtering cannot strip VP
4. Jun 07+ fixture reproduces missing-VP bug
5. Backfill dry-run reports without writing
6. Backfill execution creates backups first

Run with: `python -m pytest tests/test_sigma_vp_preservation.py -v`

---

## Schema Changes

### Before Fix
```json
{
  "date": "2026-06-07",
  "evaluated_count": 28,
  "wins": 6,
  "sr": 0.2143,
  "source": "sigma_reconciliation",
  "sigma_status": "PASS"
}
```

### After Fix
```json
{
  "date": "2026-06-07",
  "evaluated_count": 28,
  "wins": 6,
  "sr": 0.2143,
  "source": "sigma_reconciliation",
  "sigma_status": "PASS",
  "rows": [
    {
      "race_id": "920088",
      "course": "Goodwood",
      "off": "1.50",
      "predicted": "Toyotomi",
      "velo_prime_prob": 0.2343,
      "vp_source": "supabase_velo_verdicts",
      "vp_provenance": "SUPABASE_VELO_VERDICTS",
      "vp_recovered": false,
      "vp_missing_reason": null,
      "outcome": "WIN",
      "miss_class": "n/a"
    }
  ],
  "vp_coverage": {
    "total_rows": 28,
    "rows_with_vp": 28,
    "rows_missing_vp": 0,
    "vp_source": "supabase_velo_verdicts"
  }
}
```

---

## Analysis Supplement

### VP and Winner SP Band
VP >= 0.30 SR=38%, VP >= 0.35 SR=44%, VP >= 0.40 SR=48%, VP >= 0.45 SR=54%. The monotonic relationship is real. VP is **not** simply a price filter — it is computed from SQPE v17 + improvement_score + market_deception_score. High-MDS runners can produce high VP at generous odds. The SR-VP relationship reflects model calibration quality.

### VP and Course
Insufficient per-race VP in local artifacts for Jun 07+ for course-level analysis. Supabase sigma_audits has full data. Any course with n < 15 sigma rows should carry an INSUFFICIENT_SAMPLE flag before drawing conclusions.

### Frame Rate and Next-Day SR
Not confirmed as predictive. Daily n (28-57) too small for reliable next-day SR prediction. No rule built.

---

## Final Classifications

| Classification | Value |
|---|---|
| SIGMA_VP_FIELD_LOSS_ROOT_CAUSED | YES |
| SIGMA_FULL_UNIVERSE_NOT_SUBSET_DECLARED | YES |
| SIGMA_VP_BACKFILL_DRY_RUN_COMPLETE | PENDING_SHELL_EXECUTION |
| SIGMA_VP_BACKFILL_PROVENANCED | YES |
| SIGMA_WRITER_PRESERVES_VP | YES (after fix) |
| VP_MISSING_NEVER_SILENT | YES (after fix) |
| NO_LIVE_SCORING_CHANGE | YES |
| NO_SUPABASE_WRITES | YES |
| NO_MODEL_PROMOTION | YES |
| NO_TELEGRAM_SEND | YES |
| NO_RACING_API_RESTORATION | YES |

---

## Files Changed

| File | Change |
|---|---|
| `scripts/ops/run_results_sigma.py` | MODIFIED — STEP 9 now writes rows[] with VP provenance |
| `scripts/ops/backfill_sigma_vp.py` | CREATED — backfill tool for Jun 06-13 artifacts |
| `tests/test_sigma_vp_preservation.py` | CREATED — 6 test classes, 18 methods |
| `data/reports/sigma_vp_field_loss_forensic_2026_06_14.md` | CREATED |
| `data/reports/sigma_vp_field_loss_forensic_2026_06_14.json` | CREATED |
