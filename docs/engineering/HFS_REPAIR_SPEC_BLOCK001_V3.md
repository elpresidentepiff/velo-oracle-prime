# HFS Repair Specification Block 001 V3

**Status:** REVISED SPECIFICATION (V3)
**Date:** 2026-05-05
**Objective:** Reconstruct HFS Block 001 with auditable, leakage-safe doctrine signals and explicit provenance.

## 1. Corrected Feature Contracts

### A. MPI (Market Probability Index) - Runner Level
- **Nature:** Runner-level probability derived from market price.
- **Computation:**
  1. `implied_p_i = 1.0 / pre_race_odds_i`
  2. `mpi_i = implied_p_i / sum(implied_p_all_runners_in_race)`
- **Mandatory Metadata:**
  - `odds_source`: (e.g., "racing_api_standard", "betfair_bsp_proxy")
  - `odds_timestamp`: ISO 8601 string.
- **Safety Rule:** `pre_race_odds_dec` is valid only if `odds_timestamp` < `prediction_timestamp` <= `race_start_time`.
- **Leakage Status:** No timestamp means `LEAKAGE_RISK`.

### B. Chaos Bloom - Race Level
- **Nature:** Race-level market uncertainty/entropy.
- **Computation:**
  1. `H = -sum(mpi_i * ln(mpi_i))` (Shannon Entropy)
  2. `chaos_bloom = H / ln(number_of_runners)` (Normalized to 0-1)
- **Deployment:** Replicated onto every runner row within the same `race_id`.
- **Validation Gate:** Must prove `variance > 0` **across races**. Variance within a single race must be **exactly 0**.

### C. DEFAULTS Policy (Hard Gate)
- **Live/Inference:** `DEFAULTS` allowed only for degraded live display/inference fallback.
- **Training (HFS):** `DEFAULTS` are **STRICTLY FORBIDDEN** in HFS training rows.
- **Learning (G):** `DEFAULTS` must never feed Playbook G.
- **Classification:** Any row utilizing `DEFAULTS` must set:
  - `feature_quality = DEGRADED`
  - `training_safe = false`

## 2. Provenance & Traceability Fields

Every repaired row in Block 001 must populate:
- `feature_status`: (e.g., `COMPLETE`, `PARTIAL`, `ERROR`)
- `feature_quality`: (e.g., `HIGH`, `DEGRADED`, `PROXY`)
- `feature_provenance`: (e.g., `V17_REPAIR_ENGINE_V1`)
- `training_safe`: boolean
- `leakage_status`: (e.g., `CLEAN`, `LEAKAGE_RISK`, `UNVERIFIED`)
- `batch_id`: (e.g., `B001_RECON_20260505`)
- `audit_id`: (UUID)
- `reconstruction_version`: `V17_REPAIR_B3`
- `created_at`: timestamp

## 3. V17 Doctrine Wiring
- **Action:** Wire `V17FeatureExtractor().extract()` into `app/services/velo_prime_service.py`.
- **Hard Constraint:** If extraction fails for HFS reconstruction, the row must be marked `training_safe = false` and `feature_status = ERROR`. No fake data into the training set.

## 4. Validation Gates V3
The repair is successful ONLY if:
1. `mpi` variance > 0 across runners in a race.
2. `chaos_bloom` variance > 0 across the dataset, but 0 within any race.
3. `pre_race_odds_dec` timestamp proves pre-race availability.
4. `training_safe` is accurately flagged based on quality and leakage checks.

---
**Status:** SPECIFICATION ONLY. Implementation is BLOCKED until approved.
