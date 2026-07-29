# RESULTS-02: Course Feature Backfill Map

REPORT_ONLY. No external URLs called. All entries are static knowledge of BHA/RP site structure.


## [CRITICAL] draw_bias_statistics
Local status: ABSENT
BHA source: BHA raceday programme — draw statistics published for sprint distances
RP source: RP course stats pages — draw win % by stall/distance
Feasibility: SOURCE_SECTION_EXISTS_BACKFILL_NOT_PROVEN
Notes: Must be scraped/parsed and matched to course+distance combo. Not automated yet.

## [CRITICAL] pace_data_early_positions
Local status: ABSENT
BHA source: NOT_AVAILABLE
RP source: RP racecard — pace ratings sometimes published
Feasibility: SOURCE_SECTION_EXISTS_BACKFILL_NOT_PROVEN
Notes: RP pace ratings not consistently available. Manual check required.

## [HIGH] course_speed_par_figures
Local status: ABSENT
BHA source: NOT_AVAILABLE
RP source: RP speed ratings section
Feasibility: SOURCE_SECTION_EXISTS_BACKFILL_NOT_PROVEN
Notes: Track par figures used for speed figure normalisation. RP publishes these.

## [HIGH] trainer_course_win_rate
Local status: PARTIAL_JTCD
BHA source: BHA trainer stats — general, not course-specific
RP source: RP trainer profiles — course breakdown available
Feasibility: SOURCE_SECTION_EXISTS_BACKFILL_NOT_PROVEN
Notes: JTCD tables partially cover this. RP trainer course pages would enrich. Not scraped.

## [MEDIUM] going_stick_readings
Local status: GOING_DESCRIPTION_PRESENT
BHA source: BHA going reports — published pre-race
RP source: RP going updates
Feasibility: LOCAL_PRESENT_TEXT_ONLY
Notes: Going text is present (e.g. 'Soft To Heavy'). Numeric GoingStick reading not captured.

## [MEDIUM] field_size_sectional_pace
Local status: FIELD_SIZE_PRESENT
BHA source: NOT_AVAILABLE
RP source: RP sectional times — for major meetings only
Feasibility: UNSAFE_FOR_AUTOMATION
Notes: Sectional times only available for selected meetings. Cannot automate for full corpus.

## [MEDIUM] course_rpr_par
Local status: ABSENT
BHA source: NOT_AVAILABLE
RP source: RP RPR par by course/distance
Feasibility: SOURCE_SECTION_EXISTS_BACKFILL_NOT_PROVEN
Notes: RPR par figures published by RP. Would help normalise RPR by course.

## [MEDIUM] course_undulation_binary
Local status: PRESENT_IN_STATIC_PROFILES
BHA source: BHA course descriptions
RP source: RP course guides
Feasibility: LOCAL_DERIVABLE_FROM_STATIC_PROFILES
Notes: This script builds static profiles. Binary feature encodable now without scraping.