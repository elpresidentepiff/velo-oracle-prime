# VÉLØ HK Source Audit — Racing API Field Availability Matrix
**Date:** 2026-03-23
**Purpose:** Confirm what the Racing API actually provides for HK vs what is missing

---

## HK Course Map

| Course | Course ID | Region | Surface |
|---|---|---|---|
| Happy Valley | `crs_10296` | Hong Kong | Turf/Polytrack |
| Sha Tin | `crs_10816` | Hong Kong | Turf/Polytrack |

**Course count:** 2 (small, clean universe — easier to model than 188-course France)
**GB courses:** 69 | **France courses:** 188 | **HK courses:** 2

---

## HK Field Availability Matrix

| Data Field | Available? | Source | Notes |
|---|---|---|---|
| **Race metadata** ||||
| race_id | ✅ | racecards | Stable ID format |
| course | ✅ | racecards | Happy Valley / Sha Tin |
| region | ✅ | racecards | "Hong Kong" |
| date | ✅ | racecards | YYYY-MM-DD |
| off_time | ✅ | racecards | HKT = UTC+8 |
| distance_f | ✅ | racecards | Furlongs |
| race_class | ✅ | racecards | HK class system |
| going | ✅ | racecards | "Turf: Good" etc |
| prize | ✅ | racecards | HKD |
| field_size | ✅ | racecards | Typical 12-14 |
| **Runner snapshot** ||||
| horse_id | ✅ | racecards | Stable ID |
| horse_name | ✅ | racecards | |
| trainer_id | ✅ | racecards | |
| trainer_name | ✅ | racecards | |
| jockey_id | ✅ | racecards | |
| jockey_name | ✅ | racecards | |
| draw | ✅ | racecards | Barrier/draw position |
| weight | ✅ | racecards | lbs |
| age | ✅ | racecards | |
| form | ✅ | racecards | e.g. "1-232" |
| rpr | ✅ | racecards | Racing Post Rating |
| ts | ✅ | racecards | Topspeed rating |
| or_rating | ✅ | racecards | Official Rating |
| odds (decimal) | ✅ | racecards | Nested list — first=open, last=live |
| fav_flag | ⚠️ | racecards | Sometimes present, not always |
| headgear | ✅ | racecards | Blinkers, cheek pieces |
| comment | ✅ | racecards | Racing Post comment |
| **Results** ||||
| finish_position | ✅ | results | Integer |
| sp | ✅ | results | Starting price |
| beaten_distance | ✅ | results | e.g. "½L", "1¼L" |
| is_winner | ✅ | results | Boolean |
| is_placed | ✅ | results | Boolean |
| result_status | ✅ | results | "finished", "PU", "F", "CO" |
| dividends | ⚠️ | results | Win/place dividends — may be in payload |
| **Trainer stats** ||||
| trainer analysis (courses) | ✅ | trainers/{id}/analysis/courses | Standard plan ✅ |
| trainer analysis (distances) | ✅ | trainers/{id}/analysis/distances | Standard plan ✅ |
| trainer analysis (jockeys) | ✅ | trainers/{id}/analysis/jockeys | Standard plan ✅ |
| trainer analysis (owners) | ✅ | trainers/{id}/analysis/owners | Standard plan ✅ |
| trainer analysis (horse-age) | ✅ | trainers/{id}/analysis/horse-age | Standard plan ✅ |
| trainer results (full) | ❌ | trainers/{id}/results | **Pro plan only** |
| **Jockey stats** ||||
| jockey analysis (courses) | ✅ | jockeys/{id}/analysis/courses | Standard plan ✅ |
| jockey analysis (distances) | ✅ | jockeys/{id}/analysis/distances | Standard plan ✅ |
| jockey analysis (trainers) | ✅ | jockeys/{id}/analysis/trainers | Standard plan ✅ |
| jockey analysis (owners) | ✅ | jockeys/{id}/analysis/owners | Standard plan ✅ |
| jockey results (full) | ❌ | jockeys/{id}/results | **Pro plan only** |
| **Horse history** ||||
| horse standard profile | ✅ | horses/{id}/standard | Standard plan ✅ |
| horse distance/times | ✅ | horses/{id}/analysis/distance-times | Standard plan ✅ |
| horse results (full) | ❌ | horses/{id}/results | **Pro plan only** |
| **Market data** ||||
| odds (pre-race) | ✅ | racecards runners[].odds | Decimal odds list |
| odds timestamp | ⚠️ | racecards | Not explicit — assume pre-race only |
| market rank | ⚠️ | racecards | Can derive from sorted odds |
| live odds (in-race) | ❌ | not in racecards | No live odds endpoint |
| **Historical backfill** ||||
| Past racecards (yesterday) | ✅ | racecards API (today only, no date filter) | Can use daily accumulation |
| Past results | ✅ | results API (today only) | Can use daily accumulation |
| Horse past runs | ⚠️ | Build from daily results | **Pro workaround: accumulate from hk_results** |
| Trainer historical | ✅ | trainer analysis endpoints | Standard plan |
| Jockey historical | ✅ | jockey analysis endpoints | Standard plan |

---

## Critical Gaps

### Gap 1: Horse Full Results History — Pro Only
`/v1/horses/{id}/results` returns **401 Pro Plan Required**.
**Impact:** Cannot get a horse's full run history in one call.
**Workaround:** Build `hk_horse_history` incrementally from daily `hk_results`. Each race day adds to each horse's history. After 90 days of daily ingestion, horses that run regularly will have 15-20+ historical runs.

### Gap 2: Trainer/Jockey Full Results — Pro Only
Same Pro-plan restriction applies.
**Workaround:** Use the trainer/jockey analysis endpoints (courses, distances, jockeys, owners) which ARE available on Standard. These give aggregate stats without individual race results.

### Gap 3: No Date Filter on racecards/results
The Racing API returns only **today's** races. No historical date parameter available on Standard plan.
**Workaround:** Daily accumulation. Run HK ingest daily. After 90 days, you have 90 days of HK history. No backfill of old dates possible without Pro plan.

### Gap 4: Live Odds Not Available
No in-race or live-odds endpoint.
**Workaround:** Pre-race odds from racecard `odds[]` array. Can capture open and close odds for market analysis.

---

## HK Ingest Reality Check

**What you CAN build with Standard plan:**
- Daily racecards for HK (2 courses, ~3-5 race meetings/week)
- Daily results with SP and finishing positions
- Runner snapshots with odds, draw, weight, trainer/jockey
- Trainer analysis (courses, distances, jockeys)
- Jockey analysis (courses, trainers, owners)
- Horse history — built incrementally from daily results (not from Pro API)

**What you CANNOT build without Pro:**
- Horse full historical results in one call
- Trainer/Jockey full results in one call
- Historical backfill for dates before today

**Bottom line:** Standard plan is sufficient to build a working HK research spine via daily accumulation. It just takes 90 days to get 90 days of history, rather than backfilling instantly.

---

## HK Racing Schedule (UTC Reference)

HK races run HKT = UTC+8.

| HK Day | HKT | UTC | Day |
|---|---|---|---|
| Wednesday Evening | 19:15–23:30 | 11:15–15:30 | Wed |
| Friday Evening | 19:30–23:45 | 11:30–15:45 | Fri |
| Saturday Afternoon | 12:30–17:00 | 04:30–09:00 | Sat |
| Saturday Evening | 18:30–23:59 | 10:30–15:59 | Sat |
| Sunday Afternoon | 12:30–18:00 | 04:30–10:00 | Sun |

**Optimal daily ingest window: 08:00–09:00 UTC**
- Catches Saturday/Sunday afternoon meetings that ended ~09:00 UTC previous day
- Wednesday/Friday evening meetings ended ~15:30 UTC previous day — definitely available
- Results are confirmed by this time
