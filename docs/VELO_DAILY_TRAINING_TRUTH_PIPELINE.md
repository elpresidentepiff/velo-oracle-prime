# VÉLØ Daily Training Truth Pipeline

**Revision:** 2026-04-18.01 | **Status:** ACTIVE

This document defines the canonical join contract for producing the daily consolidated training truth plane. It ensures that ML retraining and Sigma audits operate on a single, universally agreed-upon historical dataset.

---

## 1. The Canonical Join Contract

The daily truth plane is built by joining `velo_verdicts` and `sigma_audits`, with optional enrichment from `velo_post_race_reviews`.

- **Primary Keys:** `race_id` is the universal anchor.
- **Base Table (Predictions):** `velo_verdicts`.
- **Truth Table (Outcomes):** `sigma_audits`.

## 2. Deduplication Policy (Latest-Row Truth)
Because VÉLØ can run multiple times per day (e.g., test runs, triggers), `velo_verdicts` often contains multiple predictions for the same `race_id`.
- **Policy:** Group by `race_id` and select the row with the latest `generated_at` timestamp. This represents the final operational truth before the off-time.

## 3. Orphan & Exclusion Policy
- **Unreconciled Races:** Any `velo_verdicts` row without a matching `sigma_audits` row is **EXCLUDED** from the training plane. A prediction without an outcome cannot be learned from.
- **Shadow/Proof Runs:** Races tagged with a non-standard `decision_tier` (e.g., `proof_run`) are retained in the dataset but must be explicitly filtered out during model retraining or financial performance audits.

## 4. The Output Contract
The pipeline (`scripts/build_training_dataset.py`) produces a flat JSON array (`training_sigma_audit_dataset.json`) where every record guarantees the following shape:
- `race_id`, `verdict_id`, `generated_at`, `fetch_timestamp`
- `decision_tier`, `confidence`, `top_pick`, `score`
- `predicted_field_size`, `actual_field_size`, `field_divergence`, `field_mutated`
- `outcome` (WIN/PLACED/MISS), `top_pick_position`
- `miss_category`, `miss_reason`, `cash_run_flag`, `doctrine_flags`
