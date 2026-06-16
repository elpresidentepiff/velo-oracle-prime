# VFU-20: Field Size Remediation — Operator Brief

        ## S01 Mission Scope
        Recover, backfill, or prove irrecoverable field_size for the 1,989/3,052 rows missing it, then regenerate EW eligibility labels and rerun the VFU-18/19 reconciliation. The key output is truthful eligibility reconstruction, not improved-looking numbers.

        ## S06 Acceptance Criteria

        | Metric | Required |
        |---|---|
        | Starting rows | 3052 |
        | Missing field_size before | 1989 |
        | Missing field_size after | 152 |
        | Recovery rate | 92.36% |
        | Deterministic recovery count | 1336 |
        | Inferred recovery count | 501 |
        | Unrecoverable count | 152 |
        | EW label changes after repair | 749 |
        | EW profitability claim status | PARTIAL |
        | Tests | FULL_PASS |

        ## S09 VFU-21+ Note
        VFU-21 (pick_sp backfill), VFU-22 (prospective validation), and VFU-23 (specialist watchlist validation) remain NOT AUTHORIZED. This mission (VFU-20) does not start, schedule, or imply authorization for any of them.

        ## S11 Final Classifications
        - VFU_20_FIELD_SIZE_REMEDIATION_COMPLETE
- FIELD_SIZE_GAP_QUANTIFIED
- FIELD_SIZE_RECOVERY_PROVENANCE_WRITTEN
- EW_ELIGIBILITY_RECONCILED_AFTER_REPAIR
- EW_PROFITABILITY_CLAIM_REEVALUATED
- NO_VP_THRESHOLD_CHANGE
- NO_MODEL_PROMOTION
- NO_LIVE_SCORING_CHANGE
- NO_SUPABASE_WRITES
- NO_TELEGRAM_SEND
- CANONICAL_HORSE_PASSPORT_NOT_MUTATED
- REPORT_ONLY

        ## STOP
        STOP — operator review required before VFU-21.