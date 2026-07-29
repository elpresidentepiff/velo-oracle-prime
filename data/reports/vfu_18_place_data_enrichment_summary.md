# VFU-18: Place Data Enrichment + Dual-Lane Cockpit

        **Validation version:** VFU_18_PLACE_DATA_ENRICHMENT_V1
        **Status:** DRY-RUN ONLY — blocked_from_live_use=True

        ## Field-Size Coverage
        - RP results races indexed: 1586
        - VFU-17 rows matched: 1063 / 3052 (34.8%)
        - Rows with EW conclusion blocked: 1989

        ## Dual-Lane Distribution
        | Label | Count |
        |---|---|
        | WIN_LANE_CONFIRMED | 186 |
| PLACE_LANE_CONFIRMED | 170 |
| EACH_WAY_REVIEW | 30 |
| WIN_SIGNAL_PLACE_OUTCOME | 44 |
| PLACE_SIGNAL_WIN_OUTCOME | 251 |
| FALSE_WIN_SIGNAL | 161 |
| FALSE_PLACE_SIGNAL | 436 |
| PLACE_SPECIALIST | 52 |
| INSUFFICIENT_PLACE_DATA | 1694 |
| EVENT_ONLY_UNUSABLE | 28 |

        ## Win Lane
        - VP >= 0.40 fires: 447
        - WIN_LANE_CONFIRMED: 186 (41.6%)
        - VP place conversion (WIN + PLACED): 58.2%

        ## Each-Way Summary
        - EW profitable (both legs): 234
        - EW place paid, win missed: 159
        - EW conclusion blocked (no field size): 1989

        ## Key Findings
        - VP >= 0.40 fired on 447 rows.
- WIN_LANE_CONFIRMED: 186 rows (41.6% of VP fires).
- EACH_WAY_REVIEW (placed, field_size>=5): 30 rows.
- WIN_SIGNAL_PLACE_OUTCOME (placed, field unknown/<5): 44 rows.
- FALSE_WIN_SIGNAL (VP fires, MISS/FRAME): 161 rows.
- PLACE_SPECIALIST: 52 rows from 16 horses.
- EACH_WAY profitable (both legs win): 234 rows.
- Field size coverage: 34.8% — 1989 rows EW conclusion blocked.

        ## Lineage
        - Scope: VFU-13 → VFU-17
        - Verdict: LINEAGE_CLEAN_PROCEED_TO_VFU18

        ## Final Classifications
        - VFU_18_PLACE_DATA_ENRICHMENT_COMPLETE
- VFU_LINEAGE_RECONCILED
- DUAL_LANE_CLASSIFICATIONS_CREATED
- PLACE_SPECIALIST_WATCHLIST_CREATED
- WIN_TO_PLACE_DOWNGRADES_REPORTED
- PLACE_TO_WIN_UPGRADES_REPORTED
- FIELD_SIZE_GAPS_REPORTED
- NO_STAKING_INSTRUCTIONS_CREATED
- NO_LIVE_DOCTRINE_PROMOTION
- NO_VP_THRESHOLD_CHANGE
- CANONICAL_HORSE_PASSPORT_NOT_MUTATED
- NO_LIVE_SCORING_CHANGE
- NO_SUPABASE_WRITES
- NO_MODEL_PROMOTION
- NO_TELEGRAM_SEND
- NO_RACING_API_RESTORATION

        ## Hard Rules
        - VP threshold: 0.4 (UNCHANGED)
        - No live doctrine promotion
        - No Passport mutation
        - No Supabase writes
        - No Racing API restoration
        - No Telegram send