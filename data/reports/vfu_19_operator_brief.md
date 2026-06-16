# VFU-19: Dual-Lane Cockpit Accounting Audit — Operator Brief

        ## S01 Mission Scope
        Reconcile VFU-18's dual-lane cockpit numbers row-by-row, add full accounting fields per row, audit the each-way profitability claim for evidentiary support, and issue an operator brief enumerating remediation options.

        ## S03 Label Reconciliation
        Matches VFU-18: True

        ## S04 VP Fire Reconciliation
        189 VP-fire rows have outcome_class=WIN, but only 186 carry dual_lane_label=WIN_LANE_CONFIRMED. The 3-row gap is explained by PLACE_SPECIALIST label priority (VFU-18 classify_dual_lane_label checks specialist_set before the VP-fire branch) — it is a documented label-precedence effect, not a counting error.

        ## S06 Each-Way Evidence Headline
        **Verdict:** PARTIAL_EW_SIGNAL_NOT_PROFIT_PROOF

        ## S11 VFU-20 Options (operator decision required)
        - **A** (FIELD_SIZE_REMEDIATION_FIRST): Recover/backfill field_size from local archives (34.8% -> target >=80% coverage) before further EW model work.
- **B** (PICK_SP_BACKFILL): Recover pick_sp from RP results to unlock EW returns calculation.
- **C** (PROSPECTIVE_DUAL_LANE_VALIDATION): Tag live predictions and validate dual-lane labels prospectively (30+ days).
- **D** (PLACE_SPECIALIST_WATCHLIST_VALIDATION): Track the 16 specialist watchlist horses live to validate the specialist label.
- **E** (HOLD_EW_DEVELOPMENT): Conservative path — pause EW development until field_size coverage exceeds 80%.

        Note: A and B are blockers for C and D. E is the conservative path. Operator must choose.

        ## S12 Final Classifications
        - VFU_19_DUAL_LANE_ACCOUNTING_COMPLETE
- LABEL_RECONCILIATION_VERIFIED
- VP_FIRE_RECONCILIATION_COMPLETE
- EW_EVIDENCE_AUDIT_COMPLETE
- OPERATOR_BRIEF_ISSUED
- NO_STAKING_INSTRUCTIONS_CREATED
- NO_LIVE_DOCTRINE_PROMOTION
- NO_VP_THRESHOLD_CHANGE
- CANONICAL_HORSE_PASSPORT_NOT_MUTATED
- NO_LIVE_SCORING_CHANGE
- NO_SUPABASE_WRITES
- NO_MODEL_PROMOTION
- NO_TELEGRAM_SEND
- NO_RACING_API_RESTORATION

        ## STOP
        STOP after VFU-19 — operator review required before VFU-20.