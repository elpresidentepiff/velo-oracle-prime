# Dashboard Daily Predictions Publisher V1

**Status:** LIVE  
**Version:** dashboard_publisher_v1  
**First published:** 2026-05-05  
**Classification:** `AUDIT_EVIDENCE` — read-only, no scoring/model/router/staking side effects

---

## What It Does

Reads the day's VÉLØ predictions and publishes a normalized per-runner payload to a JSON staging file. The dashboard can then serve this file via `/api/dashboard-daily`.

This publishes **all predictions** — every runner in every scored race, not only the top pick.

---

## Source of Truth

| Priority | Source | Content | When used |
|---|---|---|---|
| 1 | Supabase `velo_verdicts.full_analysis.predictions` | All runners per race | When Supabase credentials present |
| 2 | `data/velo_prime_verdicts_YYYY_MM_DD.json` | Top pick per race only | Fallback when Supabase unavailable |

The local JSON is written by `scripts/run_prime_today.py` step 6 (best-effort backup). The Supabase `full_analysis.predictions` JSONB column contains all scored runners for each race.

---

## Destination

```
data/dashboard_daily_predictions_YYYYMMDD.json
```

This is a JSON staging file — no database writes, no schema changes. The file is overwritten on each run (idempotent).

---

## Payload Contract

One object per runner:

```json
{
  "publish_date": "2026-05-05",
  "race_id": "rac_...",
  "race_time": "14:00",
  "course": "Ayr",
  "race_name": "...",
  "runner_id": "hrs_...",
  "horse_id": "hrs_...",
  "horse_name": "Stoneacre Joe",
  "runner_number": null,
  "draw": null,
  "jockey": null,
  "trainer": null,
  "odds": null,
  "sp": null,
  "bsp": null,
  "velo_prime_prob": 0.3008,
  "decision_tier": "B",
  "rank": 1,
  "verdict": null,
  "vp30": true,
  "tier_a": false,
  "vp30_tier_a": false,
  "market_deception_score": 0.1937,
  "mds_high": false,
  "improvement_score": 0.3384,
  "improve_high": false,
  "place_prob": 0.7443,
  "b_tier_low_vp_suppress": false,
  "power_anchor": null,
  "story_anchor": null,
  "mpi": null,
  "chaos_bloom": null,
  "narrative_disruption": null,
  "sidecars": { ... },
  "feature_presence": { ... },
  "model_version": "velo_prime_v1",
  "run_id": "uuid",
  "generated_at": "2026-05-05T06:...",
  "idempotency_key": "2026-05-05:rac_...:hrs_..."
}
```

### Always-Null Fields

These fields are null because they are not stored in the prediction pipeline. They would require enrichment from the raw racing API runner objects, which are not carried through to `full_analysis.predictions`.

| Field | Reason |
|---|---|
| `runner_number` | Not stored in prediction dict |
| `draw` | `draw_num` used in feature engineering but not output |
| `jockey` | Jockey intent signal used, not name |
| `trainer` | Trainer intent signal used, not name |
| `odds`, `sp` | `sp_dec` used in scoring but not output |
| `bsp` | Betfair BSP not ingested |
| `mpi` | Not computed in current pipeline |
| `chaos_bloom` | Not computed in current pipeline |
| `narrative_disruption` | Not computed in current pipeline |
| `power_anchor` | POWER_ANCHOR_MODE is an execution directive, not a sidecar |
| `story_anchor` | Directive-level concept, not a sidecar field |
| `verdict` | No single-word verdict field in current schema |

---

## Flag Thresholds

All thresholds sourced directly from `scripts/run_prime_today.py` (`_signal_stack_badges_and_risks` and `SIGNAL_STACK_EVIDENCE`). None invented here.

| Flag | Logic | Source line |
|---|---|---|
| `vp30` | `velo_prime_prob >= 0.30` | run_prime_today.py:709 |
| `tier_a` | `decision_tier == "A"` | run_prime_today.py:709 |
| `vp30_tier_a` | `vp >= 0.30 AND tier == "A"` | run_prime_today.py:709 |
| `mds_high` | `market_deception_score > 0.50` | run_prime_today.py:711 |
| `improve_high` | `improvement_score > 0.40` | run_prime_today.py:714 |
| `b_tier_low_vp_suppress` | `tier == "B" AND vp < 0.30` | run_prime_today.py:717 |

---

## Scripts

### Publisher
```bash
source venv/bin/activate
PYTHONPATH=. python scripts/publish_daily_predictions_to_dashboard.py --date YYYY-MM-DD
```

Defaults to today (UTC) if `--date` omitted.

### Auto-publish (after scoring)
Set `VELO_DASHBOARD_PUBLISH_ENABLED=true` in `.env` or Railway env vars.  
The flag is checked inside any downstream hook — the script always runs when called directly regardless of this flag.

---

## API Endpoint

```
GET /api/dashboard-daily?date=YYYY-MM-DD
```

Returns predictions grouped by race:

```json
{
  "meta": { "races": 32, "runners": 256, "source": "supabase+local_json", ... },
  "races": [
    {
      "race_id": "rac_...",
      "race_time": "14:00",
      "course": "Ayr",
      "decision_tier": "B",
      "runners": [ { ...per runner payload... }, ... ]
    }
  ]
}
```

Falls back to most recent available file if exact date not found. Returns 404 with rerun hint if no file exists.

---

## Dashboard Display

Panel **C · DAILY PREDICTIONS — ALL RUNNERS** is in `app/static/dashboard/index.html`.

- Collapsed by default (lazy-loads on expand)
- Shows all races, sorted by race time
- Per runner: rank, horse name, VP%, MDS, IMP, PLACE_P, tier
- Badges: VP30_TIER_A, MDS_HIGH, TIER_A, VP30, IMP_HIGH, B_LOW_VP
- Expandable sidecar JSON per runner
- Summary counts: runners, tier A, VP30, VP30_TIER_A, MDS_HIGH, races

---

## Audit File

```
data/dashboard_daily_predictions_publish_audit_v1.json
```

Overwritten on each run. Contains:
- Source table/file used
- Destination path
- Rows read / published / skipped
- VP30 / Tier A / VP30_TIER_A / MDS_HIGH counts
- Missing sidecar fields (always-null fields + reasons)
- Exact rerun command
- Confirmation that scoring/model/router/staking were untouched

---

## Hard Rules (Permanent)

```
NO scoring changes
NO model changes
NO Playbook E
NO staking changes
NO router changes
NO fabricated sidecars
NO invented thresholds
Idempotent: safe to re-run at any time
```

---

## Evidence Basis for Flags

From 49-day unified audit (2026-04-28):

| Signal | n | SR | Frame |
|---|---|---|---|
| VP30 + Tier A | 162 | 40.1% | 77.2% |
| MDS > 0.50 | 31 | 54.8% | 96.8% |
| IMP > 0.40 | 62 | 43.5% | 82.3% |
| Tier B VP<0.30 | 272 | 16.9% | 44.1% |
