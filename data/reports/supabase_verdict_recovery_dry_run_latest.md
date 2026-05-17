# SUPABASE VERDICT RECOVERY — DRY RUN REPORT
**Run:** 2026-05-17 12:56 UTC
**Mode:** DRY_RUN

---

## Context: What the Category A Gap Actually Is

The exclusion audit identified ~620 rows / 30 dates in sigma_audits with no local
verdict JSON. The assumption was that Supabase velo_verdicts holds these.

**Reality:**

| Source | Dates available | Date range |
|---|---|---|
| Local verdict JSONs | 40 dates | 2026-03-17 to 2026-05-17 |
| Supabase velo_verdicts | 21 dates | 2026-04-22 to 2026-05-17 |
| sigma_audits | 66 dates | 2026-01-09 to 2026-05-17 |

Supabase velo_verdicts only holds recent data (April 22+). All April 22+ dates
already have local verdict JSONs. The pre-April-22 Category A gap is not in velo_verdicts.

---

## Phase A — velo_verdicts Full-Fidelity Recovery

**Candidates** (in velo_verdicts, not in local): **1 dates**

| Date | Races | Has Results | Signal Fidelity | Training Safe |
|---|---|---|---|---|
| 2026-04-26 | 22 | No | FULL (VP+MDS+IMP+PP) | No (no result file) |

**Phase A training impact:**
- Races: 22
- Training-safe rows estimated: 0 (requires results file)

---

## Phase B — sigma_audits Notes Reconstruction (Partial)

**Candidates** (sigma + results exist, no verdict JSON): **12 dates**

| Date | Sigma rows | Parseable | VP extracted | Signal fidelity | Training risk |
|---|---|---|---|---|---|
| 2026-03-19 | 26 | 0 | 0 | PARTIAL (VP only) | Category G likely |
| 2026-03-25 | 30 | 0 | 0 | PARTIAL (VP only) | Category G likely |
| 2026-03-28 | 32 | 32 | 32 | PARTIAL (VP only) | Category G likely |
| 2026-03-29 | 22 | 22 | 22 | PARTIAL (VP only) | Category G likely |
| 2026-03-31 | 27 | 27 | 27 | PARTIAL (VP only) | Category G likely |
| 2026-04-01 | 33 | 33 | 33 | PARTIAL (VP only) | Category G likely |
| 2026-04-02 | 27 | 27 | 27 | PARTIAL (VP only) | Category G likely |
| 2026-04-03 | 22 | 22 | 22 | PARTIAL (VP only) | Category G likely |
| 2026-04-12 | 36 | 36 | 36 | PARTIAL (VP only) | Category G likely |
| 2026-04-13 | 29 | 29 | 29 | PARTIAL (VP only) | Category G likely |
| 2026-04-14 | 35 | 35 | 35 | PARTIAL (VP only) | Category G likely |
| 2026-04-15 | 38 | 38 | 38 | PARTIAL (VP only) | Category G likely |

**Phase B total:** 301 races across 12 dates

⚠️ **Category G warning:** Phase B rows have VP but no MDS/improvement/place_prob.
These rows will enter the corpus with result_matched=True but will be excluded from
training by the Category G filter (missing 3+ of 4 key signal fields).

They are still useful for date coverage audits and basic VP-only analysis.

---

## Honest Gap Assessment

| Category | Rows | Status |
|---|---|---|
| Full Category A (exclusion audit estimate) | 620 rows / 30 dates | Documented |
| Recoverable Phase A (full fidelity) | 22 | Available — execute to recover |
| Recoverable Phase B (VP only) | 301 | Available — training value limited |
| Unrecoverable | 319 rows | Pre-04-22 Railway data not in Supabase |

**Recommendation:**
The pre-April 22 Railway scoring data is not stored in Supabase velo_verdicts.
The 1310-row SIGMA_2K_SAFE_TRAINING_SLICE_V1 is the correct corpus baseline.
Growth path: daily scoring accumulation + Phase A/B recovery if applicable.

---

## Next Steps

1. If Phase A races found: `--execute` to write verdict JSONs + rebuild corpus chain
2. If Phase B only: decide whether partial VP-only rows are worth adding
3. Accept the 1310-row baseline as-is — signals are stable and validated

---

## Governance

No scoring / model / staking / router / Telegram changes.
Recovery audit only. Classification: CORPUS_RECOVERY_AUDIT_ONLY

*RECOVER_SUPABASE_VERDICTS_TO_LOCAL_V1 — recover_supabase_verdicts_to_local.py*