# RPDC Mission Control Chain Requirements

**Classification:** `CHAIN_REQUIREMENTS`  
**Status:** DEFINED — pending implementation  
**Date:** 2026-05-24  
**Authority:** El Presidente  
**Reference:** `docs/engineering/RPDC_SUPABASE_BACKFILL_PROPOSAL.md`  
**Reference:** `docs/engineering/RPDC_TAGGING_ASSET_INVENTORY.md`

---

## Purpose

Mission control (`scripts/ops/velo_morning_cockpit.py`, Railway health checks, and operator dashboards) must be able to answer the following questions about the RPDC chain at any time:

1. Is the horse history layer current? (`racing_horse_runs` freshness)
2. Were RPDC tags built for today's runners? (`runner_release_candidates` freshness)
3. What coverage did scoring get? (RPDC attach rate on today's verdicts)
4. Are there gaps in the historical chain? (dates missing from `racing_horse_runs`)

Without these fields, chain failures like the May 8–May 24 degradation go undetected until a manual audit is triggered.

---

## Required Status Fields

The following fields must be present in every mission control snapshot (daily and live):

### RPDC Chain Health Block

```json
{
  "rpdc_chain": {
    "horse_runs_last_ingest_date": "YYYY-MM-DD",
    "horse_runs_staleness_days": 0,
    "horse_runs_status": "CURRENT | STALE_1D | STALE_2D | STALE_7D+ | EMPTY",
    "rpdc_candidates_last_build_date": "YYYY-MM-DD",
    "rpdc_candidates_staleness_days": 0,
    "rpdc_candidates_status": "CURRENT | STALE | EMPTY",
    "rpdc_attach_rate_today": 0.0,
    "rpdc_attach_rate_status": "HIGH | LOW | NONE | NOT_SCORED_YET",
    "rpdc_chain_status": "HEALTHY | DEGRADED | BROKEN | UNKNOWN"
  }
}
```

### Field Definitions

| Field | Source | Threshold |
|---|---|---|
| `horse_runs_last_ingest_date` | `MAX(run_date) FROM racing_horse_runs` | Must equal yesterday |
| `horse_runs_staleness_days` | Today minus horse_runs_last_ingest_date | Alert if > 1 |
| `horse_runs_status` | Derived from staleness | STALE_1D = warn, STALE_2D+ = alert, EMPTY = critical |
| `rpdc_candidates_last_build_date` | `MAX(run_date) FROM runner_release_candidates` | Must equal today |
| `rpdc_candidates_staleness_days` | Today minus rpdc_candidates_last_build_date | Alert if > 0 |
| `rpdc_candidates_status` | Derived | Alert if not CURRENT |
| `rpdc_attach_rate_today` | % of today's verdicts with `rpdc_lookup_status = "attached"` | Warn if < 50%, alert if 0% |
| `rpdc_chain_status` | Derived aggregate | HEALTHY = all current. DEGRADED = ≥1 warn. BROKEN = critical. |

---

## RPDC Chain Status Logic

```
HEALTHY:   horse_runs_staleness ≤ 1
           AND rpdc_candidates_staleness = 0
           AND rpdc_attach_rate > 0

DEGRADED:  horse_runs_staleness = 2 OR rpdc_candidates_staleness = 1
           OR rpdc_attach_rate < 50%

BROKEN:    horse_runs is EMPTY
           OR rpdc_candidates is EMPTY
           OR horse_runs_staleness > 7
           OR rpdc_attach_rate = 0.0 on a day with > 0 verdicts

UNKNOWN:   Cannot query Supabase (no credentials or timeout)
```

---

## improvement_score Variance Requirement

The May 17–24 degradation was caused by `improvement_score` being excluded from the ensemble due to flatline input features (all None). Mission control must track this:

```json
{
  "improvement_score_variance": {
    "variance_today": 0.0,
    "status": "ACTIVE | FLATLINE | EXCLUDED | UNAVAILABLE",
    "exclusion_reason": null,
    "alert_if_flatline": true
  }
}
```

| Status | Condition |
|---|---|
| ACTIVE | improvement_score variance > 1e-6 across today's scored races |
| FLATLINE | improvement_score variance ≤ 1e-6 (zero-variance kill switch fired) |
| EXCLUDED | improvement_score not in active_components for > 80% of races |
| UNAVAILABLE | No verdicts available yet for today |

---

## Repair Runbook (embed in mission control output)

When `rpdc_chain_status` is `DEGRADED` or `BROKEN`, mission control must print the exact repair commands:

```
⚠ RPDC_CHAIN_DEGRADED — {date}

  horse_runs_staleness    = {N} days  (last: {last_date})
  rpdc_candidates_stale   = {N} days  (last: {last_date})
  rpdc_attach_rate_today  = {pct}%

  Repair sequence:
    1. source venv/bin/activate
    2. PYTHONPATH=. python scripts/ops/run_results_sigma.py --date {yesterday}
    3. PYTHONPATH=. python scripts/ops/ingest_results_to_horse_runs.py --date {yesterday}
    4. PYTHONPATH=. python scripts/ops/build_rpdc_daily.py --date {today}
    5. Rerun scoring if today's window is still open.
```

---

## Implementation Plan

### Phase 1 — Read from Supabase (no new table, low risk)

Add a `_rpdc_chain_health()` function to `scripts/ops/velo_morning_cockpit.py` that:
1. Queries `MAX(run_date)` from `racing_horse_runs`
2. Queries `MAX(run_date)` from `runner_release_candidates`
3. Reads today's verdict JSONL for attach rate
4. Computes `rpdc_chain_status`
5. Prints the block and injects into the mission control JSON

No new Supabase tables. No schema changes. Read-only.

### Phase 2 — rpdc_horse_memory table (requires Council approval)

If Option A from `RPDC_SUPABASE_BACKFILL_PROPOSAL.md` is approved, the `rpdc_horse_memory` table provides an additional status field:

```json
{
  "rpdc_horse_memory": {
    "total_horses": 14810,
    "last_updated": "YYYY-MM-DD",
    "staleness_days": 0,
    "status": "CURRENT | STALE | EMPTY"
  }
}
```

---

## What Must NOT Be Included in Mission Control

- Do not print RPDC tags for individual horses (privacy / operational risk)
- Do not print `rpdc_cash_window_flag` for live runners before race starts
- Do not print attach rate by horse name — aggregate only
- Do not compare current RPDC to historical verdicts in this block (separate audit script)

---

```
STATUS:                   DEFINED — pending implementation in velo_morning_cockpit.py
REQUIRED_TABLES:          racing_horse_runs (read), runner_release_candidates (read)
NEW_TABLE_REQUIRED:       NO (Phase 1) / YES rpdc_horse_memory (Phase 2)
SCORING_CHANGE:           NONE
MODEL_CHANGE:             NONE
TELEGRAM_CHANGE:          NONE
LIVE_STATE_MUTATION:      NONE
COUNCIL_APPROVAL_REQ:     Phase 2 only
```
