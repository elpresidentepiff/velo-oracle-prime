# VÉLØ Live Feature Persistence Proof

**Revision:** 2026-04-18.01 | **Status:** PROVEN SURVIVAL

This document provides definitive proof that critical doctrine flags now survive the journey from feature construction into the live database.

---

## 1. The Flag Lifecycle

| Flag | Birth (File) | Survival Point | Persistence (DB) |
|---|---|---|---|
| `cash_run_flag` | `v17_feature_extractor.py` | `score_race_velo_prime` | `velo_verdicts.full_analysis` |
| `setup_run_flag`| `v17_feature_extractor.py` | `score_race_velo_prime` | `velo_verdicts.full_analysis` |
| `decoy_support_flag`| `v17_feature_extractor.py` | `score_race_velo_prime` | `velo_verdicts.full_analysis` |

---

## 2. Evidence: End-to-End Audit (2026-04-18)

- **Test Race:** `rac_11899862` (Ayr 1:10)
- **Verdict ID:** `ac83288e-ac04-411d-9c69-fe64ce4427d9`
- **Audit Tool:** `scripts/generate_cache_persistence_proof.py`
- **Result:**
```json
{
  "cash_run_flag": false,
  "setup_run_flag": false,
  "decoy_support_flag": false
}
```
*(Flags are present as `bool` values in the JSON blob; historical `null` or missing keys have been replaced by active persistence).*

---

## 3. Detected Blockers: Schema Drift
During the persistence proof, the following columns were identified as **MISSING** from the live Supabase schema, causing HTTP 400 errors:
- `fetch_timestamp`
- `predicted_field_size`
- `a_tier_suspect_cohort`
- `g_shadow_multiplier`

**Audit Verdict:** Feature survival inside the JSON blob is **PROVEN**. However, top-level table observability is currently **DEGRADED** due to schema drift.

---

## 4. Next Action: Unified Truth Reconstruction
1.  **Fix Schema:** Apply missing migrations to Supabase to enable top-level observability for these flags.
2.  **Dataset Re-Build:** Re-run the daily training truth pipeline to capture these flags for the 784-race corpus.
