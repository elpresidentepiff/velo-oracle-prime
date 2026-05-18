# MAY 18 FULL PIPELINE INCIDENT REPORT

**Date:** 2026-05-18  
**Classification:** INFRASTRUCTURE FAILURE — NOT A MODEL FAILURE  
**Status:** INVESTIGATION COMPLETE — PATCH PENDING OPERATOR APPROVAL  
**Learning:** BLOCKED

---

## A. Executive Summary

May 18 Sigma reported 7 evaluated races, 24 NR-ABSENT, 3 no-result. The NR-ABSENT classification is **incorrect**. Forensic audit proves zero true non-runners. The 24 exclusions are identity reconciliation failures caused by inconsistent synthetic horse ID normalisation between two code paths:

- **Scoring path** (`run_prime_today.py`): generates `RP_imperial guard` (spaces preserved)
- **Scraper path** (`scrape_results_atr.py`): generates `RP_imperialguard` (spaces stripped)
- **Sigma matcher** (`run_results_sigma.py` line 491): strict equality, no normalisation tolerance

Multi-word horse names always fail this strict match. Single-word names pass. The 7 sigma-evaluated races are exactly the 9 single-word-name predictions minus 2 with missing result races.

**May 18 is not a model performance result. It is an infrastructure failure.**

---

## B. Timeline

| Time | Event |
|---|---|
| 2026-05-18 morning | Racing API returns 401. RP PRIMARY policy activated. |
| 2026-05-18 morning | Orchestrator runs `FULL_ENGINE_RUN_RP_SOURCED`. 34 predictions generated from RP profile. |
| 2026-05-18 | Predictions persisted to Supabase `velo_verdicts` with synthetic IDs: `RP_{horse_norm}` where `horse_norm` column preserves spaces. |
| 2026-05-18 evening | SL scraper built to replace Racing API results endpoint. Generates synthetic IDs with `re.sub(r"[^a-z0-9]", "", name.lower())` — **strips spaces**. |
| 2026-05-18 evening | Sigma runs. Attempts strict horse_id equality match. 24 multi-word horse names fail match. Logged as NR-ABSENT. |
| 2026-05-18 evening | Sigma Telegram sent as "ABOVE BASELINE" — **invalid claim**. |
| 2026-05-18 late | Operator identifies sample as invalid. Sigma rejected. Forensic investigation opened. |
| 2026-05-18 late | Forensic audit confirms root cause: `SYNTHETIC_ID_NORMALISATION_DRIFT`. |

---

## C. Raw RP Inventory

| Metric | Value |
|---|---|
| RP profile rows for 2026-05-18 | 34+ (from `rp_runner_profile_latest.parquet`) |
| Venues covered | Carlisle (CRL), Lingfield, Redcar, Roscommon (ROS), Windsor, Wolverhampton |
| Races built from profile | 34 |
| horse_id type | Synthetic: `RP_{horse_norm}` |

---

## D. Prediction Artifact Audit

| Metric | Value |
|---|---|
| Supabase `velo_verdicts` rows | 34 |
| Local JSON rows | 34 |
| Unique race_ids | 34 |
| `top_rank_horse_id` WITH spaces | 25 |
| `top_rank_horse_id` NO spaces | 9 |
| `top_rank_horse_id` EMPTY | 0 |
| ID format | `RP_{horse_norm}` — `horse_norm` column preserves spaces |

Prediction identity shape: **mixed** — 9 single-word names (no spaces), 25 multi-word names (spaces in ID).

---

## E. Result Source Audit

| Metric | Value |
|---|---|
| Result source | `data/results_2026_05_18.json` (Sporting Life scraper) |
| Result races | 31 / 34 predicted races |
| Missing races | 3 (CRL_400, Lingfield_350, Windsor_610 — maiden/novice not matched by SL scraper) |
| Runner horse_id format | `RP_{re.sub(non-alnum, '', name.lower())}` — **STRIPS SPACES** |
| horse_ids=11/11 for CRL 2:30 | True — all 11 runners received IDs, but with different normalisation |

---

## F. Reconciliation Audit (Correct Taxonomy)

| Bucket | Count | Description |
|---|---|---|
| MATCH_WIN | 2 | Adalida (Lingfield), Lequinto (Windsor) |
| MATCH_PLACED | 1 | Wipeawayyourtears (Roscommon) |
| MATCH_MISS | 4 | Detective, Letmeseethecolts, Profiteer, Powernap |
| RESULT_RACE_MISSING | 3 | Genuinely no SL result for these race_ids |
| TRUE_NON_RUNNER | **0** | **Zero actual non-runners** |
| SYNTHETIC_ID_NORMALISATION_DRIFT | **22** | **Root cause — space in predicted ID vs no space in result ID** |
| HORSE_ID_MISMATCH_NAME_OK | 2 | Name resolves (apostrophes/special chars in horse name) |
| HORSE_ID_MISMATCH_UNKNOWN | 0 | — |

---

## G. Sigma Reconciliation Audit

**Sigma Line 491** (`run_results_sigma.py`):
```python
if runner.get("horse_id") == predicted_horse_id:  # STRICT EQUALITY
    found_in_result = True
```

**Sigma NR-ABSENT trigger** (line 499-501):
```python
if not found_in_result and predicted_horse_id and predicted_horse_id not in runner_ids_in_result:
    non_runners.append(race_id)
    print(f"  [NR-ABSENT] ...")
```

**The bug:** `runner_ids_in_result` is a set of result horse_ids (no spaces). `predicted_horse_id` has spaces. Strict set membership check fails. Horse is classified as non-runner.

**No name fallback exists in sigma.** If horse_id fails, horse is excluded. This is correct behaviour for the primary case (Racing API IDs are stable and canonical), but fails catastrophically when synthetic IDs use inconsistent normalisation.

---

## H. May 17 vs May 18 Comparison

| Dimension | May 17 | May 18 |
|---|---|---|
| Racing API status | AUTH_OK | AUTH_FAIL_401 |
| Racecard source | LIVE_API or CACHE | RP_PROFILE_FALLBACK |
| horse_id type | Real Racing API IDs (`hrs_...`) | Synthetic `RP_` IDs |
| Scoring ID normalisation | N/A (canonical IDs) | Spaces preserved in `horse_norm` |
| Result source | Racing API `/results` | Sporting Life scraper |
| Result ID normalisation | Racing API canonical | Spaces stripped |
| Sigma evaluated | Normal coverage | 7/34 (21%) |
| NR-ABSENT | Genuine NRs only | 24 identity failures |

May 17 worked because Racing API canonical IDs (`hrs_64780492`) are identical in both scoring and results. May 18 broke because synthetic IDs were generated by two different normalisations.

---

## I. Root Cause

```
COMPONENT:      Synthetic ID normalisation inconsistency
CONFIDENCE:     PROVEN_FROM_ARTIFACTS
```

**Scoring path** (`run_prime_today.py` `_load_rp_profile_as_racecards`):
```python
raw_hid = f"RP_{horse_norm_val}"
# horse_norm_val = RP profile 'horse_norm' column
# Column is lowercase with spaces: 'imperial guard'
# Result: 'RP_imperial guard'
```

**Scraper path** (`scrape_results_atr.py` `load_racecard_from_rp_profile`):
```python
horse_norm = re.sub(r"[^a-z0-9]", "", str(row.get("horse") or "").lower())
horse_id = _val(row.get("horse_id")) or f"RP_{horse_norm}"
# Strips ALL non-alphanumeric including spaces
# 'Imperial Guard' → 'imperialguard'
# Result: 'RP_imperialguard'
```

**Mismatch:**
```
Supabase: 'RP_imperial guard'   ≠   Result file: 'RP_imperialguard'
→ Sigma: NR-ABSENT (WRONG)
```

**Why single-word names passed:**
- `Adalida`, `Lequinto`, `Detective`, `Profiteer`, `Powernap` — no spaces in horse name
- Both paths produce identical IDs for single-word names
- All 9 no-space predictions matched correctly (minus 2 with RESULT_RACE_MISSING)

---

## J. Repair Plan (Pending Operator Approval)

**Fix target:** `scripts/run_prime_today.py` — `_load_rp_profile_as_racecards()`

```python
# Current (broken)
raw_hid = f"RP_{horse_norm_val}"

# Required fix
import re as _re
_canonical_norm = lambda s: _re.sub(r"[^a-z0-9]", "", str(s or "").lower())
raw_hid = f"RP_{_canonical_norm(horse_norm_val)}"
```

**Canonical synthetic ID rule** (to be locked in `RP_API_IDENTITY_BRIDGE_V1.md`):
```
synthetic_id = "RP_" + re.sub(r"[^a-z0-9]", "", horse_name.lower())
```
All spaces, apostrophes, hyphens stripped. Lowercase alphanumeric only.

**After patch:**
1. All future RP-sourced predictions will use no-space IDs
2. Re-run SL scraper for May 18 (will use same normalisation as it already does)
3. Re-run sigma for May 18
4. Verify matched race coverage ≥ 90%
5. If valid, assess May 18 model performance

**Supabase historical records:** May 18 velo_verdicts rows have space-format IDs. These are the forensic record of what happened. Do not retroactively patch them. They are a sealed incident artifact.

**Also needed in sigma** (secondary fix, pending approval): Add normalised-name fallback for RP-sourced predictions when horse_id match fails. This creates defence-in-depth against future normalisation drift.

---

## K. Learning Block Confirmation

```
LEARNING_ALLOWED              = FALSE
EOD_CONSUME                   = BLOCKED
SHADOW_CONSUME                = BLOCKED
TRAINING_DATASET_UPDATE       = BLOCKED
SIGMA_VALID                   = FALSE
MODEL_CONCLUSION_ALLOWED      = FALSE
```

The 7 evaluated races (2W/1P/4M, SR 28.6%) are not rejected as a result — they are correctly matched. But they are not a valid daily sample. May 18 cannot enter learning until full coverage sigma is complete.

---

## L. No Model Conclusion Confirmation

May 18 Sigma cannot be used to make any claim about:
- Model calibration
- SQPE accuracy
- VP probability validity
- Any feature signal
- Baseline comparison

The sentence "SIGMA above baseline — model calibration healthy" sent to Telegram on 18 May is **invalid and retracted.**

---

## M. Artifacts

| Artifact | Path |
|---|---|
| Forensic JSON | `data/reports/may18_full_pipeline_forensics.json` |
| Forensic MD | `data/reports/may18_full_pipeline_forensics.md` |
| Forensic script | `scripts/audit_may18_full_pipeline_forensics.py` |
| Incident report | `docs/engineering/MAY18_FULL_PIPELINE_INCIDENT_REPORT.md` |
| Identity bridge spec | `docs/engineering/RP_API_IDENTITY_BRIDGE_V1.md` |
| Sealed sigma audit | Supabase `sigma_audits` rows (6 rows — partial, do not consume) |
| Sealed result file | `data/results_2026_05_18.json` (SL scraper output — do not delete) |

---

**Governance locks active:**
```
NO_SCORING_CHANGE
NO_MODEL_CHANGE
NO_ROUTER_CHANGE
NO_STAKING_CHANGE
NO_TELEGRAM_CHANGE
NO_LIVE_STATE_MUTATION
NO_LEARNING_FROM_MAY18
PATCH_REQUIRES_OPERATOR_APPROVAL
```
