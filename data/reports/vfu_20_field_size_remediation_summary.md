# VFU-20: Field Size Remediation and EW Eligibility Truth Repair

        **Validation version:** VFU_20_FIELD_SIZE_REMEDIATION_V1
        **Status:** DRY-RUN ONLY — blocked_from_live_use=True

        ## Recovery Audit
        - Starting rows: 3052
        - Missing field_size before: 1989
        - Missing field_size after: 152
        - Recovery rate: 92.36%
        - Deterministic recovery: 1336
        - Inferred recovery: 501
        - Unrecoverable: 152

        ## Label Reconciliation After Repair
        - Rows with label changed by repair: 30
        - All rows still valid label: True

        ## Each-Way Evidence Audit After Repair
        - EW label changes after repair: 749
        - EW analysis possible rows: 193 (6.32%)
        - **EW profitability verdict: PARTIAL**

        After repair, field_size remains unknown for 152/3052 rows (down from 1989). EW analysis is possible (EW_RESULT_CONFIRMED + EW_RESULT_POSSIBLE) for 193 rows (6.32%). Verdict is PARTIAL because 152 rows remain an unrecoverable source gap — partial improvement, not full proof.

        ## Final Classifications
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

        STOP after VFU-20 — operator review required before VFU-21.