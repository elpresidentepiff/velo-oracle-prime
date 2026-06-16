# VFU-19: Dual-Lane Cockpit Accounting Audit

**Validation version:** VFU_19_DUAL_LANE_ACCOUNTING_AUDIT_V1
**Status:** DRY-RUN ONLY — blocked_from_live_use=True

## Label Reconciliation
- Total rows: 3052
- Matches VFU-18: True

## VP Fire Reconciliation
- Total VP fires: 447
- WIN_LANE_CONFIRMED: 186 (41.6%)
- 189 VP-fire rows have outcome_class=WIN, but only 186 carry dual_lane_label=WIN_LANE_CONFIRMED. The 3-row gap is explained by PLACE_SPECIALIST label priority (VFU-18 classify_dual_lane_label checks specialist_set before the VP-fire branch) — it is a documented label-precedence effect, not a counting error.

## Each-Way Evidence Audit
- Rows missing field_size: 1989 (65.2%)
- EW_BLOCKED_FIELD_SIZE: 809
- EW_BLOCKED_INSUFFICIENT_DATA: 1774
- EW_RESULT_CONFIRMED: 69
- EW_RESULT_POSSIBLE: 25
- **Verdict: PARTIAL_EW_SIGNAL_NOT_PROFIT_PROOF**

VFU-18's EW-profitable rows are NOT proof of system-wide EW profitability. field_size is unknown for 1989/3052 rows (65.2%) system-wide. Of rows with an actionable win/place signal, 809 are specifically blocked on missing field_size (EW_BLOCKED_FIELD_SIZE); the remaining field_size-missing rows fall under INSUFFICIENT_PLACE_DATA/PLACE_SPECIALIST/EVENT_ONLY_UNUSABLE and get EW_BLOCKED_INSUFFICIENT_DATA instead.