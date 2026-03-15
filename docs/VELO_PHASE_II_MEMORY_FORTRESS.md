# VÉLØ Phase II — The Memory Fortress

**Date:** 15 March 2026
**CTO:** Manus AI

---

## 1. Mission

To build a permanent, queryable racing intelligence warehouse. This document outlines the complete data architecture required to transform daily race ingestion into a deep historical memory, enabling the VÉLØ engine to learn, evolve, and detect complex patterns over time.

This is the blueprint for VÉLØ's nervous system.

---

## 2. The Ingestion Schedule (The Clock)

All times are UTC. The `ingestion_scheduler.py` worker will execute these pulls without fail.

| Time | Endpoint | Target Table(s) | Purpose |
|:---|:---|:---|:---|
| **06:00** | `racecards/standard` | `races`, `runners` | Morning card pull; establish the day's baseline. |
| **09:00** | `racecards/standard` | `odds_snapshots` | T-3hrs odds snapshot. |
| **11:00** | `racecards/standard` | `odds_snapshots` | T-1hr odds snapshot. |
| **12:30** | `racecards/standard` | `odds_snapshots` | T-30min odds snapshot. |
| **13:10** | `racecards/standard` | `odds_snapshots` | T-10min odds snapshot. |
| **Post-Race** | `results/{race_id}` | `results` | Settle race, log final positions and BSP. |
| **23:00** | `horses/{horse_id}/standard` | `horses`, `sires`, `dams`, `damsires` | Nightly entity enrichment for all new IDs. |

---

## 3. The Database Spine (The Memory)

These tables form the core of the Memory Fortress. New tables are marked with `*`.

| Table | Purpose | Key Columns | Source Endpoint |
|:---|:---|:---|:---|
| `races` | Master record for each race. | `race_id`, `course`, `date`, `time`, `distance_f`, `going` | `racecards/standard` |
| `runners` | Master record for each runner in a race. | `runner_id`, `race_id`, `horse_id`, `horse_name`, `trainer_id`, `jockey_id` | `racecards/standard` |
| `* odds_snapshots` | Time-series odds data. | `race_id`, `horse_id`, `bookmaker`, `decimal`, `timestamp` | `racecards/standard` |
| `results` | Final race outcomes. | `race_id`, `horse_id`, `position`, `win_bsp` | `results/{race_id}` |
| `horses` | Static data for each unique horse. | `horse_id`, `horse_name`, `sire_id`, `dam_id` | `horses/{horse_id}/standard` |
| `trainers` | Static data for each unique trainer. | `trainer_id`, `trainer_name` | `trainers/search` |
| `jockeys` | Static data for each unique jockey. | `jockey_id`, `jockey_name` | `jockeys/search` |
| `sires` | Static data for each unique sire. | `sire_id`, `sire_name` | `sires/search` |
| `dams` | Static data for each unique dam. | `dam_id`, `dam_name` | `dams/search` |
| `damsires` | Static data for each unique damsire. | `damsire_id`, `damsire_name` | `damsires/search` |
| `* comments_archive` | Historical NLP fuel. | `horse_id`, `race_id`, `spotlight`, `comment`, `timestamp` | `racecards/standard` |
| `* gear_medical_events` | Change-event tracking. | `horse_id`, `race_id`, `headgear`, `wind_surgery`, `timestamp` | `racecards/standard` |
| `* trainer_switch_events` | Change-event tracking. | `horse_id`, `prev_trainer_id`, `new_trainer_id`, `detected_date` | `horses/{horse_id}/standard` |
| `* velo_features` | The feature factory output. | `runner_id`, `race_id`, `trainer_heat`, `wind_op_run`, `stamina_score` | Computed |
| `velo_verdicts` | Final engine output. | `race_id`, `verdict`, `confidence`, `primary_strike` | `playbook_orchestrator.py` |

---

## 4. The Raw Payload Archive (The Insurance)

Every raw JSON response from the Racing API will be stored untouched in a dedicated Supabase table or S3 bucket, keyed by endpoint and timestamp. This is non-negotiable. It provides:

- **Recovery:** Rebuild the entire database from scratch if needed.
- **Backtesting:** Test new parsers or features on historical data.
- **Audit:** Prove exactly what data the engine saw at a specific time.

---

## 5. The Feature Factory (The Nervous System)

The `feature_factory.py` module will be built to compute these derived features before any analysis. This is the bridge between raw data and VÉLØ doctrine.

- **Trainer Heat Score:** Wins/runs in the last 14 days.
- **Jockey-Trainer Combo Score:** Historical win % for the specific pairing.
- **Wind-Op Run Flag:** 1st or 2nd run after wind surgery.
- **Headgear Delta:** Impact of new/removed headgear vs. career norm.
- **Stable Switch Flag:** First run for a new trainer.
- **Breeding Stamina Score:** Computed from sire/damsire distance analysis.
- **Going/Course Suitability:** Historical performance on similar ground/track.
- **Market Steam/Drift Class:** Categorizes odds movement in the final 30 minutes.

This blueprint is the foundation for Phase II. Execution begins now.
