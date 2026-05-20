# HFS Repair Specification Block 001 V2

**Status:** REVISED SPECIFICATION (V2)
**Date:** 2026-05-05
**Objective:** Reconstruct HFS Block 001 with auditable, leakage-safe doctrine signals.

## 1. Corrected Feature Contracts

### A. MPI (Market Probability Index) - Runner Level
- **Nature:** Runner-level probability derived from market price.
- **Computation:**
  1. `implied_p_i = 1.0 / pre_race_odds_i`
  2. `mpi_i = implied_p_i / sum(implied_p_all_runners_in_race)`
- **Mandatory Metadata:**
  - `odds_source`: (e.g., "racing_api_standard", "betfair_bsp_proxy")
  - `odds_timestamp`: ISO 8601 string.
- **Safety Rule:** If `odds_timestamp` is absent or post-race, the row is marked `LEAKAGE_RISK` and excluded from training.

### B. Chaos Bloom - Race Level
- **Nature:** Race-level market uncertainty/entropy.
- **Computation:**
  1. `H = -sum(mpi_i * ln(mpi_i))` (Shannon Entropy)
  2. `chaos_bloom = H / ln(number_of_runners)` (Normalized to 0-1)
- **Deployment:** Replicated onto every runner row within the same `race_id`.
- **Validation:** Must prove `variance > 0` **across races**. Variance within a single race must be **exactly 0**.

### C. Temporal Safety & Leakage Control
- **Schema Separation:**
  - `pre_race_odds_dec`: The odds used for prediction (must have pre-race timestamp).
  - `sp_dec`: Final starting price (for post-race audit/sigma only).
- **Rule:** Scoring models (`velo_prime_service.py`) are FORBIDDEN from reading `sp_dec` or `bsp_dec` during live inference.

## 2. V17 Doctrine Wiring

- **Decision:** `V17FeatureExtractor` is currently ORPHANED in the canonical backfill path.
- **Action:** Wire `V17FeatureExtractor().extract()` into `app/services/velo_prime_service.py`.
- **Hard Constraint:** 
  - `DEFAULTS` are strictly for live fallback only.
  - For HFS Block 001 reconstruction, a failure to extract history MUST result in `status: FEATURE_ERROR` and a NULL value. 
  - **No fake data in the training set.**

## 3. Schema Migration Plan (Missing Columns)

The following signals are currently missing from the `historical_feature_store` schema and require an Alembic migration:
1. `market_deception_score` (float)
2. `improvement_score` (float)
3. `trainer_score` (float)
4. `jockey_score` (float)
5. `course_score` (float)
6. `distance_score` (float)
7. `pace_profile` (string/json)
8. `field_strength` (float)
9. `market_pressure` (float)

## 4. Validation Gates V2
The repair is successful ONLY if:
1. `mpi` variance > 0 across runners in a race.
2. `chaos_bloom` variance > 0 across the dataset, but 0 within any race.
3. `pre_race_odds_dec` timestamp < `race_time`.
4. No `DEFAULTS` found in `reconstruction_version = 'V17_REPAIR_B2'`.

---
**Status:** SPECIFICATION ONLY. Implementation is BLOCKED until approved.
