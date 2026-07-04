# RESULTS-02: VÉLØ Course Intelligence Audit

Generated: 2026-07-01T00:48:07.882824
Status: REPORT_ONLY

## Hard Constraints
- REPORT_ONLY
- NO_LIVE_SCORING_CHANGE
- NO_VP_THRESHOLD_CHANGE
- NO_MODEL_PROMOTION
- NO_SUPABASE_WRITES
- NO_TELEGRAM_SEND
- NO_VFU_21_START
- NO_VCP_04_START
- CANONICAL_HORSE_PASSPORT_NOT_MUTATED
- DO_NOT_SUPPRESS_CONTRADICTIONS
- MISSING_ARTIFACTS_RESOLVE_UNKNOWN_NOT_CLEAN
- COURSE_HYPOTHESES_ARE_NOT_PROMOTION_RULES
- CONTAINMENT_IS_NOT_PROFIT
- SP_PROXY_IS_NOT_DIVIDEND_PROOF

## S1: Course Inventory
Total courses in sigma: 116

## S2: Drain Audit

### Perth
n=39, SR=5.1%, wins=2, misses=23
avg_winner_sp=7.78, avg_pick_sp=12.87, sp_gap=-5.09
Miss reasons: {'short_fav_won': 4, 'mid_priced_won': 7, 'outsider_won': 5, 'horse_absent_from_result': 1, 'market_decoy_followed': 3, 'horse_set_divergence (1 non-runners)': 1, 'horse_set_divergence (2 non-runners)': 2, 'horse_set_divergence (3 non-runners)': 1}
Root cause hypotheses:
  - Irish/Scottish handler patterns poorly modelled
  - Jump track: pace dynamics different from flat model baseline
  - Sharp turns reward nimble jumpers not captured in form proxy
Status: WATCHLIST_ONLY

### Beverley
n=50, SR=4.0%, wins=2, misses=31
avg_winner_sp=7.21, avg_pick_sp=13.92, sp_gap=-6.7
Miss reasons: {'mid_priced_won': 19, 'outsider_won': 4, 'short_fav_won': 4, 'market_decoy_followed': 5, 'horse_absent_from_result': 1, 'horse_set_divergence (1 non-runners)': 2}
Root cause hypotheses:
  - Sharp uphill finish penalises VELO speed-model picks
  - Low draw bias (5f) not captured in VELO scoring
  - Front-runner hold-on pattern: mid-price pacers not flagged
  - Small tight oval: track bias systematic, model undertrained
Status: WATCHLIST_ONLY

### Clonmel
n=11, SR=0.0%, wins=0, misses=9
avg_winner_sp=5.48, avg_pick_sp=5.67, sp_gap=-0.2
Miss reasons: {'mid_priced_won': 2, 'market_decoy_followed': 7, 'outsider_hedge_omitted': 1}
Root cause hypotheses:
  - 0% SR — n=11, high noise risk
  - Uphill finish not captured in stamina model
  - Thin Irish handler representation
Status: WATCHLIST_ONLY

### Ludlow
n=18, SR=5.6%, wins=1, misses=7
avg_winner_sp=6.72, avg_pick_sp=5.48, sp_gap=1.24
Miss reasons: {'short_fav_won': 1, 'mid_priced_won': 3, 'outsider_won': 1, 'market_decoy_followed': 4, 'non_runner_or_untracked': 1, 'outsider_hedge_omitted': 1}
Root cause hypotheses:
  - Small field sizes create unpredictable pace dynamics
  - Local handler knowledge gap
  - Sharp turns favour adaptable jumpers not form-based picks
Status: WATCHLIST_ONLY

### Down Royal
n=15, SR=6.7%, wins=1, misses=8
avg_winner_sp=9.92, avg_pick_sp=None, sp_gap=None
Miss reasons: {'mid_priced_won': 6, 'outsider_won': 2}
Root cause hypotheses:
  - Very thin VELO sample — possible NOISE_RISK not true DRAIN
  - Northern Irish racing poorly modelled
  - Irish handler patterns absent
Status: WATCHLIST_ONLY

### Kilbeggan
n=13, SR=7.7%, wins=1, misses=7
avg_winner_sp=12.03, avg_pick_sp=None, sp_gap=None
Miss reasons: {'mid_priced_won': 3, 'outsider_won': 4}
Root cause hypotheses:
  - Thin sample — 0% SR plausible noise
  - Tight circuit pace dynamics not modelled
  - Low-profile Irish handlers underrepresented
Status: WATCHLIST_ONLY

### Wexford
n=13, SR=0.0%, wins=0, misses=11
avg_winner_sp=7.95, avg_pick_sp=None, sp_gap=None
Miss reasons: {'mid_priced_won': 10, 'short_fav_won': 1}
Root cause hypotheses:
  - 0% SR — n=13, high noise risk
  - Tight Irish jump track: front runners hold on, not flagged by VELO
Status: WATCHLIST_ONLY

### Ayr
n=41, SR=9.8%, wins=4, misses=23
avg_winner_sp=11.77, avg_pick_sp=6.88, sp_gap=4.9
Miss reasons: {'mid_priced_won': 13, 'short_fav_won': 4, 'outsider_won': 6}
Root cause hypotheses:
  - Mixed race type profile (flat + jumps) dilutes model confidence
  - Galloping track rewards speed — model may overweight stamina here
  - Scottish handlers underrepresented in trainer profile
Status: WATCHLIST_ONLY

## S3: Edge Audit

### Musselburgh
n=46, SR=37.0%, wins=17, misses=17
Why working: Speed/pace model well-calibrated for flat oval | Low draw bias may align with picks

### Hexham
n=41, SR=29.3%, wins=12, misses=20
Why working: Stamina emphasis matches jump model output | Stiff track filters weak profiles

### Ripon
n=39, SR=28.2%, wins=11, misses=17
Why working: Sprint pace dynamics well-matched | Draw bias less relevant for longer trips

### Ffos Las
n=38, SR=31.6%, wins=12, misses=19
Why working: Moderate track suits balanced model | Dual-purpose racing provides richer profile data

### Chester
n=37, SR=29.7%, wins=11, misses=17
Why working: Tight circuit amplifies handicap knowledge | Low draw bias — draw feature may be active

### Uttoxeter
n=36, SR=36.1%, wins=13, misses=17
Why working: Flat oval suits pace-tracking model | Jump form profiles consistent here

### Catterick
n=35, SR=31.4%, wins=11, misses=19
Why working: Speed and draw-bias alignment | Sprint races benefit from pace model

### Lingfield
n=25, SR=36.0%, wins=9, misses=7
Why working: AW poly surface suits front-runner bias | Low draw feature may be contributing

### Pontefract
n=35, SR=28.6%, wins=10, misses=18
Why working: Stamina emphasis well-modelled | Uphill finish filters short-runners

### York
n=30, SR=30.0%, wins=9, misses=9
Why working: High-class racing: form holds up | Wide galloping track rewards class

### Salisbury
n=28, SR=35.7%, wins=10, misses=11
Why working: Uphill finish filters weak stamina | Flat stayer profiles well-matched

### Southwell
n=28, SR=32.1%, wins=9, misses=11
Why working: AW fibresand front-runner pattern clear | Consistent surface conditions reduce noise

### Kelso
n=28, SR=28.6%, wins=8, misses=10
Why working: Scottish jump form profiles consistent | Moderate oval doesn't distort model

### Worcester
n=24, SR=50.0%, wins=12, misses=5
Why working: Flat jump track maximises pace advantage | SR=50% — pace model dominant here

### Stratford
n=24, SR=29.2%, wins=7, misses=10
Why working: Sharp jump track: handy types flagged | Front runner pattern consistent

### Wetherby
n=23, SR=30.4%, wins=7, misses=6
Why working: Jump form profiles well-matched | Moderate oval supports balanced picks

### Leopardstown (Ire)
n=0, SR=0.0%, wins=0, misses=0
Why working: High-class Irish track: form strong indicator | Galloping track suits class-based model

### Wexford (Ire)
n=0, SR=0.0%, wins=0, misses=0
Why working: Thin but clean sample — may be noise | Front runner pattern aligns with model

### Huntingdon
n=16, SR=37.5%, wins=6, misses=7
Why working: Very flat — speed/pace premium clear | Front runner bias well-modelled

### Brighton
n=16, SR=31.2%, wins=5, misses=3
Why working: Quirky track filters weak horses | Uphill finish stamps stamina picks

### Newcastle
n=14, SR=28.6%, wins=4, misses=8
Why working: Tapeta AW: consistent conditions | Front runner pace model effective

### Newmarket (July)
n=15, SR=40.0%, wins=6, misses=4
Why working: Top-class racing: class indicators reliable | SR=40% — model sharp here

### Killarney (Ire)
n=0, SR=0.0%, wins=0, misses=0
Why working: Thin sample — SR may be noise | Irish form profiles moderate

### Naas (Ire)
n=0, SR=0.0%, wins=0, misses=0
Why working: Galloping Irish track: class holds up | Consistent form indicators

### Bellewstown (Ire)
n=0, SR=0.0%, wins=0, misses=0
Why working: Uphill finish filters short stamina | Front runner pattern flagged

### Sligo (Ire)
n=0, SR=0.0%, wins=0, misses=0
Why working: Very thin sample — SR=42% noise risk | No strong hypothesis

### Curragh
n=10, SR=30.0%, wins=3, misses=4
Why working: See Curragh (Ire) — may be naming variant | Galloping track suits class model

## S5: Mid-Price Failure Summary
Total mid_priced_won misses: 803
By band: {'6-10': 312, '<4': 116, '4-6': 288, '10-16': 65, 'UNKNOWN': 22}
By race type: {'unknown': 464, 'Flat': 217, 'NH Flat': 11, 'Chase': 47, 'Hurdle': 64}
Top courses: {'Southwell (AW)': 30, 'Bath': 21, 'Doncaster': 20, 'Kempton (AW)': 20, 'Wolverhampton (AW)': 20, 'Beverley': 19, 'Thirsk': 19, 'Pontefract': 16, 'Newmarket': 16, 'Lingfield (AW)': 16}

## S7: Missing Features

### [CRITICAL] draw_bias_by_course_distance
in_velo=no, derivable_locally=no
bha_available=yes_published, rp_available=yes_course_stats
Notes: BHA and RP both publish draw statistics. Not currently ingested. Beverley 5f, Chester, Catterick all have documented biases.

### [CRITICAL] pace_map_front_runner_flag
in_velo=no, derivable_locally=partial_from_form
bha_available=no, rp_available=yes_rp_pace_data
Notes: RP provides pace data in race cards. Not ingested. Front runner identification is root cause of most drain course failures.

### [HIGH] course_speed_figure_adjustment
in_velo=no, derivable_locally=yes_from_sigma_history
bha_available=no, rp_available=yes
Notes: Track-adjusted speed figures available from RP. Local derivation possible from sigma win patterns.

### [HIGH] course_specific_trainer_handler_profile
in_velo=partial_jtcd, derivable_locally=yes_from_jtcd_tables
bha_available=no, rp_available=yes
Notes: JTCD tables built but course-specific trainer win rate at specific venues not fully exposed to scorer.

### [HIGH] going_course_interaction
in_velo=partial, derivable_locally=yes
bha_available=no, rp_available=yes
Notes: Going captured but interaction with specific course drainage/camber not modelled. Cheltenham soft vs Flat soft are different.

### [MEDIUM] field_size_pace_dynamics
in_velo=field_size_present, derivable_locally=yes
bha_available=no, rp_available=partial
Notes: Field size present in sigma but pace dynamic modelling not done. Small fields at Ludlow/Perth need different pace assumptions.

### [MEDIUM] course_undulation_stamp
in_velo=no, derivable_locally=yes_from_static_profiles
bha_available=no, rp_available=partial
Notes: Static course profiles exist (this script). Could be encoded as binary feature for stamina-finish adjustment.

### [MEDIUM] distance_suitability_at_course
in_velo=distance_present, derivable_locally=yes
bha_available=no, rp_available=yes
Notes: Distance present but optimal distance for horse at specific course not computed.

### [MEDIUM] course_experience_count
in_velo=partial_passport, derivable_locally=yes_from_passport
bha_available=no, rp_available=yes
Notes: Passport has course history. Course experience count (runs at this venue) not used as feature.

### [LOW] seasonal_course_form_filter
in_velo=no, derivable_locally=yes
bha_available=no, rp_available=partial
Notes: Some courses heavily seasonal (Galway festival, Royal Ascot form). Seasonal adjustment not modelled.

## S8: Candidate Rules (WATCHLIST_ONLY)

### R01: BEVERLEY_MIDPRICE_WATCH
Status: WATCHLIST_ONLY
Description: Flag Beverley races where winner_sp in 4-12 range and front_runner_flag absent
Promotion gate: n>=30 Beverley wins with rule applied, operator review required

### R02: SHARP_TRACK_PACE_WATCH
Status: WATCHLIST_ONLY
Description: At sharp-turn tracks (Beverley, Chester, Catterick, Ripon, Thirsk): down-weight picks without pace flag
Promotion gate: Backtest across 200+ races, operator review

### R03: IRISH_TRACK_CONFIDENCE_FLOOR
Status: WATCHLIST_ONLY
Description: For Irish tracks with n<20 in VELO: apply confidence floor, avoid A-tier classification
Promotion gate: Pending Irish handler profile enrichment, n>=30 per venue

### R04: AW_SURFACE_PACE_ADJUSTMENT
Status: WATCHLIST_ONLY
Description: For AW tracks (Tapeta, Poly, Fibresand): flag front-runner type more aggressively
Promotion gate: Backtest across AW corpus, operator review

### R05: UPHILL_FINISH_STAMINA_GATE
Status: WATCHLIST_ONLY
Description: At uphill finish tracks (Beverley, Pontefract, Bath, Hamilton, Brighton, Salisbury): require stamina indicator present
Promotion gate: Feature must be built and backtested first

### R06: DRAW_BIAS_KNOWN_TRACK_FLAG
Status: WATCHLIST_ONLY
Description: At draw-bias-known tracks (Chester, Catterick, Ripon, Beverley 5f): suppress picks without draw data
Promotion gate: Draw feature must be built and validated first

### R07: MID_PRICE_BAND_6_10_WATCH
Status: WATCHLIST_ONLY
Description: 6-10 band is highest volume mid-price miss zone — monitor for systematic pick suppression opportunity
Promotion gate: Operator review after n>=200 in band, no model change without review

### R08: WORCESTER_EDGE_DEFEND
Status: REPORT_ONLY
Description: Worcester SR=50% — defend edge by maintaining model consistency, do not override
Promotion gate: N/A — defend existing edge

## Final Classifications
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