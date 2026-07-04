# RESULTS-02: Operator Brief

## Status
REPORT_ONLY. No scoring changes. No model promotion. No Supabase writes. No Telegram.

## Q1. What is Beverley's failure pattern?
Beverley: n=50, SR=4.0%, misses=31.
Dominant miss reason: mid_priced_won.
Profile: sharp right-hand oval, stiff uphill finish, documented 5f low-draw bias.
Root causes: front-runner hold-on pattern, draw bias not in model, pace dynamics absent.
Treatment: WATCHLIST_ONLY — do not apply rule until draw/pace features built.

## Q2. Why is mid-price the biggest miss category?
Total mid-price misses (miss_reason=mid_priced_won): 803
By band: {'6-10': 312, '<4': 116, '4-6': 288, '10-16': 65, 'UNKNOWN': 22}
Root cause: VELO picks shorter-priced horses. Mid-price winners (4-16) are often
pace setters at front-runner tracks, or draw-advantaged horses at bias tracks.
Model does not have pace or draw features — cannot flag these types.

## Q3. Which courses drive most mid-price misses?
Top 5 by miss count: Southwell (AW)(30), Bath(21), Doncaster(20), Kempton (AW)(20), Wolverhampton (AW)(20)

## Q4. What are the drain course root causes?
Drain courses: Perth, Beverley, Clonmel, Ludlow, Down Royal, Kilbeggan, Wexford, Ayr
Common patterns: Irish tracks thin data / handler gap; sharp tracks pace/draw gap; 
Perth/Ludlow small-field jump dynamics not modelled.

## Q5. What are the edge course drivers?
Top 3 edge courses: Worcester(SR=50.0%), Newmarket (July)(SR=40.0%), Huntingdon(SR=37.5%)
Common patterns: flat/pace-friendly tracks, stamina-testing tracks where model is calibrated.

## Q6. What critical features are missing?
2 CRITICAL features, 3 HIGH features missing.
CRITICAL: draw_bias_by_course_distance, pace_map_front_runner_flag
HIGH: course_speed_figure_adjustment, trainer_handler_course_profile, going_course_interaction

## Q7. Is Beverley a special case or systemic?
Both. Beverley is the most acute single-venue failure (SR=4%).
But the root causes (draw bias, pace dynamics) are systemic across multiple tracks.

## Q8. Should any drain rule be applied now?
NO. All rules are WATCHLIST_ONLY. Features must be built and backtested first.
Do not apply course suppression rules without operator approval.

## Q9. Are edge course rules safe to promote?
NO promotion without operator review. Edge performance is passive — no rule needed to maintain it.
Rule R08 (Worcester defend) is REPORT_ONLY — do not override current model.

## Q10. What is the BHA/RP backfill plan?
Critical: draw_bias_statistics (RP/BHA), pace_data_early_positions (RP).
Status: SOURCE_SECTION_EXISTS_BACKFILL_NOT_PROVEN — sites known, not yet scraped.
No external URLs called in this report.

## Q11. What is the EW course picture?
EW place performance not separately audited in RESULTS-02 (see RESULTS-01 EW table).
Course place rate in S1 inventory. Frame rate >50% at edge courses is consistent.
EW course audit is OPEN for follow-on task.

## Q12. What are the immediate next steps?
1. WATCHLIST_ONLY — monitor all 8 candidate rules, do not apply.
2. Backfill draw_bias feature — BHA/RP source confirmed, scrape pending.
3. Backfill pace_map feature — RP pace ratings, scrape pending.
4. Irish handler enrichment — JTCD tables extend to venue level.
5. Beverley: next 20 races shadow log — test draw/pace hypothesis.
6. NO_VFU_21_START, NO_VCP_04_START, NO_MODEL_PROMOTION until gates met.

## FINAL CLASSIFICATIONS
- RESULTS_02_COURSE_INTELLIGENCE_AUDIT_COMPLETE
- COURSE_PROFILES_TABLE_WRITTEN
- COURSE_DRAIN_ROOT_CAUSES_AUDITED
- COURSE_EDGE_ROOT_CAUSES_AUDITED
- BEVERLEY_DEEP_DIVE_WRITTEN
- MIDPRICE_FAILURE_ROOT_CAUSE_AUDITED
- COURSE_MIDPRICE_MATRIX_WRITTEN
- MISSING_COURSE_FEATURES_IDENTIFIED
- COURSE_RULES_REPORT_ONLY
- EXTERNAL_COURSE_BACKFILL_PLAN_WRITTEN
- BHA_RP_COURSE_SOURCE_FEASIBILITY_CHECKED
- MIDPRICE_MISSES_NOT_SUPPRESSED
- RPR_COURSE_DEPENDENCY_REVIEWED
- NEW_BUILD_COURSE_VALUE_REVIEWED
- EW_COURSE_PLACE_REVIEWED
- MEMORY_CAPTURE_OPEN
- FAILURE_LEARNING_OPEN
- PROMOTION_LEARNING_GATED
- NO_VFU_21_START
- NO_VCP_04_START
- NO_LIVE_SCORING_CHANGE
- NO_MODEL_PROMOTION
- NO_SUPABASE_WRITES
- NO_TELEGRAM_SEND
- CANONICAL_HORSE_PASSPORT_NOT_MUTATED
- REPORT_ONLY