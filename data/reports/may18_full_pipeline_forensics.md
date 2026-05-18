# MAY 18 FULL PIPELINE FORENSICS

**Date:** 2026-05-18
**Generated:** 2026-05-18 23:09 UTC
**Classification:** READ-ONLY AUDIT — no scoring, no learning, no state mutation

---

## Classification

```
MAY18_SIGMA_INVALID_SAMPLE
RESULT_RECONCILIATION_FAILURE
RP_IDENTITY_BRIDGE_FAILURE
SYNTHETIC_ID_NORMALISATION_DRIFT
NO_LEARNING_ALLOWED
```

---

## Coverage Numbers

| Metric | Value |
|---|---|
| Expected predicted races | 34 |
| Supabase velo_verdicts rows | 34 |
| Result races in file (SL scraper) | 31 |
| Sigma reported evaluated | 7 |
| Sigma reported NR-ABSENT | 24 |
| Sigma reported no-result | 3 |
| **Forensic true matches** | **7** |
| **Forensic identity failures** | **24** |
| Forensic RESULT_RACE_MISSING | 3 |
| Forensic TRUE_NON_RUNNER | 0 |

---

## Reconciliation Taxonomy (Correct Classification)

| Bucket | Count | Meaning |
|---|---|---|
| MATCH_WIN | 2 | Predicted horse won |
| MATCH_PLACED | 1 | Predicted horse 2nd/3rd |
| MATCH_MISS | 4 | Predicted horse ran, didn't place |
| RESULT_RACE_MISSING | 3 | Race not in SL result file |
| TRUE_NON_RUNNER | 0 | Confirmed WD/NR/PU |
| **SYNTHETIC_ID_NORMALISATION_DRIFT** | **22** | **Root cause — ID mismatch** |
| HORSE_ID_MISMATCH_NAME_OK | 2 | Name matches but ID doesn't |
| HORSE_ID_MISMATCH_UNKNOWN | 0 | No match at all |
| UNKNOWN | 0 | Unclassified |

---

## Root Cause — Proven from Artifacts

**Component:** Synthetic ID normalisation inconsistency

### Scoring path (`run_prime_today.py`)
```python
raw_hid = f"RP_{horse_norm_val}"
# horse_norm_val = RP profile horse_norm column
# PRESERVES SPACES
# 'Imperial Guard' → horse_norm='imperial guard' → 'RP_imperial guard'
```

### Scraper path (`scrape_results_atr.py`)
```python
horse_norm = re.sub(r"[^a-z0-9]", "", name.lower())
# STRIPS SPACES AND ALL NON-ALPHANUMERIC
# 'Imperial Guard' → 'imperialguard' → 'RP_imperialguard'
```

### Sigma matcher (`run_results_sigma.py` line 491)
```python
if runner.get("horse_id") == predicted_horse_id:  # STRICT EQUALITY
```

### Result
```
'RP_imperial guard' != 'RP_imperialguard'
→ found_in_result = False
→ NR-ABSENT (misclassified)
```

### Evidence
- Supabase `velo_verdicts.top_rank_horse_id`: `'RP_imperial guard'` (with space)
- `results_2026_05_18.json` runner `horse_id`: `'RP_imperialguard'` (no space)
- 25/34 predictions have spaces in synthetic ID
- 9/34 single-word names (no spaces) matched correctly → exactly the 7 sigma evaluated + 2 RESULT_RACE_MISSING

---

## Races Marked NR-ABSENT by Sigma (True Classification)

These were NOT non-runners. They were identity join failures:

- `2026-05-18_Wolverhampton_900` — predicted `RP_kelly burn` vs result `rp_kellyburn`
- `2026-05-18_Wolverhampton_830` — predicted `RP_dontwaste a moment` vs result `rp_dontwasteamoment`
- `2026-05-18_Wolverhampton_800` — predicted `RP_silkies sib` vs result `rp_silkiessib`
- `2026-05-18_Wolverhampton_730` — predicted `RP_lyra lea` vs result `rp_lyralea`
- `2026-05-18_Windsor_810` — predicted `RP_cape toronada` vs result `rp_capetoronada`
- `2026-05-18_Windsor_740` — predicted `RP_sir william` vs result `rp_sirwilliam`
- `2026-05-18_Windsor_710` — predicted `RP_grey sands` vs result `rp_greysands`
- `2026-05-18_Windsor_540` — predicted `RP_rhythm n hooves` vs result `rp_rhythmnhooves`
- `2026-05-18_Redcar_443` — predicted `RP_long shot` vs result `rp_longshot`
- `2026-05-18_Redcar_410` — predicted `RP_harswell river` vs result `rp_harswellriver`
- `2026-05-18_Redcar_240` — predicted `RP_electric lightning` vs result `rp_electriclightning`
- `2026-05-18_ROS_820` — predicted `RP_cuckaloo hill` vs result `rp_cuckaloohill`
- `2026-05-18_ROS_650` — predicted `RP_rising sky` vs result `rp_risingsky`
- `2026-05-18_ROS_550` — predicted `RP_irish rumour` vs result `rp_irishrumour`
- `2026-05-18_ROS_450` — predicted `RP_cosmic funk` vs result `rp_cosmicfunk`
- `2026-05-18_Lingfield_422` — predicted `RP_recon mission` vs result `rp_reconmission`
- `2026-05-18_Lingfield_250` — predicted `RP_high favour` vs result `rp_highfavour`
- `2026-05-18_Lingfield_220` — predicted `RP_panama black` vs result `rp_panamablack`
- `2026-05-18_CRL_435` — predicted `RP_mereside princess` vs result `rp_meresideprincess`
- `2026-05-18_CRL_330` — predicted `RP_billy no mates` vs result `rp_billynomates`
- `2026-05-18_CRL_300` — predicted `RP_iris dancer` vs result `rp_irisdancer`
- `2026-05-18_CRL_230` — predicted `RP_imperial guard` vs result `rp_imperialguard`

---

## Races With No Result File Coverage

These races genuinely had no SL scraper match (maiden/novice races outside scraper's field coverage):

- `2026-05-18_Windsor_610` — Race not in Sporting Life result file
- `2026-05-18_Lingfield_350` — Race not in Sporting Life result file
- `2026-05-18_CRL_400` — Race not in Sporting Life result file

---

## Sigma Sample — Invalid

The 7 races sigma evaluated are only the single-word horse names (no spaces in synthetic ID):
- Adalida (WIN), Lequinto (WIN), Wipeawayyourtears (PLACED)
- Detective (MISS), Letmeseethecolts (MISS), Profiteer (MISS), Powernap (MISS)

**This is NOT a representative sample of May 18 predictions.**
**No model conclusion is possible from this sigma.**

---

## Learning Guard

```
LEARNING_ALLOWED              = FALSE
EOD_CONSUME                   = BLOCKED
SHADOW_CONSUME                = BLOCKED
TRAINING_DATASET_UPDATE       = BLOCKED
SIGMA_VALID                   = FALSE
```

Required before unblocking:
1. Patch synthetic ID normalisation to be consistent (strip spaces in scoring path)
2. Re-run SL scraper to regenerate result file with consistent IDs
3. Re-run sigma with consistent IDs
4. Verify matched race coverage ≥ 90%
5. Operator approval

---

## What Did NOT Fail

- Racing Post files are legitimate
- RP ingestion produced 34 races correctly
- SQPE scoring fired correctly
- Sporting Life scraper matched 31/34 races
- Sigma machinery is correct — it was given inconsistent IDs as input

**This is an infrastructure identity bridge failure, not a model failure.**

---

## Required Patch (Pending Operator Approval)

In `run_prime_today.py` `_load_rp_profile_as_racecards()`:
```python
# Current (broken)
raw_hid = f"RP_{horse_norm_val}"

# Fix: strip spaces and non-alphanumeric — match the canonical norm
import re as _re
raw_hid = "RP_" + _re.sub(r"[^a-z0-9]", "", str(horse_norm_val or "").lower())
```

This makes scoring path IDs match the scraper path IDs everywhere.

**Commit only after operator approves this patch.**
