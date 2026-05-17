# SIGMA TRAINING EXCLUSION AUDIT V1
**Run:** 2026-05-17 12:30 UTC

---

## The 2050 → Clean Training Slice Gap

| Level | Rows |
|---|---|
| Sigma audit pool (Supabase) | 1898 (66 dates) |
| Corpus total | 1521 (38 dates) |
| **Clean training-safe rows** | **1310** |
| Gap (sigma → training) | 588 |
| % captured in training | **69.0%** |

The corpus is not "the 2K sigma set." It is the **SIGMA_2K_SAFE_TRAINING_SLICE_V1** — the subset of sigma evidence with both verdict signals and confirmed results.

---

## Exclusion Category Breakdown

| Category | Rows | Recoverable | Action |
|---|---|---|---|
| A. No local verdict (Railway-only score) | ~620 (30 dates) | No (complex) | Pull from Supabase velo_verdicts |
| B. Verdict exists, no result scraped | ~76 (2 dates) | Yes | scrape_results_atr.py |
| C. In corpus, no result match | 211 | No | Accept as excluded |
| D. Recoverable (verdict+result not yet joined) | ~71 (2 dates) | Yes | Re-run corpus builder |
| E. X-tier (design exclusion from stats) | 199 | N/A | Keep in corpus, exclude from SR/frame |
| F. Missing horse_id | 0 | No | Accept |
| G. Insufficient signal fields | 3 | No | Accept |

---

## Category A — No Local Verdict (largest gap)

These are sigma rows from dates when VELO was scoring on Railway but local
verdict JSONs were not saved. The model was running, the predictions were made,
but only Supabase has the verdict data — not the local file system.

Affected dates: 30

To recover: pull velo_verdicts from Supabase for each missing date and write
them as local JSON files. Possible but requires a dedicated harvest script.

---

## What This Means for the '2K Training Brain'

| Claim | Reality |
|---|---|
| 2050 sigma rows | ✅ Correct — Supabase has this many |
| 721 training-safe rows (old) | ⚠️ Stale — corpus was last built April 19 |
| 1310 training-safe rows (current) | ✅ Post-rebuild with 38 dates |
| Full 2K clean training corpus | ❌ Not yet — need Category A recovery |

The correct name is: **SIGMA_2K_SAFE_TRAINING_SLICE_V1**

The full 2K brain requires recovering Category A rows (Railway-only dates).

---

## Governance

No scoring/model/staking changes. Exclusion audit only.

*SIGMA_TRAINING_EXCLUSION_AUDIT_V1 — sigma_training_dataset_exclusion_audit.py*