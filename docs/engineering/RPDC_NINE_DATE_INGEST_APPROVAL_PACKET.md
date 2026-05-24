# RPDC Nine-Date Supabase Ingest — Operator Approval Packet

**Prepared:** 2026-05-24  
**Status:** AWAITING_OPERATOR_APPROVAL — each date requires individual sign-off  
**Hard rule:** No ingest runs until operator marks the date approved below  

---

## What this packet is for

Nine scored race days (2026-05-09 to 2026-05-20) have results files locally but
zero rows in `racing_horse_runs` in Supabase. Without these rows, `build_rpdc_daily.py`
cannot generate RPDC tags for horses that ran on those days — because the tag builder
reads `racing_horse_runs` to construct each horse's career history.

Ingesting these dates would extend the RPDC chain backward, giving more horses a
prior-run history entry and improving the coverage rate on future cards.

This is **not** required for today's scoring (Option B local JSONL already covers
18,554 historical rows). This is a Supabase quality improvement only.

---

## What ingest does

Script: `scripts/ingest_results_to_horse_runs.py --date YYYY-MM-DD`

- Reads `data/results_YYYY_MM_DD.json`
- Parses runners, computes basic race facts (class, distance, going, position, SP)
- Upserts into `racing_horse_runs` (conflict key: `race_id, horse_id` — safe to re-run)
- Does NOT touch `runner_release_candidates`
- Does NOT touch `velo_verdicts`
- Does NOT change any scoring output
- Does NOT trigger any pipeline rerun

Rollback: `DELETE FROM racing_horse_runs WHERE race_date = 'YYYY-MM-DD'`

Identity risk: Low — results files use standard Racing Post horse IDs (rp_... format).
The `racing_horse_runs` table accepts rp_ IDs. No identity translation required.

---

## Per-Date Approval Table

Each date must be approved independently before its ingest runs.

---

### Date 1 — 2026-05-09 (Saturday)

| Field | Value |
|---|---|
| Results file | `data/results_2026_05_09.json` — EXISTS |
| Races in file | 87 |
| Expected horse_runs rows | ~881 |
| Current horse_runs rows | 0 |
| Identity risk | LOW |
| Rollback | `DELETE FROM racing_horse_runs WHERE race_date = '2026-05-09'` |
| Why ingest? | Extends history for horses that ran on this day; improves RPDC match rate for future cards |
| Conflict on re-run | SAFE — upsert on (race_id, horse_id) |

**OPERATOR APPROVAL:** `[ ]` — Sign off by writing your initials and date

---

### Date 2 — 2026-05-10 (Sunday)

| Field | Value |
|---|---|
| Results file | `data/results_2026_05_10.json` — EXISTS |
| Races in file | 32 |
| Expected horse_runs rows | ~345 |
| Current horse_runs rows | 0 |
| Identity risk | LOW |
| Rollback | `DELETE FROM racing_horse_runs WHERE race_date = '2026-05-10'` |
| Why ingest? | Sunday card — Sunday runners often reappear within 1-2 weeks. History improves mark compression scoring. |
| Conflict on re-run | SAFE — upsert on (race_id, horse_id) |

**OPERATOR APPROVAL:** `[ ]` — Sign off by writing your initials and date

---

### Date 3 — 2026-05-12 (Tuesday)

| Field | Value |
|---|---|
| Results file | `data/results_2026_05_12.json` — EXISTS |
| Races in file | 48 |
| Expected horse_runs rows | ~457 |
| Current horse_runs rows | 0 |
| Identity risk | LOW |
| Rollback | `DELETE FROM racing_horse_runs WHERE race_date = '2026-05-12'` |
| Why ingest? | Mid-week flat runners frequently reappear by week 2-3. |
| Conflict on re-run | SAFE — upsert on (race_id, horse_id) |

**OPERATOR APPROVAL:** `[ ]` — Sign off by writing your initials and date

---

### Date 4 — 2026-05-13 (Wednesday)

| Field | Value |
|---|---|
| Results file | `data/results_2026_05_13.json` — EXISTS |
| Races in file | 59 |
| Expected horse_runs rows | ~564 |
| Current horse_runs rows | 0 |
| Identity risk | LOW |
| Rollback | `DELETE FROM racing_horse_runs WHERE race_date = '2026-05-13'` |
| Why ingest? | High-volume mid-week day — 59 races. Good history depth. |
| Conflict on re-run | SAFE — upsert on (race_id, horse_id) |

**OPERATOR APPROVAL:** `[ ]` — Sign off by writing your initials and date

---

### Date 5 — 2026-05-14 (Thursday) ⚠️ Racing API Decommission Day

| Field | Value |
|---|---|
| Results file | `data/results_2026_05_14.json` — EXISTS |
| Races in file | 45 |
| Expected horse_runs rows | ~468 |
| Current horse_runs rows | 0 |
| Identity risk | LOW |
| Rollback | `DELETE FROM racing_horse_runs WHERE race_date = '2026-05-14'` |
| Why ingest? | Racing API was decommissioned on this date. Last day with Racing API-sourced results. Ingesting this gives the chain a final API-era reference point. |
| Special note | Results file was downloaded before decommission. Data is complete. |
| Conflict on re-run | SAFE — upsert on (race_id, horse_id) |

**OPERATOR APPROVAL:** `[ ]` — Sign off by writing your initials and date

---

### Date 6 — 2026-05-15 (Friday)

| Field | Value |
|---|---|
| Results file | `data/results_2026_05_15.json` — EXISTS |
| Races in file | 52 |
| Expected horse_runs rows | ~601 |
| Current horse_runs rows | 0 |
| Identity risk | LOW |
| Rollback | `DELETE FROM racing_horse_runs WHERE race_date = '2026-05-15'` |
| Why ingest? | First post-Racing-API day. Results were sourced from RP. Ingesting confirms RP-sourced results land correctly in racing_horse_runs. |
| Conflict on re-run | SAFE — upsert on (race_id, horse_id) |

**OPERATOR APPROVAL:** `[ ]` — Sign off by writing your initials and date

---

### Date 7 — 2026-05-16 (Saturday)

| Field | Value |
|---|---|
| Results file | `data/results_2026_05_16.json` — EXISTS |
| Races in file | 60 |
| Expected horse_runs rows | ~676 |
| Current horse_runs rows | 0 |
| Identity risk | LOW |
| Rollback | `DELETE FROM racing_horse_runs WHERE race_date = '2026-05-16'` |
| Why ingest? | High-volume Saturday card. Horses from this day are most likely to reappear within 14 days. Highest-priority ingest date. |
| Conflict on re-run | SAFE — upsert on (race_id, horse_id) |

**OPERATOR APPROVAL:** `[ ]` — Sign off by writing your initials and date

---

### Date 8 — 2026-05-18 (Monday)

| Field | Value |
|---|---|
| Results file | `data/results_2026_05_18.json` — EXISTS |
| Races in file | 31 |
| Expected horse_runs rows | ~336 |
| Current horse_runs rows | 0 |
| Identity risk | LOW |
| Rollback | `DELETE FROM racing_horse_runs WHERE race_date = '2026-05-18'` |
| Why ingest? | Bank Holiday Monday card — typically higher-class entries. |
| Conflict on re-run | SAFE — upsert on (race_id, horse_id) |

**OPERATOR APPROVAL:** `[ ]` — Sign off by writing your initials and date

---

### Date 9 — 2026-05-20 (Wednesday) ⚠️ Partial results file

| Field | Value |
|---|---|
| Results file | `data/results_2026_05_20.json` — EXISTS |
| Races in file | 32 |
| Expected horse_runs rows | ~78 (placed finishers only — results file stores finishers, not full field) |
| Runner snapshots | 3 × JSONL at data/runner_snapshots_2026_05_20_*.jsonl (269 rows each — full field) |
| Current horse_runs rows | 0 |
| Identity risk | MODERATE — results file has 78 runners but snapshots have 269. The 191 gap are non-placed runners not in results JSON. |
| Rollback | `DELETE FROM racing_horse_runs WHERE race_date = '2026-05-20'` |
| Why ingest? | Most recent eligible date. Horses from May 20 are most likely to appear on May 24-30 cards. High recency value. |
| Special note | Only placed finishers will be ingested from results file. Non-placed runners from this day will lack history entry. This is a known limitation of the results-file-only ingest path. |
| Conflict on re-run | SAFE — upsert on (race_id, horse_id) |

**OPERATOR APPROVAL:** `[ ]` — Sign off by writing your initials and date

---

## Ingest Order (if multiple dates approved)

Run in chronological order to ensure each day's results are available as history
for the next day's RPDC build:

```bash
# Activate venv first
source venv/bin/activate

# Run each approved date in order:
PYTHONPATH=. python scripts/ingest_results_to_horse_runs.py --date 2026-05-09
PYTHONPATH=. python scripts/ingest_results_to_horse_runs.py --date 2026-05-10
PYTHONPATH=. python scripts/ingest_results_to_horse_runs.py --date 2026-05-12
PYTHONPATH=. python scripts/ingest_results_to_horse_runs.py --date 2026-05-13
PYTHONPATH=. python scripts/ingest_results_to_horse_runs.py --date 2026-05-14
PYTHONPATH=. python scripts/ingest_results_to_horse_runs.py --date 2026-05-15
PYTHONPATH=. python scripts/ingest_results_to_horse_runs.py --date 2026-05-16
PYTHONPATH=. python scripts/ingest_results_to_horse_runs.py --date 2026-05-18
PYTHONPATH=. python scripts/ingest_results_to_horse_runs.py --date 2026-05-20

# After ingest, rebuild RPDC tags for the ingested dates:
# (Only if you want to populate runner_release_candidates retroactively)
# Each date needs per-approval for build_rpdc_daily too.
```

---

## What ingest does NOT do

- Does NOT run scoring (run_prime_today.py not triggered)
- Does NOT regenerate verdicts
- Does NOT write to velo_verdicts
- Does NOT publish to Telegram
- Does NOT update runner_release_candidates automatically
- Does NOT change any live model weights or routing rules
- Does NOT approve Option A (rpdc_horse_memory table) — that remains a separate Council decision

---

## Post-Ingest Verification

After any approved ingest, verify with:

```bash
# Count rows added
PYTHONPATH=. python -c "
from scripts.ops.supabase_client import get_client
sb = get_client()
result = sb.table('racing_horse_runs').select('race_date', count='exact').eq('race_date', 'YYYY-MM-DD').execute()
print('Rows inserted:', result.count)
"

# Rollback if something looks wrong:
# DELETE FROM racing_horse_runs WHERE race_date = 'YYYY-MM-DD'
```

---

## Classification

```
STATUS:                 AWAITING_OPERATOR_APPROVAL
SUPABASE_MIGRATION:     NOT APPROVED
OLD_VERDICTS_MUTATION:  NOT APPROVED
SCORING_CHANGE:         NONE
MODEL_CHANGE:           NONE
OPTION_B_BRIDGE:        APPROVED (separate — load_rpdc_memory.py)
OPTION_A_TABLE:         NOT APPROVED (separate Council decision)
```
