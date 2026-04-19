# VÉLØ Schema Drift Reconciliation Dossier

**Revision:** 2026-04-18.02 | **Status:** MANUAL EXECUTION REQUIRED

This dossier establishes the exact SQL needed to restore the VÉLØ Truth Plane. The Supabase Management API is currently blocked (403), so these changes must be applied manually via the Supabase SQL Editor.

---

## 1. Missing Live Columns (Audit 2026-04-18)

| Canonical Column | Data Type | Migration Source | Purpose |
|---|---|---|---|
| `fetch_timestamp` | TIMESTAMPTZ | `20260418_001` | Mutation detection (ground-shift). |
| `predicted_field_size` | INTEGER | `20260418_001` | Mathematical divergence audit. |
| `a_tier_weak_place_flag` | BOOLEAN | `20260412_003` | Shadow monitor for weak A-Tier calls. |
| `g_shadow_multiplier` | FLOAT | `20260408_005` | Sentient bridge forensic auditing. |

---

## 2. Code Mitigation Status
**File:** `app/services/velo_prime_service.py`
- **Logic:** Tolerated stripping of the `honesty_labels` and `a_tier_suspect_cohort` groups.
- **Truth Impact:** Data for these columns is **SILENTLY LOST** in the top-level table but remains recoverable in the `full_analysis` JSON blob for recent rows.

---

## 3. Reconciliation SQL (Canonical)

Run this in the Supabase SQL Editor to restore full integrity. These statements are idempotent (`IF NOT EXISTS`).

```sql
-- 1. Honesty Labels (Mutation Detection)
ALTER TABLE public.velo_verdicts 
  ADD COLUMN IF NOT EXISTS fetch_timestamp TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS predicted_field_size INTEGER;

-- 2. Calibration & Audit Labels
ALTER TABLE public.velo_verdicts 
  ADD COLUMN IF NOT EXISTS confidence_level_raw TEXT,
  ADD COLUMN IF NOT EXISTS confidence_level_effective TEXT,
  ADD COLUMN IF NOT EXISTS active_components TEXT[],
  ADD COLUMN IF NOT EXISTS excluded_from_ensemble TEXT[];

-- 3. Shadow & Sentient Bridge
ALTER TABLE public.velo_verdicts 
  ADD COLUMN IF NOT EXISTS g_shadow_multiplier FLOAT,
  ADD COLUMN IF NOT EXISTS a_tier_weak_place_flag BOOLEAN DEFAULT FALSE;

-- 4. Registry & Annotations
COMMENT ON COLUMN public.velo_verdicts.fetch_timestamp IS 'Time of initial API fetch to detect ground-shift.';
COMMENT ON COLUMN public.velo_verdicts.predicted_field_size IS 'Field size at scoring time for divergence audit.';
COMMENT ON COLUMN public.velo_verdicts.a_tier_weak_place_flag IS 'Shadow cohort: A-Tier with weak place confirmation.';
```

---

## 4. Verification
Run `python scripts/generate_cache_persistence_proof.py`.
**Target Success:** `✓ SUCCESS: Verdict persisted` without `SCHEMA_DRIFT` critical alerts in the logs.
