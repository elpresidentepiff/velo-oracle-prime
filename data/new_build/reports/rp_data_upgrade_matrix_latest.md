# RP Data Upgrade Matrix

Generated: 2026-05-25 | Trust policy: ARCHIVE_CONTEXT_ONLY_NOT_SCORING

This matrix compares what each data source provides for horse shape analysis.

---

## Source Summary

| Source | Coverage |
|--------|----------|
| Race-day RP profiles | 7 dates captured, 1-70 horses per day |
| Race shape form history | May 26-27 only: 161 horses, 2,228 runs |
| Racing API racecards | 36 files, 1,654 races |
| Racing API results | 62 files, 2,742 races |
| Raceform parquets | raceform_clean.parquet + raceform_v17_features.parquet (unaudited) |
| RPDC backfill | 18,554 rows |

---

## Field-by-Field Comparison

| Field | Race-Day Profiles | Form History | Racing API | Best Source | Confidence |
|-------|-------------------|--------------|------------|-------------|------------|
| Horse identity | GOOD | GOOD | GOOD | racing_api (numeric IDs) | GOOD |
| Run frequency | PARTIAL | **GOOD** | PARTIAL | **form_history** | GOOD |
| Layoff patterns | PARTIAL | **GOOD** | MISSING | **form_history** | GOOD |
| Course history | MISSING | **GOOD** | GOOD | **form_history** (career) | GOOD |
| Course switching | MISSING | **GOOD** | PARTIAL | **form_history** | GOOD |
| Distance switching | MISSING | **GOOD** | PARTIAL | **form_history** | GOOD |
| Jockey per run | PARTIAL | **GOOD** | PARTIAL | **form_history** | GOOD |
| SP history | MISSING | **GOOD** | GOOD | **form_history** (career) | GOOD |
| Win/place/fail rate | PARTIAL | **GOOD** | GOOD | **form_history** | GOOD |
| Field size context | MISSING | **GOOD** | PARTIAL | **form_history** | GOOD |
| Beaten margin | MISSING | **GOOD** | GOOD | **form_history** | GOOD |
| Course affinity | MISSING | **GOOD** | PARTIAL | **form_history** | GOOD |
| Going history | MISSING | **GOOD** | GOOD | **form_history** (career) | GOOD |
| Trainer current | **GOOD** | MISSING | GOOD | race_day_profiles | GOOD |
| Trainer per-run history | MISSING | MISSING | PARTIAL | racing_api results | PARTIAL |
| Class / race type | PARTIAL | MISSING | **GOOD** | racing_api | PARTIAL |
| TopSpeed (TS) | PARTIAL | **GOOD** | GOOD | **form_history** (career TS) | GOOD |
| RPR rating | archive-only | archive-only | archive-only | **BANNED from predictor** | BANNED |
| Official Rating history | GOOD | **GOOD** | GOOD | form_history (career OR progression) | GOOD |
| Owner | GOOD | MISSING | GOOD | race_day / racing_api | GOOD |
| Pedigree | **GOOD** | MISSING | GOOD | race_day_profiles (has avg win dist) | GOOD |
| Headgear | PARTIAL | **PARTIAL** | PARTIAL | form_history (shows sequence) | PARTIAL |
| Draw | GOOD | MISSING | GOOD | racing_api | GOOD |
| Video URL | MISSING | **GOOD** | MISSING | form_history (exclusive) | GOOD |
| Trainer quotes/intent | **GOOD** | MISSING | MISSING | **race_day_profiles** (exclusive) | GOOD |
| Newspaper tip count | GOOD | MISSING | MISSING | race_day_profiles | GOOD |

---

## Key Upgrade: Form History Beyond Last-6

Race-day profiles and Racing API racecard data only carry `form_figures` (a string like "1-211-") showing the last 6 runs symbolically. The full form history provides:

- **Full career run sequence** — up to 88 runs, going back to 2018
- **SP per run** — enables career SP trajectory (was horse well fancied historically?)
- **Position + field_size** — career form profile derivable
- **Beaten margin** — quantifies run quality
- **Jockey per run** — career jockey continuity/change signal
- **Course per run** — course specialist vs nomad
- **Distance per run** — distance preference derivable
- **Going per run** — going preference derivable
- **TS per run** — career speed figure trajectory
- **OR per run** — Official Rating career progression (class level movement)
- **result_type** — WIN/PLACED/LOSS per run (clean categorical target derivation)
- **Winner identity** — quality of opposition faced

## What Is Still Missing Even With Form History

- **Trainer per-run history** — who trained the horse for each career run (only current trainer known)
- **Class level per run** — what class was each race (needs Racing API results join)
- **Race type per run** — Flat/NH/Chase etc per run (not in form table cells)
- **Prize money** — not scraped

---

No live VELO or Shadow VELO touched. All form history is ARCHIVE_CONTEXT_ONLY_NOT_SCORING.
