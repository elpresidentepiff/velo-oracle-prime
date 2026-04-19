# VÉLØ Corpus Census Audit

**Revision:** 2026-04-18.01 | **Status:** PROVEN TRUTH

This document establishes the exact shape, count, and integrity of the VÉLØ historical data corpus.

---

## 1. Raw Organism Counts
Direct query against the live Supabase production instance:
- `velo_verdicts`: **1,234**
- `sigma_audits`: **1,078**
- `races`: **1,172**
- `race_results`: **1,049**
- `velo_post_race_reviews`: **324**

## 2. The 324-Row Join Failure (Diagnosed)
**Problem:** The initial dataset builder returned exactly 324 rows despite there being >1,000 scored races.
**Root Cause:** The script performed an inner join between `velo_verdicts` and `velo_post_race_reviews`.
**Missing Link Analysis:** `velo_post_race_reviews` is a newly introduced structural table. Its earliest row dates to **2026-04-13**. The historical reconciliation data from February and March only exists in `sigma_audits` (earliest row: 2026-02-27).
**Resolution:** The join contract was rewritten to use `sigma_audits` as the primary truth anchor, gracefully falling back to `velo_post_race_reviews` only for recent, richer miss-category classification.

## 3. Real Corpus Count
After applying the corrected canonical join and deduplicating multiple runs per race_id (keeping the latest `generated_at`), the true, reconciled historical corpus is:
- **Total Reconciled Races:** **784**

## 4. Join Coverage & Drift
- **Orphan Verdicts:** 1,234 verdicts -> 1,000 unique `race_ids`. 216 unique `race_ids` lack a corresponding `sigma_audits` record. This represents races that were scored but never successfully reconciled (due to Racing API 404s, missing historical subscriptions, or abandoned test runs).
- **Missing Labels:** Because "Honesty Labeling" (field mutation detection) was only implemented on 2026-04-18, the historical corpus currently defaults to `clean` unless `sigma_audits.miss_reason` explicitly contains a `divergence` string.
