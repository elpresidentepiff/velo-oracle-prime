# HFS Schema Verification V1

**Date:** 2026-05-05
**Actual Schema Source:** Supabase REST API `historical_feature_store` inspection.

## 1. Actual vs Required Comparison

| Column Name | Status (Actual) | Status (Required) | Data Type | Action Required |
|---|---|---|---|---|
| `id` | PRESENT | Mandatory | bigint | None |
| `race_id` | PRESENT | Mandatory | text | None |
| `horse_id` | PRESENT | Mandatory | text | None |
| `mpi` | PRESENT | Mandatory | double precision | Reconstruction |
| `chaos_bloom` | PRESENT | Mandatory | double precision | Reconstruction |
| `market_deception_score` | **MISSING** | Mandatory | float | **Add via Migration** |
| `improvement_score` | **MISSING** | Mandatory | float | **Add via Migration** |
| `trainer_score` | **MISSING** | Mandatory | float | **Add via Migration** |
| `jockey_score` | **MISSING** | Mandatory | float | **Add via Migration** |
| `course_score` | **MISSING** | Mandatory | float | **Add via Migration** |
| `distance_score` | **MISSING** | Mandatory | float | **Add via Migration** |
| `pace_profile` | **MISSING** | Mandatory | text/json | **Add via Migration** |
| `field_strength` | **MISSING** | Mandatory | float | **Add via Migration** |
| `market_pressure` | **MISSING** | Mandatory | float | **Add via Migration** |
| `pre_race_odds_dec` | **MISSING** | Mandatory | float | **Add via Migration** |
| `odds_timestamp` | **MISSING** | Mandatory | timestamptz | **Add via Migration** |
| `odds_source` | **MISSING** | Mandatory | text | **Add via Migration** |
| `feature_status` | **MISSING** | Mandatory | text | **Add via Migration** |
| `feature_quality` | **MISSING** | Mandatory | text | **Add via Migration** |
| `feature_provenance` | **MISSING** | Mandatory | text | **Add via Migration** |
| `training_safe` | **MISSING** | Mandatory | boolean | **Add via Migration** |
| `leakage_status` | **MISSING** | Mandatory | text | **Add via Migration** |
| `batch_id` | **MISSING** | Mandatory | text | **Add via Migration** |
| `audit_id` | **MISSING** | Mandatory | uuid | **Add via Migration** |

## 2. Verdict
The current `historical_feature_store` schema is **unfit for V17 Doctrine reconstruction**. 19 mandatory columns for provenance, leakage control, and specialist signals are missing. 

**Blocked:** No HFS reconstruction until migration `add_missing_doctrine_and_provenance_columns` is applied.
