# MAY 18 SYNTHETIC ID REGRESSION — COMMIT AUDIT

**Date:** 2026-05-18  
**Status:** ROOT CAUSE PROVEN — PATCH APPROVED (pending operator sign-off)  
**Incident ref:** MAY18_FULL_PIPELINE_INCIDENT_REPORT.md

---

## A. Exact Offending Commit

```
commit 1dc8d5bc78fa06f797d78fed1d6a6ad50858d6f2
Author: elpresidentepiff <219481177+elpresidentepiff@users.noreply.github.com>
Date:   Mon May 18 05:32:02 2026 -0700

ops(backfill): 2026-05-18 full engine run using RP primary profile fallback
```

**File:** `scripts/run_prime_today.py`  
**Function:** `_load_rp_profile_as_racecards()`  
**Lines (post-commit):** 236–237

---

## B. Whether It Was Part of Yesterday's Ingestion-Layout Work

**No.** The offending commit was authored on **May 18 itself at 05:32 AM PDT** — the same session that introduced the RP primary policy and performed the backfill. It was not part of prior-day ingestion-layout changes.

The commit that first introduced `_load_rp_profile_as_racecards()` was `6aff150` (one commit earlier, same session), where `horse_id` was taken directly from `row.get("horse_id")` with no synthetic generation at all. The synthetic ID logic was added in `1dc8d5b` to prevent `persist_race_predictions` from rejecting runners with missing `horse_id`.

---

## C. Bad Line — Before

```python
# commit 1dc8d5b — scripts/run_prime_today.py lines 236-237
raw_hid = _v(row.get("horse_id"))
if not raw_hid:
    horse_norm_val = str(row.get("horse_norm") or row.get("horse") or "").lower()
    raw_hid = f"RP_{horse_norm_val}" if horse_norm_val else None
```

**Why it's wrong:**  
The `horse_norm` column in `rp_runner_profile_latest.parquet` stores ALL-CAPS values with spaces preserved:

```
horse='Imperial Guard'   →   horse_norm='IMPERIAL GUARD'
```

`.lower()` converts case but preserves spaces:

```
'IMPERIAL GUARD'.lower() = 'imperial guard'
f"RP_{horse_norm_val}"   = 'RP_imperial guard'   ← SPACE PRESERVED
```

---

## D. Fixed Line — After

```python
raw_hid = _v(row.get("horse_id"))
if not raw_hid:
    horse_norm_val = _norm_horse_name(row.get("horse_norm") or row.get("horse") or "")
    raw_hid = f"RP_{horse_norm_val}" if horse_norm_val else None
```

`_norm_horse_name()` is defined at line 808 of the same file:

```python
def _norm_horse_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())
```

This strips ALL non-alphanumeric characters (spaces, apostrophes, hyphens) and lowercases:

```
'IMPERIAL GUARD' → 'imperial guard' → 'imperialguard'
f"RP_{horse_norm_val}" = 'RP_imperialguard'   ← NO SPACE
```

Now matches the Sporting Life scraper and sigma matcher normalisation.

---

## E. Regression Proof — Before and After

| Horse Name | prediction_id (BAD) | result_id (CORRECT) | match before | match after |
|---|---|---|---|---|
| Imperial Guard | `RP_imperial guard` | `RP_imperialguard` | **FAIL** | PASS |
| Ride The Thunder | `RP_ride the thunder` | `RP_ridethethunder` | **FAIL** | PASS |
| Trojan Soldier | `RP_trojan soldier` | `RP_trojansoldier` | **FAIL** | PASS |
| Cooley's Mist | `RP_cooley's mist` | `RP_cooleysmist` | **FAIL** | PASS |
| Billy No Mates | `RP_billy no mates` | `RP_billynomates` | **FAIL** | PASS |
| Dontwaste A Moment | `RP_dontwaste a moment` | `RP_dontwasteamoment` | **FAIL** | PASS |
| Plaid | `RP_plaid` | `RP_plaid` | PASS | PASS |
| Adalida | `RP_adalida` | `RP_adalida` | PASS | PASS |
| Letmeseethecolts | `RP_letmeseethecolts` | `RP_letmeseethecolts` | PASS | PASS |

**Failing before fix:** 6/9 (all multi-word names)  
**Failing after fix:** 0/9

---

## F. Why It Slipped Through

1. **No test for synthetic ID format existed.** The synthetic ID logic was introduced as a one-commit fix to stop `persist_race_predictions` rejecting runners. The fix worked (runners were no longer rejected). Nobody verified that the ID format matched what the result-side scraper would produce.

2. **The scraper was built the same evening.** The scoring ran in the morning. The result scraper was built hours later. The two ID generations were written in different contexts by the same session with no shared normalizer contract.

3. **Single-word horses passed.** `Adalida`, `Lequinto`, `Detective` — these matched correctly. Sigma returned 7 evaluated races without error. No alarm fired.

4. **horse_norm column format was unknown.** The `horse_norm` column in the RP profile was assumed to be lowercase — it is ALL CAPS. The `.lower()` call appeared to normalise it, masking the space-preservation problem.

---

## G. May 18 Artifact Repairability

The official May 18 prediction artifact in **Supabase `velo_verdicts`** contains the bad IDs (`RP_imperial guard`). These are the sealed forensic record of what happened. **They must not be overwritten.**

The Sporting Life result file `data/results_2026_05_18.json` was generated with correct (no-space) IDs. This file is correct and must not be regenerated.

**Options for sigma rerun:**

**Option A — Patch sigma matcher** (recommended):  
Add a normalised-ID fallback in `run_results_sigma.py` when primary strict match fails and both IDs are `RP_` synthetic:
```python
# After strict equality fails for RP_ ids:
if not found_in_result and predicted_horse_id.startswith("RP_"):
    norm_pred = re.sub(r"[^a-z0-9]", "", predicted_horse_id.lower())
    for runner in full_runners:
        rid = runner.get("horse_id", "")
        if re.sub(r"[^a-z0-9]", "", rid.lower()) == norm_pred:
            found_in_result = True
            break
```
This reads existing Supabase records as-is, normalises both sides before comparing. No prediction overwrite. No DB mutation. **Requires separate operator approval per governance.**

**Option B — Forensic copy**:  
Create a read-only `data/reports/may18_predictions_normalised_forensic.json` with IDs fixed for audit purposes only. Never replaces official artifact.

**Option C — Rerun predictions**:  
Not recommended. Would overwrite official May 18 Supabase records. Requires explicit operator approval with stale-overwrite protection.

**Recommended path:** Option A (sigma normalised fallback) + re-run sigma.

---

## H. Canonical Synthetic ID Rule (Locked)

```python
def rp_synthetic_id(name: str) -> str:
    """Canonical synthetic RP horse_id. Strip all non-alnum, lowercase, prefix RP_."""
    norm = re.sub(r"[^a-z0-9]+", "", str(name or "").lower())
    return f"RP_{norm}" if norm else ""
```

**Used in:** `run_prime_today.py` (scoring), `scrape_results_atr.py` (results), `audit_rp_synthetic_horse_ids.py` (audit)

All three must produce identical output for the same horse name.

---

## I. Patch Scope

**Commit 2 files:**
- `scripts/run_prime_today.py` — one line changed (line 236)
- `tests/test_rp_synthetic_id_normalisation.py` — new regression test

**Not changed in this commit:**
- `scripts/run_results_sigma.py` (sigma matcher — separate approval required)
- Any Supabase records
- Any scoring model
- Any router or staking

---

## J. Governance

```
PATCH_APPROVED         = PENDING_OPERATOR
NO_SCORING_CHANGE      = CONFIRMED
NO_MODEL_CHANGE        = CONFIRMED
NO_DB_OVERWRITE        = CONFIRMED
SIGMA_PATCH_SEPARATE   = YES — requires separate approval
MAY18_LEARNING_BLOCKED = TRUE (until valid sigma run completes)
```
