# VFU-11 — 2K Sigma Investigation Unit
**Version:** VFU_11_2K_SIGMA_INVESTIGATION_UNIT_V1  
**Timestamp:** 2026-06-15T02:01:04.880452+00:00  
**VP Threshold:** 0.4 (UNCHANGED)  

---

## VFU-10 Law (carried forward)

> *No evidence becomes doctrine unless it was knowable before the race.*

---

## Executive Summary

- Total source rows discovered: **6,019**
- Total rows processed (master ledger): **6,019**
- CURRENT_ERA_VALIDATED: **3,052**
- PRE_SURGERY_MAY_QUARANTINE: **471** (inspect only)
- PRE_SURGERY_ARCHIVE_QUARANTINE: **2,165** (Mar–Apr, quarantine only)
- SKELETON_OR_NULL_DATE_EXCLUDED: **331** (excluded)
- Usable for VP analysis: **2,298**
- Usable for doctrine: **940**
- Blocked from live use: **2,967**
- Pattern candidates created: **7**
- Human review queue: **200**

---

## Source Inventory

| Source | Rows Discovered |
|--------|----------------|
| identity_enriched_autopsy | 1,263 |
| sigma_2k_training | 1,310 |
| sigma_audits_dump | 2,686 |
| sigma_results_eod_rows | 740 |
| archive_mar_2026 | 20 |

---

## Era Quality Report

| Era | n | Avg VP | SR | ID Confirmed | Doctrine Eligible |
|-----|---|--------|----|--------------|-------------------|
| CURRENT_ERA_VALIDATED | 3,052 | 0.302 | 25.8% | 559 (18.3%) | YES |
| PRE_SURGERY_MAY_QUARANTINE | 471 | 0.281 | 22.5% | 0 (0.0%) | QUARANTINE |
| PRE_SURGERY_ARCHIVE_QUARANTINE | 2,165 | 0.252 | 19.7% | 0 (0.0%) | QUARANTINE |
| SKELETON_OR_NULL_DATE_EXCLUDED | 331 | 0.262 | 15.4% | 0 (0.0%) | EXCLUDED |

---

## Identity Status Distribution

- **AMBIGUOUS**: 708
- **EOD_NON_CANONICAL**: 2,307
- **EVENT_ONLY_NO_HORSE**: 331
- **NAME_ONLY**: 1,977
- **RP_UID_CONFIRMED**: 559
- **UNMATCHED**: 137

---

## Time-Safety Status Distribution

- **NOT_APPLICABLE_EVENT_ONLY**: 331
- **PARTIAL_TIME_SAFE**: 471
- **TEMPORAL_CONTAMINATION_RISK**: 2,165
- **TIME_SAFE**: 3,052

---

## Pattern Candidates (Dry-Run Only)

All candidates: `blocked_from_live_use=True`, `human_approval_required=True`

| Pattern | n | n current-era | SR | Era Scope | Next Requirement |
|---------|---|-------------|-----|-----------|-----------------|
| DATA_QUALITY_DEBT_CANDIDATE | 2516 | 1265 | 22.9% | ALL_ERAS | n >= 50 + operator review before any doctrine consideration... |
| ERA_CONTAMINATION_CANDIDATE | 2165 | 0 | 19.7% | QUARANTINE_ERAS_ONLY | n >= 50 + operator review before any doctrine consideration... |
| FALSE_GREEN_CANDIDATE | 366 | 258 | 0.0% | ALL_ERAS | Identify shared feature pattern; confirm with VP>=0.40 sub-p... |
| IDENTITY_RESOLUTION_NEEDED | 2822 | 2112 | 24.5% | ALL_ERAS | n >= 50 + operator review before any doctrine consideration... |
| PASSPORT_OVERRIDE_CANDIDATE | 258 | 235 | 19.8% | ALL_ERAS | n >= 50 + operator review before any doctrine consideration... |
| SP_SHORTENING_CANDIDATE | 501 | 316 | 100.0% | ALL_ERAS | Build time-safe pre-era SP trajectory (per VFU-10 method)... |
| VP_SUPPRESSION_CANDIDATE | 582 | 342 | 100.0% | ALL_ERAS | Cross-reference with time-safe pre-era Passport snapshot (pe... |

---

## Top Data Quality Debts

- **SP_MISSING**: 3,074 instances
- **VP_MISSING**: 2,343 instances
- **HORSE_ID_MISSING**: 1,748 instances
- **horse_id_null — RP uid not in sigma row**: 1,263 instances
- **pick_sp_null — not stored in sigma union**: 1,156 instances

---

## Required Questions — Answers

**Q1 Total Sigma rows discovered:** 6,019
**Q2 Total rows processed:** 6,019
**Q3 Rows by era:** Current=3052, MayQ=471, ArchiveQ=2165, Skeleton=331
**Q4 Rows by evidence quality tier:** {'HIGH': 13, 'LOW': 1, 'MEDIUM': 8, 'None': 3175, 'TIER_A_FULL': 107}
**Q5 Rows by identity status:** {'AMBIGUOUS': 708, 'EOD_NON_CANONICAL': 2307, 'EVENT_ONLY_NO_HORSE': 331, 'NAME_ONLY': 1977, 'RP_UID_CONFIRMED': 559, 'UNMATCHED': 137}
**Q6 Usable for VP analysis:** 2,298
**Q7 Usable for course analysis:** 2,866
**Q8 Usable for price analysis:** 5,537
**Q9 Usable for Passport analysis:** 940
**Q10 Blocked from doctrine:** 2,967
**Q11 Excluded rows:** 331 (null/skeleton dates)
**Q12 Current-era findings valid:** YES
**Q13 Pre-surgery May viable:** YES
**Q14 Mar–Apr archive status:** QUARANTINE_INSPECT_ONLY
**Q15 Skeleton rows usable:** NO — excluded from all conclusions
**Q16 Top data quality debt:** SP_MISSING
**Q17 Top time-safety risk:** TEMPORAL_CONTAMINATION_RISK (2,165 rows)
**Q18 Top pattern candidates:** DATA_QUALITY_DEBT_CANDIDATE, ERA_CONTAMINATION_CANDIDATE, FALSE_GREEN_CANDIDATE
**Q19 Human review queue:** 200 cases
**Q20 VFU-12 recommended:** YES — Expand time-safe Passport snapshot coverage to Mar–Apr era horses. Specifically: (1) build per-race-date Passport snapsh...

---

## Hard Rules — Confirmed

- VP threshold: 0.40 — UNCHANGED
- Canonical Horse Passport: NOT MUTATED
- Supabase: NOT WRITTEN
- Live scoring: NOT CHANGED
- Model: NOT PROMOTED
- Telegram: NOT SENT
- Racing API: NOT RESTORED
- Mar–Apr: QUARANTINE ONLY — no doctrine, no Passport, no live use
- All pattern candidates: DRY_RUN_ONLY

---

## Final Classifications

```
VFU_11_2K_SIGMA_INVESTIGATION_UNIT_COMPLETE
SIGMA_MASTER_LEDGER_CREATED
ERA_BUCKETS_ENFORCED
MAR_APR_QUARANTINE_ONLY
CURRENT_ERA_NOT_BLENDED_WITH_PRE_SURGERY
TIME_SAFETY_STATUS_ASSIGNED
TEMPORAL_CONTAMINATION_BLOCKS_DOCTRINE
PATTERN_CANDIDATES_DRY_RUN_ONLY
HUMAN_REVIEW_QUEUE_CREATED
NO_LIVE_DOCTRINE_PROMOTION
NO_VP_THRESHOLD_CHANGE
CANONICAL_HORSE_PASSPORT_NOT_MUTATED
NO_LIVE_SCORING_CHANGE
NO_SUPABASE_WRITES
NO_MODEL_PROMOTION
NO_TELEGRAM_SEND
NO_RACING_API_RESTORATION
```